"""Sprint 2 / Frente 3 — services e multi-role (RN-003a / RN-004).

Cobre `change_roles` / `deactivate_user` / `reactivate_user`, a guarda do ultimo
Pastor (RN-004, incl. a extensao conservadora a `deactivate_user`), a uniao de
papeis (`has_any_role` / `has_all_roles`) e a trilha dupla AuditLog +
SecurityLog no schema do tenant.

Os services gravam logs via os helpers de `apps.core.audit`, que tem guarda de
schema public: para a trilha persistir, a operacao precisa rodar no schema de um
tenant. Por isso usamos `schema_context('tenant_a')` ao chamar os services que
devem auditar, e `transaction=True` (criar Church dispara DDL nao-transacional).
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.accounts.services import change_roles, deactivate_user, reactivate_user
from apps.core.models import AuditLog, SecurityLog

GOOD_PASSWORD = 'Senha@123'


@pytest.fixture
def restore_public_schema():
    """Restaura o search_path para o public apos testes que entram em um tenant.

    Igual ao padrao da Frente 2: o schema_context deve sair limpo, e qualquer
    fixture de Church subsequente exige estar no public.
    """
    yield
    connection.set_schema_to_public()


def _make_user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


# --------------------------------------------------------------------------- #
# Multi-role: uniao de permissoes (RN-003a)
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_has_any_role_and_has_all_roles():
    """has_any_role = OU dos papeis; has_all_roles = E (subconjunto)."""
    user = User(roles=['treasurer', 'leader'])

    # has_any_role: basta um.
    assert user.has_any_role('leader') is True
    assert user.has_any_role('pastor', 'leader') is True
    assert user.has_any_role('pastor') is False
    assert user.has_any_role('pastor', 'member') is False

    # has_all_roles: precisa de todos.
    assert user.has_all_roles('treasurer', 'leader') is True
    assert user.has_all_roles('leader') is True
    assert user.has_all_roles('treasurer', 'pastor') is False


@pytest.mark.django_db
def test_user_multi_role_union_of_permissions():
    """Um user ['treasurer','leader'] satisfaz mixins de ambos os papeis.

    Verifica a uniao na fonte (has_any_role) com os required_roles dos mixins de
    Lider e de Tesoureiro — sem precisar montar request: o que os mixins de papel
    avaliam e exatamente `has_any_role(*required_roles)`.
    """
    from apps.core.mixins import (
        LeaderOrPastorMixin,
        PastorRequiredMixin,
        TreasurerOrPastorMixin,
    )

    user = User(roles=['treasurer', 'leader'])

    assert user.has_any_role(*LeaderOrPastorMixin.required_roles) is True
    assert user.has_any_role(*TreasurerOrPastorMixin.required_roles) is True
    # Mas NAO satisfaz um mixin exclusivo de Pastor.
    assert user.has_any_role(*PastorRequiredMixin.required_roles) is False


# --------------------------------------------------------------------------- #
# change_roles + RN-004 (ultimo Pastor) + trilha de auditoria
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
def test_change_roles_updates_and_validates_choices(church_a, restore_public_schema):
    pastor = _make_user(church_a, 'p1@a.com', ['pastor'])
    member = _make_user(church_a, 'm1@a.com', ['member'])

    with schema_context('tenant_a'):
        change_roles(user=member, new_roles=['leader', 'treasurer'], actor=pastor)
    member.refresh_from_db()
    assert sorted(member.roles) == ['leader', 'treasurer']

    # Papel invalido e rejeitado.
    with schema_context('tenant_a'):
        with pytest.raises(ValidationError):
            change_roles(user=member, new_roles=['xpto'], actor=pastor)


@pytest.mark.django_db(transaction=True)
def test_cannot_remove_last_pastor(church_a, restore_public_schema):
    """RN-004: remover 'pastor' do unico Pastor ativo e rejeitado (multi-role)."""
    only_pastor = _make_user(church_a, 'solo@a.com', ['pastor', 'leader'])

    with schema_context('tenant_a'):
        with pytest.raises(ValidationError):
            # Mesmo mantendo 'leader', remover 'pastor' esvazia a igreja.
            change_roles(user=only_pastor, new_roles=['leader'])

    only_pastor.refresh_from_db()
    assert 'pastor' in only_pastor.roles


@pytest.mark.django_db(transaction=True)
def test_can_remove_pastor_when_another_active_pastor_exists(
    church_a, restore_public_schema
):
    """Com outro Pastor ATIVO, remover 'pastor' de um deles e permitido."""
    p1 = _make_user(church_a, 'p1@a.com', ['pastor'])
    _make_user(church_a, 'p2@a.com', ['pastor'])

    with schema_context('tenant_a'):
        change_roles(user=p1, new_roles=['member'])
    p1.refresh_from_db()
    assert p1.roles == ['member']


@pytest.mark.django_db(transaction=True)
def test_inactive_pastor_does_not_count_as_other_pastor(
    church_a, restore_public_schema
):
    """Pastor INATIVO nao satisfaz a guarda RN-004 (precisa de outro ATIVO)."""
    active_pastor = _make_user(church_a, 'active@a.com', ['pastor'])
    _make_user(church_a, 'inactive@a.com', ['pastor'])
    # Desativa o segundo pastor diretamente (sem passar pela guarda do service).
    User.objects.filter(email='inactive@a.com').update(is_active=False)

    with schema_context('tenant_a'):
        with pytest.raises(ValidationError):
            change_roles(user=active_pastor, new_roles=['member'])


@pytest.mark.django_db(transaction=True)
def test_role_change_audited_and_security_logged(church_a, restore_public_schema):
    """change_roles grava AuditLog(update) + SecurityLog(role_change) no tenant."""
    pastor = _make_user(church_a, 'actor@a.com', ['pastor'])
    member = _make_user(church_a, 'target@a.com', ['member'])

    with schema_context('tenant_a'):
        change_roles(user=member, new_roles=['leader'], actor=pastor)

        audits = AuditLog.objects.filter(
            tenant_id='tenant_a', action='update', object_id=str(member.id)
        )
        assert audits.count() == 1
        assert audits.first().changes == {'roles': [['member'], ['leader']]}
        # actor (autor) registrado em user_id; target no payload do SecurityLog.
        assert audits.first().user_id == pastor.id

        secs = SecurityLog.objects.filter(
            tenant_id='tenant_a', event_type='role_change'
        )
        assert secs.count() == 1
        log = secs.first()
        assert log.user_id == pastor.id
        assert log.payload == {
            'target_user_id': member.id,
            'roles_before': ['member'],
            'roles_after': ['leader'],
        }


# --------------------------------------------------------------------------- #
# deactivate_user / reactivate_user + guarda conservadora RN-004
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
def test_deactivate_user_sets_inactive_and_logs(church_a, restore_public_schema):
    pastor = _make_user(church_a, 'p@a.com', ['pastor'])
    member = _make_user(church_a, 'm@a.com', ['member'])

    with schema_context('tenant_a'):
        deactivate_user(user=member, actor=pastor)
        member.refresh_from_db()
        assert member.is_active is False

        assert (
            SecurityLog.objects.filter(
                tenant_id='tenant_a',
                event_type='user_deactivated',
                user_id=pastor.id,
            ).count()
            == 1
        )
        audit = AuditLog.objects.get(
            tenant_id='tenant_a', action='update', object_id=str(member.id)
        )
        assert audit.changes == {'is_active': [True, False]}


@pytest.mark.django_db(transaction=True)
def test_deactivate_last_pastor_is_blocked(church_a, restore_public_schema):
    """Extensao conservadora de RN-004: nao desativar o ultimo Pastor ativo."""
    only_pastor = _make_user(church_a, 'solo@a.com', ['pastor'])

    with schema_context('tenant_a'):
        with pytest.raises(ValidationError):
            deactivate_user(user=only_pastor)

    only_pastor.refresh_from_db()
    assert only_pastor.is_active is True


@pytest.mark.django_db(transaction=True)
def test_deactivate_pastor_allowed_when_another_active_pastor(
    church_a, restore_public_schema
):
    p1 = _make_user(church_a, 'p1@a.com', ['pastor'])
    _make_user(church_a, 'p2@a.com', ['pastor'])

    with schema_context('tenant_a'):
        deactivate_user(user=p1)
    p1.refresh_from_db()
    assert p1.is_active is False


@pytest.mark.django_db(transaction=True)
def test_reactivate_user_logs(church_a, restore_public_schema):
    member = _make_user(church_a, 'm@a.com', ['member'])
    User.objects.filter(id=member.id).update(is_active=False)
    member.refresh_from_db()

    with schema_context('tenant_a'):
        reactivate_user(user=member)
        member.refresh_from_db()
        assert member.is_active is True

        assert (
            SecurityLog.objects.filter(
                tenant_id='tenant_a', event_type='user_reactivated'
            ).count()
            == 1
        )
        audit = AuditLog.objects.get(
            tenant_id='tenant_a', action='update', object_id=str(member.id)
        )
        assert audit.changes == {'is_active': [False, True]}


@pytest.mark.django_db(transaction=True)
def test_deactivate_blocks_login(church_a, restore_public_schema):
    """Apos deactivate_user, o login do usuario falha (is_active=False)."""
    from django.test import Client

    member = _make_user(church_a, 'blocked@a.com', ['member'])
    with schema_context('tenant_a'):
        deactivate_user(user=member)
    connection.set_schema_to_public()

    client = Client(HTTP_HOST='a.testserver')
    resp = client.post(
        '/contas/login/',
        {'login': 'blocked@a.com', 'password': GOOD_PASSWORD},
    )
    # Login nao autentica usuario inativo: allauth redireciona para a pagina
    # "inactive" (302) e NUNCA estabelece sessao autenticada.
    assert '_auth_user_id' not in client.session
    assert resp.status_code == 302
    assert 'inactive' in resp.url
    connection.set_schema_to_public()
