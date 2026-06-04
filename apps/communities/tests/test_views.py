"""Sprint 3 / Frente 3 (Bloco 2) — views CRUD de Comunidade (ACCESS_MATRIX §3.4).

Cobre: barreira de papel (Criar/Excluir só Pastor; Listar Pastor+Líder; Editar
Líder escopado), módulo escondido quando `has_communities=False` (404), auditoria
de edição, e a trava "Líder não define líderes" (campo some no form).
"""

import pytest
from django.db import connection
from django.test import Client
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.communities.models import Community
from apps.core.models import AuditLog
from apps.people.models import Person

GOOD_PASSWORD = 'Senha@123'
LIST_URL = '/comunidades/'
CREATE_URL = '/comunidades/nova/'


@pytest.fixture
def tenant_client():
    client = Client(HTTP_HOST='a.testserver')
    yield client
    connection.set_schema_to_public()


def _make_user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


def _make_community(church, name, leaders=None):
    with schema_context(church.schema_name):
        community = Community.objects.create(name=name)
        if leaders:
            community.leaders.add(*leaders)
        return community


# --- Barreira de papel -------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    'roles,expected', [(['pastor'], 200), (['leader'], 200), (['member'], 403)]
)
def test_community_list_role_barrier(tenant_client, church_a, roles, expected):
    user = _make_user(church_a, f'{roles[0]}@a.com', roles)
    tenant_client.force_login(user)
    assert tenant_client.get(LIST_URL).status_code == expected


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    'roles,expected', [(['pastor'], 200), (['leader'], 403), (['member'], 403)]
)
def test_community_create_pastor_only(tenant_client, church_a, roles, expected):
    user = _make_user(church_a, f'{roles[0]}@a.com', roles)
    tenant_client.force_login(user)
    assert tenant_client.get(CREATE_URL).status_code == expected


@pytest.mark.django_db(transaction=True)
def test_community_create_via_view(tenant_client, church_a):
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    tenant_client.force_login(pastor)

    resp = tenant_client.post(CREATE_URL, {'name': 'Celula Nova', 'is_active': 'on'})
    assert resp.status_code == 302
    with schema_context(church_a.schema_name):
        assert Community.objects.filter(name='Celula Nova').exists()


# --- Módulo escondido quando has_communities=False ---------------------------


@pytest.mark.django_db(transaction=True)
def test_community_module_hidden_when_has_communities_false(tenant_client, church_a):
    church_a.has_communities = False
    church_a.save()
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    tenant_client.force_login(pastor)

    assert tenant_client.get(LIST_URL).status_code == 404
    assert tenant_client.get(CREATE_URL).status_code == 404


# --- Auditoria de edição -----------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_community_update_audited(tenant_client, church_a):
    community = _make_community(church_a, 'Antiga')
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    tenant_client.force_login(pastor)

    resp = tenant_client.post(
        f'/comunidades/{community.pk}/editar/', {'name': 'Renomeada', 'is_active': 'on'}
    )
    assert resp.status_code == 302

    with schema_context(church_a.schema_name):
        community.refresh_from_db()
        assert community.name == 'Renomeada'
        assert AuditLog.objects.filter(
            model_name='Community', action='update', object_id=str(community.pk)
        ).exists()


# --- Escopo de Líder ---------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_leader_sees_only_own_community_detail(tenant_client, church_a):
    leader_user = _make_user(church_a, 'leader@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        leader_person = Person.objects.create(name='Lider', user_id=leader_user.id)
        mine = Community.objects.create(name='Minha')
        mine.leaders.add(leader_person)
        other = Community.objects.create(name='Outra')

    tenant_client.force_login(leader_user)
    assert tenant_client.get(f'/comunidades/{mine.pk}/').status_code == 200
    assert tenant_client.get(f'/comunidades/{other.pk}/').status_code == 404


@pytest.mark.django_db(transaction=True)
def test_leader_edit_form_has_no_leaders_field(tenant_client, church_a):
    """Definir líderes é só do Pastor: o Líder não vê o campo ao editar a sua."""
    leader_user = _make_user(church_a, 'leader@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        leader_person = Person.objects.create(name='Lider', user_id=leader_user.id)
        mine = Community.objects.create(name='Minha')
        mine.leaders.add(leader_person)

    tenant_client.force_login(leader_user)
    resp = tenant_client.get(f'/comunidades/{mine.pk}/editar/')
    assert resp.status_code == 200
    assert 'leaders' not in resp.context['form'].fields


# --- Exclusão (só Pastor) ----------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_community_delete_pastor_only(tenant_client, church_a):
    community = _make_community(church_a, 'Alvo')
    leader = _make_user(church_a, 'leader@a.com', ['leader'])
    tenant_client.force_login(leader)
    assert tenant_client.get(f'/comunidades/{community.pk}/excluir/').status_code == 403

    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    tenant_client.force_login(pastor)
    resp = tenant_client.post(f'/comunidades/{community.pk}/excluir/')
    assert resp.status_code == 302
    with schema_context(church_a.schema_name):
        assert not Community.objects.filter(pk=community.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_community_create_via_view_blocked_by_plan_limit(
    tenant_client, church_a, monkeypatch
):
    """Form válido, mas o SERVICE recusa pelo limite de plano -> 200, nada criado."""
    from apps.tenants.models import Plan

    monkeypatch.setitem(Plan.PLAN_LIMITS['free'], 'max_communities', 1)
    _make_community(church_a, 'Existente')
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    tenant_client.force_login(pastor)

    resp = tenant_client.post(CREATE_URL, {'name': 'Nova', 'is_active': 'on'})
    assert resp.status_code == 200
    with schema_context(church_a.schema_name):
        assert not Community.objects.filter(name='Nova').exists()


@pytest.mark.django_db(transaction=True)
def test_secretary_creates_but_cannot_delete_community(tenant_client, church_a):
    """OD-019: Secretário cria/edita comunidade, mas não exclui (só Pastor)."""
    secretary = _make_user(church_a, 'sec@a.com', ['secretary'])
    community = _make_community(church_a, 'Alvo')
    tenant_client.force_login(secretary)

    assert tenant_client.get(CREATE_URL).status_code == 200
    assert tenant_client.get(f'/comunidades/{community.pk}/excluir/').status_code == 403
