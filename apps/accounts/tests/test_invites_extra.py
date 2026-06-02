"""Sprint 2 / Frente 4 — robustez dos services de convite (RN-003a).

Complementa test_invites_services.py com defesas alem do happy path:
- validacao de roles (vazio / inexistente);
- email enviado COM o link de aceite (e o token vai SO no email — TENANT-07);
- barreira cross-tenant no aceite (expected_church);
- hard delete no cancelamento.

Mesma disciplina de schema/transaction/email dos demais arquivos da frente.
"""

import pytest
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import override_settings

from apps.accounts.models import Invite, User
from apps.accounts.services import accept_invite, cancel_invite, create_invite

GOOD_PASSWORD = 'Senha@123'
LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'


@pytest.fixture
def restore_public_schema():
    yield
    connection.set_schema_to_public()


def _make_pastor(church, email='pastor@a.com'):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=['pastor'], church=church
    )


def _noop_url(token):
    return f'https://a.testserver/contas/convite/{token}/'


# --------------------------------------------------------------------------- #
# Validacao de roles
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND=LOCMEM)
def test_create_invite_requires_valid_roles(church_a, restore_public_schema):
    """roles vazio OU papel inexistente -> ValidationError; nada e persistido."""
    pastor = _make_pastor(church_a)

    with pytest.raises(ValidationError):
        create_invite(
            church=church_a,
            email='novo@a.com',
            roles=[],
            invited_by=pastor,
            build_accept_url=_noop_url,
        )

    with pytest.raises(ValidationError):
        create_invite(
            church=church_a,
            email='novo@a.com',
            roles=['xpto'],
            invited_by=pastor,
            build_accept_url=_noop_url,
        )

    # Nenhum convite criado nas tentativas invalidas.
    assert not Invite.objects.filter(email='novo@a.com').exists()


# --------------------------------------------------------------------------- #
# Email com o link de aceite (token SO no email)
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND=LOCMEM)
def test_create_invite_sends_email_with_accept_link(church_a, restore_public_schema):
    """Um email e enviado ao convidado e o corpo contem o link com o token.

    Confirma a invariante TENANT-07: o token (segredo) viaja SO no email — aqui
    via build_accept_url, que embute o token na URL de aceite.
    """
    pastor = _make_pastor(church_a)
    mail.outbox.clear()

    invite = create_invite(
        church=church_a,
        email='convidado@a.com',
        roles=['member'],
        invited_by=pastor,
        build_accept_url=_noop_url,
    )

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ['convidado@a.com']
    # O corpo carrega o link de aceite com o token (unico canal do segredo).
    assert str(invite.token) in message.body
    assert _noop_url(invite.token) in message.body


# --------------------------------------------------------------------------- #
# Token inexistente no aceite
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND=LOCMEM)
def test_accept_invite_unknown_token_is_invalid(church_a, restore_public_schema):
    """Token inexistente -> ValidationError('Convite invalido.') (mensagem generica).

    A mensagem e a mesma de cross-tenant: nao revela se o token existe — defesa
    contra enumeracao de convites.
    """
    import uuid

    # Garante que ha pelo menos um convite real na base (token diferente).
    pastor = _make_pastor(church_a)
    create_invite(
        church=church_a,
        email='real@a.com',
        roles=['member'],
        invited_by=pastor,
        build_accept_url=_noop_url,
    )

    with pytest.raises(ValidationError) as exc:
        accept_invite(
            token=uuid.uuid4(), password=GOOD_PASSWORD, expected_church=church_a
        )
    assert 'invalido' in str(exc.value).lower()


# --------------------------------------------------------------------------- #
# Cross-tenant no aceite
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND=LOCMEM)
def test_accept_invite_rejects_cross_tenant(church_a, church_b, restore_public_schema):
    """Convite de A aceito com expected_church=B -> ValidationError('Convite invalido').

    Barreira cross-tenant (RISK-001): a mensagem e a generica de 'invalido', para
    nao revelar a existencia do token a quem esta no tenant errado.
    """
    pastor = _make_pastor(church_a)
    invite = create_invite(
        church=church_a,
        email='novo@a.com',
        roles=['member'],
        invited_by=pastor,
        build_accept_url=_noop_url,
    )

    with pytest.raises(ValidationError) as exc:
        accept_invite(
            token=invite.token, password=GOOD_PASSWORD, expected_church=church_b
        )
    assert 'invalido' in str(exc.value).lower()

    # Nenhum usuario criado no tenant errado.
    assert not User.objects.filter(email='novo@a.com').exists()


# --------------------------------------------------------------------------- #
# Cancelamento = hard delete
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND=LOCMEM)
def test_cancel_invite_deletes_row(church_a, restore_public_schema):
    """Apos cancel_invite, a linha do convite nao existe mais (hard delete)."""
    pastor = _make_pastor(church_a)
    invite = create_invite(
        church=church_a,
        email='novo@a.com',
        roles=['member'],
        invited_by=pastor,
        build_accept_url=_noop_url,
    )
    pk = invite.pk

    result = cancel_invite(invite=invite, actor=pastor)

    assert result is None
    assert not Invite.objects.filter(pk=pk).exists()
