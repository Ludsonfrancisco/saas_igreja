from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'

    def ready(self):
        """Conecta os signals de seguranca da autenticacao (P-ARQ-06).

        Imports tardios DENTRO do ready(): os modulos de signal de Django/allauth/
        axes so podem ser importados com o app registry pronto. Conectamos com
        dispatch_uid para evitar conexao dupla em reload/autoreload.
        """
        from allauth.account.signals import password_reset
        from axes.signals import user_locked_out
        from django.contrib.auth.signals import user_logged_in, user_login_failed

        from apps.accounts import signals

        user_logged_in.connect(
            signals.on_user_logged_in,
            dispatch_uid='accounts.on_user_logged_in',
        )
        user_login_failed.connect(
            signals.on_user_login_failed,
            dispatch_uid='accounts.on_user_login_failed',
        )
        user_locked_out.connect(
            signals.on_user_locked_out,
            dispatch_uid='accounts.on_user_locked_out',
        )
        password_reset.connect(
            signals.on_password_reset,
            dispatch_uid='accounts.on_password_reset',
        )
