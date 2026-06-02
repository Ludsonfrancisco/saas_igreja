from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'

    def ready(self):
        # Conecta os receivers de auditoria (P-ARQ-06: signals no ready(),
        # nunca em models.py). O import tem o efeito colateral de registrar
        # os @receiver de post_save/post_delete.
        from apps.core import signals  # noqa: F401
