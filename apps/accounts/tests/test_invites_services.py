"""Sprint 2 / Frente 4 — services de convite (RN-003a).

Cobre o ciclo de vida do convite na camada de servico (apps.accounts.services):
create / accept / resend / cancel, mais as invariantes obrigatorias do
SPRINTS.md (P0): unicidade por igreja, single-use do token, expiracao de 7 dias,
renovacao de token no reenvio e criacao de conta no aceite.

Padrao de schema (espelha test_authz_services.py)
-------------------------------------------------
Os models Invite/User vivem no schema PUBLIC (SHARED_APPS), entao os services
operam corretamente mesmo a partir do public. Mas os helpers de auditoria
(record_audit) tem guarda de schema public — so gravam AuditLog quando estamos no
schema de um TENANT. Onde verificamos a trilha, rodamos sob
`schema_context('tenant_a')`. Onde so verificamos o comportamento de negocio,
chamamos o service direto (no public) — e mais barato e cobre o mesmo caminho.

`transaction=True` em todo teste que cria Church: a criacao dispara DDL
(auto_create_schema) que o rollback transacional padrao nao desfaz; o teardown de
church_a/church_b derruba o schema. `restore_public_schema` devolve o search_path
ao public apos qualquer schema_context.

Email: a suite roda sob core.settings.dev (EMAIL_BACKEND=console), que NAO
popula mail.outbox. Os testes que asseguram envio forcam o backend locmem via
@override_settings — assim mail.outbox fica disponivel para assert.
"""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import override_settings
from django.utils import timezone

from apps.accounts.models import Invite, User
from apps.accounts.services import accept_invite, create_invite, resend_invite

GOOD_PASSWORD = 'Senha@123'
LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'


@pytest.fixture
def restore_public_schema():
    """Restaura o search_path para o public apos testes que entram num tenant."""
    yield
    connection.set_schema_to_public()


def _make_pastor(church, email='pastor@a.com'):
    """Pastor que sera o `invited_by` dos convites."""
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=['pastor'], church=church
    )


def _noop_url(token):
    """build_accept_url minimo: o service so precisa de um callable (token)->str."""
    return f'https://a.testserver/contas/convite/{token}/'


# --------------------------------------------------------------------------- #
# 1. test_invite_unique_per_church (P0)
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND=LOCMEM)
def test_invite_unique_per_church(church_a, restore_public_schema):
    """Dois convites para o mesmo (church, email) — o 2o levanta ValidationError.

    A colisao do unique_together('church','email') vira ValidationError amigavel
    (o service traduz o IntegrityError).
    """
    pastor = _make_pastor(church_a)

    create_invite(
        church=church_a,
        email='convidado@a.com',
        roles=['member'],
        invited_by=pastor,
        build_accept_url=_noop_url,
    )

    with pytest.raises(ValidationError):
        create_invite(
            church=church_a,
            email='convidado@a.com',
            roles=['leader'],
            invited_by=pastor,
            build_accept_url=_noop_url,
        )

    # So existe um convite para esse email nessa igreja.
    assert Invite.objects.filter(church=church_a, email='convidado@a.com').count() == 1


@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND=LOCMEM)
def test_invite_same_email_coexists_across_churches(
    church_a, church_b, restore_public_schema
):
    """Bonus: o MESMO email pode ter convite em A e em B (unicidade e por igreja).

    O unique_together inclui church, entao nao ha colisao entre tenants distintos.
    """
    pastor_a = _make_pastor(church_a, email='pastor@a.com')
    pastor_b = _make_pastor(church_b, email='pastor@b.com')

    create_invite(
        church=church_a,
        email='mesmo@email.com',
        roles=['member'],
        invited_by=pastor_a,
        build_accept_url=_noop_url,
    )
    # Nao deve levantar: church diferente.
    create_invite(
        church=church_b,
        email='mesmo@email.com',
        roles=['member'],
        invited_by=pastor_b,
        build_accept_url=_noop_url,
    )

    assert Invite.objects.filter(email='mesmo@email.com').count() == 2


# --------------------------------------------------------------------------- #
# 2. test_accept_invite_creates_user_and_marks_accepted_at (P0)
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND=LOCMEM)
def test_accept_invite_creates_user_and_marks_accepted_at(
    church_a, restore_public_schema
):
    """Apos aceitar: existe User com email/roles/church do convite, accepted_at set.

    Tambem confirma que a senha foi REALMENTE definida — o User autentica com ela
    (check_password), provando que create_user recebeu o password.
    """
    pastor = _make_pastor(church_a)
    invite = create_invite(
        church=church_a,
        email='novo@a.com',
        roles=['leader', 'treasurer'],
        invited_by=pastor,
        build_accept_url=_noop_url,
    )

    user = accept_invite(
        token=invite.token,
        password=GOOD_PASSWORD,
        first_name='Ana',
        last_name='Souza',
        expected_church=church_a,
    )

    assert user.email == 'novo@a.com'
    assert sorted(user.roles) == ['leader', 'treasurer']
    assert user.church_id == church_a.id
    assert user.first_name == 'Ana'
    assert user.last_name == 'Souza'
    # Senha setada: autentica com a senha definida no aceite.
    assert user.check_password(GOOD_PASSWORD) is True

    invite.refresh_from_db()
    assert invite.accepted_at is not None


# --------------------------------------------------------------------------- #
# 3. test_invite_expires_after_7_days (P0)
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND=LOCMEM)
def test_create_invite_sets_expiration_seven_days_ahead(
    church_a, restore_public_schema
):
    """create_invite seta expires_at ~ now + 7 dias (tolerancia de minutos)."""
    pastor = _make_pastor(church_a)
    before = timezone.now()
    invite = create_invite(
        church=church_a,
        email='novo@a.com',
        roles=['member'],
        invited_by=pastor,
        build_accept_url=_noop_url,
    )
    after = timezone.now()

    # A janela esta entre (before+7d) e (after+7d), com folga.
    assert before + timedelta(days=7) - timedelta(minutes=1) <= invite.expires_at
    assert invite.expires_at <= after + timedelta(days=7) + timedelta(minutes=1)


@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND=LOCMEM)
def test_invite_expires_after_7_days(church_a, restore_public_schema):
    """Convite com expires_at no passado -> accept_invite recusa (expirado)."""
    pastor = _make_pastor(church_a)
    invite = create_invite(
        church=church_a,
        email='novo@a.com',
        roles=['member'],
        invited_by=pastor,
        build_accept_url=_noop_url,
    )

    # Força a expiracao para o passado (sem mexer no relogio do sistema).
    Invite.objects.filter(pk=invite.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )

    with pytest.raises(ValidationError) as exc:
        accept_invite(
            token=invite.token, password=GOOD_PASSWORD, expected_church=church_a
        )
    assert 'expirou' in str(exc.value).lower()

    # Nenhum usuario criado a partir de um convite expirado.
    assert not User.objects.filter(email='novo@a.com').exists()


# --------------------------------------------------------------------------- #
# 4. test_invite_token_single_use (P0)
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND=LOCMEM)
def test_invite_token_single_use(church_a, restore_public_schema):
    """Aceitar o mesmo token 2x: a 1a cria o user; a 2a recusa ('ja foi utilizado')."""
    pastor = _make_pastor(church_a)
    invite = create_invite(
        church=church_a,
        email='novo@a.com',
        roles=['member'],
        invited_by=pastor,
        build_accept_url=_noop_url,
    )

    accept_invite(token=invite.token, password=GOOD_PASSWORD, expected_church=church_a)

    with pytest.raises(ValidationError) as exc:
        accept_invite(
            token=invite.token, password=GOOD_PASSWORD, expected_church=church_a
        )
    assert 'utilizado' in str(exc.value).lower()

    # So um usuario foi criado (sem duplicata).
    assert User.objects.filter(email='novo@a.com').count() == 1


# --------------------------------------------------------------------------- #
# 5. test_resend_invite_renews_expiration (P0)
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND=LOCMEM)
def test_resend_invite_renews_expiration(church_a, restore_public_schema):
    """resend_invite aumenta expires_at E TROCA o token (link antigo morre)."""
    pastor = _make_pastor(church_a)
    invite = create_invite(
        church=church_a,
        email='novo@a.com',
        roles=['member'],
        invited_by=pastor,
        build_accept_url=_noop_url,
    )

    # Envelhece o convite para garantir que o novo expires_at sera maior.
    old_expires = timezone.now() - timedelta(days=1)
    Invite.objects.filter(pk=invite.pk).update(expires_at=old_expires)
    invite.refresh_from_db()
    old_token = invite.token

    resend_invite(invite=invite, actor=pastor, build_accept_url=_noop_url)
    invite.refresh_from_db()

    assert invite.expires_at > old_expires  # expiracao renovada (para o futuro)
    assert invite.expires_at > timezone.now()
    assert invite.token != old_token  # token regenerado: link antigo invalidado


@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND=LOCMEM)
def test_resend_accepted_invite_is_rejected(church_a, restore_public_schema):
    """Convite ja aceito nao pode ser reenviado -> ValidationError."""
    pastor = _make_pastor(church_a)
    invite = create_invite(
        church=church_a,
        email='novo@a.com',
        roles=['member'],
        invited_by=pastor,
        build_accept_url=_noop_url,
    )
    accept_invite(token=invite.token, password=GOOD_PASSWORD, expected_church=church_a)
    invite.refresh_from_db()

    with pytest.raises(ValidationError):
        resend_invite(invite=invite, actor=pastor, build_accept_url=_noop_url)
