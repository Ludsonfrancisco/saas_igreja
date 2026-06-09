"""Endpoints de observabilidade (TECH_SPEC §12.1 / RNF-018).

`health` e a sonda de liveness: responde 200 enquanto o processo Django
estiver vivo, sem tocar no banco nem no Redis. `ready` e a sonda de
readiness: verifica Postgres e Redis e responde 200 se ambos estiverem
acessiveis, 503 caso contrario.
"""

import redis
from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

# A home pós-login (`/`) virou a Home nova da Sprint 6.6 (`dashboard.views.HomeView`,
# RF-102/103/104) — registrada direto no ROOT_URLCONF. O antigo redirect por papel
# foi removido aqui.


@require_GET
def health(request):
    """Liveness: 200 sempre que o processo estiver vivo (nao toca no banco)."""
    return JsonResponse({'status': 'ok'})


@require_GET
def ready(request):
    """Readiness: verifica Postgres (SELECT 1) e Redis (ping); 200 ou 503."""
    checks = {}
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        checks['postgres'] = 'ok'
    except Exception as exc:
        checks['postgres'] = f'fail: {exc!r}'
    try:
        r = redis.from_url(settings.REDIS_URL, socket_timeout=2)
        r.ping()
        checks['redis'] = 'ok'
    except Exception as exc:
        checks['redis'] = f'fail: {exc!r}'
    healthy = all(v == 'ok' for v in checks.values())
    return JsonResponse(checks, status=200 if healthy else 503)
