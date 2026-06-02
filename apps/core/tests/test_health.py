"""Sprint 1 — endpoints de observabilidade (RNF-022 / TECH_SPEC §12.1).

Cobre os testes minimos de healthcheck (SPRINTS Sprint 1):
- /health/ (liveness) responde 200 sem auth e sem tocar no banco.
- /ready/ (readiness) responde 200 com Postgres+Redis ok, 503 se qualquer um
  falhar. As falhas sao simuladas via monkeypatch (sem derrubar PG/Redis reais).
"""

import json

import pytest


def test_health_endpoint_returns_200(client):
    # Liveness nao depende de tenant nem de banco: qualquer Host serve e o
    # TenantMiddleware faz bypass de /health/.
    response = client.get('/health/', HTTP_HOST='monitor.example')

    assert response.status_code == 200
    assert json.loads(response.content) == {'status': 'ok'}


@pytest.mark.django_db
def test_ready_endpoint_returns_200_when_pg_and_redis_ok(client):
    response = client.get('/ready/', HTTP_HOST='monitor.example')

    assert response.status_code == 200
    body = json.loads(response.content)
    assert body['postgres'] == 'ok'
    assert body['redis'] == 'ok'


@pytest.mark.django_db
def test_ready_endpoint_returns_503_when_pg_down(client, monkeypatch):
    # Simula Postgres fora do ar: o cursor da connection levanta excecao.
    # NAO derruba o banco real — apenas o objeto usado pela view.
    def _boom(*args, **kwargs):
        raise Exception('connection refused')

    monkeypatch.setattr('apps.core.views.connection.cursor', _boom)

    response = client.get('/ready/', HTTP_HOST='monitor.example')

    assert response.status_code == 503
    body = json.loads(response.content)
    assert body['postgres'].startswith('fail')
    assert body['redis'] == 'ok'


@pytest.mark.django_db
def test_ready_endpoint_returns_503_when_redis_down(client, monkeypatch):
    # Simula Redis fora do ar: from_url retorna um cliente cujo ping() falha.
    # NAO derruba o Redis real — apenas o caminho usado pela view.
    class _DeadRedis:
        def ping(self):
            raise Exception('redis unreachable')

    monkeypatch.setattr('apps.core.views.redis.from_url', lambda *a, **k: _DeadRedis())

    response = client.get('/ready/', HTTP_HOST='monitor.example')

    assert response.status_code == 503
    body = json.loads(response.content)
    assert body['redis'].startswith('fail')
    assert body['postgres'] == 'ok'
