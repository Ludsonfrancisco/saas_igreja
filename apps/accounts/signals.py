"""Signals de seguranca da autenticacao (SEC-02 / PRD §15.1 / P-ARQ-06).

Cada evento de auth dispara um `SecurityLog` via `log_security_event(...)`. Os
handlers ficam AQUI e sao conectados em `AccountsConfig.ready()` (nunca em
models.py): assim cobrimos TODOS os caminhos de auth (views do allauth, admin,
shell que passe pela stack de auth), nao so uma view especifica.

Mapeamento evento -> signal:
  - login_success            <- django.contrib.auth.signals.user_logged_in
  - login_failure            <- django.contrib.auth.signals.user_login_failed
  - lockout                  <- axes.signals.user_locked_out
  - password_reset_completed <- allauth.account.signals.password_reset
  - password_reset_requested -> NAO aqui: e disparado no AccountAdapter
    (`send_password_reset_mail`), pois o allauth nao emite signal de "reset
    solicitado". Ver apps/accounts/adapter.py.

Por que `user_logged_in`/`user_login_failed` do Django (e nao do allauth)? Sao os
signals canonicos disparados por QUALQUER backend (incluindo o EmailBackend e o
fluxo do axes), capturando todo login/falha de forma uniforme. O allauth tambem
emite os seus, mas o do Django e o ponto comum mais baixo.

SANITIZACAO (TENANT-07 / §12.3): NUNCA gravamos email/telefone/senha/token crus.
Identificamos o usuario por `user_id` (IntegerField). Em falhas de login, o email
tentado NAO vai para o payload — so um metadado de que houve tentativa. O proprio
`log_security_event` so persiste se o request estiver no schema de um tenant
(guarda de schema public) e nunca levanta excecao.
"""

import logging

from apps.core.audit import log_security_event

logger = logging.getLogger(__name__)


def on_user_logged_in(sender, request, user, **kwargs):
    """SecurityLog 'login_success' (django user_logged_in)."""
    log_security_event(
        event_type='login_success',
        user_id=getattr(user, 'id', None),
        payload={'backend': 'email'},
    )


def on_user_login_failed(sender, credentials, request=None, **kwargs):
    """SecurityLog 'login_failure' (django user_login_failed).

    NAO logamos o email tentado (PII / enumeracao): apenas o fato da falha. O
    `credentials` chega aqui mas e deliberadamente ignorado no payload.
    """
    log_security_event(
        event_type='login_failure',
        user_id=None,
        payload={'backend': 'email'},
    )


def on_user_locked_out(sender, request=None, **kwargs):
    """SecurityLog 'lockout' (axes user_locked_out) — 5 falhas em 15 min."""
    log_security_event(
        event_type='lockout',
        user_id=None,
        payload={'reason': 'axes_failure_limit'},
    )


def on_password_reset(sender, request, user, **kwargs):
    """SecurityLog 'password_reset_completed' (allauth password_reset).

    Disparado quando a senha e EFETIVAMENTE redefinida (token consumido), nao no
    pedido. O pedido e auditado separadamente pelo AccountAdapter.
    """
    log_security_event(
        event_type='password_reset_completed',
        user_id=getattr(user, 'id', None),
        payload={'channel': 'email'},
    )
