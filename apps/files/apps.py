from django.apps import AppConfig


class FilesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.files'

    def ready(self):
        """Conecta os signals de auditoria/seguranca de arquivos (P-ARQ-06).

        Import tardio + `dispatch_uid` para evitar conexao dupla no autoreload:
        - `post_save` de `FileAsset` (created) -> SecurityLog de upload sensivel.
        - sinal custom `file_downloaded` (disparado pela view) -> AuditLog 'read'
          + SecurityLog de download sensivel.
        """
        from django.db.models.signals import post_save

        from apps.files import signals
        from apps.files.models import FileAsset

        post_save.connect(
            signals.on_file_asset_created,
            sender=FileAsset,
            dispatch_uid='files.on_file_asset_created',
        )
        signals.file_downloaded.connect(
            signals.on_file_downloaded,
            dispatch_uid='files.on_file_downloaded',
        )
