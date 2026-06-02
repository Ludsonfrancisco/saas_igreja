"""Adapter customizado do django-allauth (SEC-02 / PRD §15.1 / §15.2).

Duas responsabilidades nesta frente (Autenticacao):

1. Fechar o cadastro aberto: usuarios entram SOMENTE via Invite (Frente 4). O
   allauth nao deve expor signup publico. `is_open_for_signup` -> False bloqueia
   a view de signup (retorna 403/redirect, conforme a config do allauth).

2. Disparar o SecurityLog `password_reset_requested` no momento exato em que o
   reset e solicitado para um usuario EXISTENTE. O allauth so chama
   `send_password_reset_mail` quando ha usuario com aquele email — exatamente o
   ponto onde temos um `user.id` para atribuir o evento. Para email inexistente o
   allauth NAO chama este metodo (e nao envia email), preservando a ausencia de
   enumeracao (mesma resposta/mensagem para existente/inexistente). Logamos pelo
   adapter (e nao por signal) porque o allauth nao emite um signal de "reset
   solicitado" — apenas de "reset concluido" (`password_reset`).

O log so persiste se o request estiver no schema de um tenant (o helper
`log_security_event` tem guarda de schema public e nunca levanta).
"""

from allauth.account.adapter import DefaultAccountAdapter

from apps.core.audit import log_security_event


class AccountAdapter(DefaultAccountAdapter):
    """Cadastro fechado + auditoria do pedido de reset de senha."""

    def is_open_for_signup(self, request):
        """Desabilita o cadastro aberto: entrada apenas via Invite (Frente 4)."""
        return False

    def send_password_reset_mail(self, user, email, context):
        """Audita o pedido de reset (usuario existente) e segue o fluxo padrao.

        Chamado pelo allauth apenas quando existe um usuario com o email
        informado. Payload SANITIZADO: nunca o email/token cru — apenas o
        identificador `user_id` (IntegerField) vai no SecurityLog; aqui passamos
        so um metadado de canal.
        """
        log_security_event(
            event_type='password_reset_requested',
            user_id=getattr(user, 'id', None),
            payload={'channel': 'email'},
        )
        return super().send_password_reset_mail(user, email, context)
