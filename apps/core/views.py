"""Endpoints de observabilidade (TECH_SPEC §12.1 / RNF-018).

`health` e a sonda de liveness: responde 200 enquanto o processo Django
estiver vivo, sem tocar no banco nem no Redis. `ready` e a sonda de
readiness: verifica Postgres e Redis e responde 200 se ambos estiverem
acessiveis, 503 caso contrario.
"""

import redis
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET


@login_required
def home(request):
    """Home pós-login (`/`): redireciona para o painel do papel (Sprint 6.5/Bloco 2).

    Corrige o gap em que `LOGIN_REDIRECT_URL='/'` caía em 404. Anônimo → login
    (via `@login_required`). Cada papel vai para um painel ao qual TEM acesso (os
    `Dashboard*View` têm gate de papel). Tesoureiro/Membro ainda não têm painel
    próprio (financeiro = Sprint 6.7) → cai na Segurança da conta por ora.
    """
    user = request.user
    if user.has_any_role('pastor'):
        return redirect('dashboard:pastor')
    if user.has_any_role('secretary', 'leader'):
        return redirect('dashboard:leader')
    return redirect('/contas/seguranca/')


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
