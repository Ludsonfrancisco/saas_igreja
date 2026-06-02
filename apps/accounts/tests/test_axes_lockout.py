"""Sprint 2 / Frente 2 — account lockout via django-axes (SEC-02).

5 tentativas falhas -> lockout (15 min de cooloff). O lockout dispara o signal
`axes.signals.user_locked_out`, que grava SecurityLog event_type='lockout' no
schema do tenant.

Isolamento entre testes: o estado do axes vive no schema PUBLIC e NAO e revertido
pelo rollback de testes transaction=True. Limpamos TODAS as tabelas do axes no
setup/teardown e, alem disso, cada teste usa um par (email, IP) PROPRIO — o
lockout e keyed por usuario+IP, entao pares distintos garantem que um lockout
nunca vaze para o teste seguinte mesmo diante de registros residuais de
expiracao/falha.
"""

import pytest
from axes.models import (
    AccessAttempt,
    AccessAttemptExpiration,
    AccessFailureLog,
    AccessLog,
)
from django.db import connection
from django.test import Client
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.core.models import SecurityLog

TENANT_HOST = 'a.testserver'
GOOD_PASSWORD = 'Senha@123'
WRONG_PASSWORD = 'ErradaTotal@9'


def _purge_axes():
    """Apaga TODO o estado do axes (todas as tabelas vivem no schema public)."""
    connection.set_schema_to_public()
    AccessAttempt.objects.all().delete()
    AccessAttemptExpiration.objects.all().delete()
    AccessFailureLog.objects.all().delete()
    AccessLog.objects.all().delete()


@pytest.fixture(autouse=True)
def _clean_axes_state():
    _purge_axes()
    yield
    _purge_axes()


def _client(ip):
    """Client no tenant_a com REMOTE_ADDR fixo (parte da chave de lockout)."""
    return Client(HTTP_HOST=TENANT_HOST, REMOTE_ADDR=ip)


def _make_user(church, email):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=['member'], church=church
    )


def _attempt(client, email, password):
    return client.post('/contas/login/', {'login': email, 'password': password})


@pytest.mark.django_db(transaction=True)
def test_axes_lockout_after_5_failures(church_a, settings):
    assert settings.AXES_FAILURE_LIMIT == 5
    email = 'lock5@a.com'
    _make_user(church_a, email)
    client = _client('198.51.100.10')

    # As 4 primeiras falhas ainda nao bloqueiam.
    for _ in range(4):
        resp = _attempt(client, email, WRONG_PASSWORD)
        assert resp.status_code == 200

    # A 5a falha atinge o limite -> lockout. axes 8 responde 429 (Too Many
    # Requests) por padrao quando bloqueia.
    resp = _attempt(client, email, WRONG_PASSWORD)
    assert resp.status_code == 429
    assert '_auth_user_id' not in client.session


@pytest.mark.django_db(transaction=True)
def test_axes_lockout_logged_in_security_log(church_a):
    email = 'locklog@a.com'
    _make_user(church_a, email)
    client = _client('198.51.100.20')
    for _ in range(5):
        _attempt(client, email, WRONG_PASSWORD)

    connection.set_schema_to_public()
    with schema_context('tenant_a'):
        lockouts = SecurityLog.objects.filter(
            tenant_id='tenant_a', event_type='lockout'
        )
        assert lockouts.count() >= 1
        log = lockouts.first()
        assert log.payload == {'reason': 'axes_failure_limit'}
        # Nao auditamos PII: o evento de lockout nao carrega o email tentado.
        assert 'email' not in log.payload


@pytest.mark.django_db(transaction=True)
def test_axes_cooloff_is_15_minutes(settings):
    from datetime import timedelta

    assert settings.AXES_COOLOFF_TIME == timedelta(minutes=15)
