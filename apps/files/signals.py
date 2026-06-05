"""Signals de auditoria/seguranca de arquivos (Sprint 6 / Bloco 3, P-ARQ-06).

Dois eventos sao tratados aqui:

1. Upload de arquivo sensivel (evento de ORM): `post_save` de `FileAsset` com
   `created=True` emite um `SecurityLog` `sensitive_file_upload`. O `AuditLog` de
   create ja sai automatico (FileAsset herda `AuditLogMixin`, receivers globais do
   core) — aqui acrescentamos APENAS a camada de SecurityLog (auditoria reforcada
   `📝` da ACCESS_MATRIX §3.8). Modelo identico ao
   `schedules.on_conflict_approval_created`.

2. Download de arquivo sensivel (NAO e evento de ORM — ler nao dispara `post_save`):
   a VIEW de download envia o `Signal` custom `file_downloaded`; o receiver grava o
   par auditoria + seguranca do download:
     - `record_audit(action='read', ...)`  -> AuditLog de leitura (LGPD); o mixin
       so cobre create/update/delete, entao o 'read' do download e explicito aqui.
     - `log_security_event('sensitive_file_download', ...)` -> SecurityLog `📝`.

Delete de `FileAsset` ja gera AuditLog `delete` pelo mixin global — nao duplicamos.

Tudo conectado em `FilesConfig.ready()` com `dispatch_uid` (nunca em models.py).
`user_id` = ator competente (TENANT-04, IntegerField do User publico). Sem PII no
payload (TENANT-07): so ids/metadados, nunca o conteudo nem dados pessoais.
"""

from django.dispatch import Signal

from apps.core.audit import log_security_event, record_audit

# Sinal custom de download: a view o dispara apos servir os bytes com sucesso.
# Args esperados no `send`: sender (a view), file_asset (FileAsset), user_id (int).
file_downloaded = Signal()


def _upload_payload(instance):
    """Metadados nao-sensiveis do upload para o SecurityLog (TENANT-07)."""
    return {
        'file_id': instance.pk,
        'mime_type': instance.mime_type,
        'size_bytes': instance.size_bytes,
        'related_model': instance.related_model,
        'related_object_id': instance.related_object_id,
    }


def on_file_asset_created(sender, instance, created, **kwargs):
    """SecurityLog 'sensitive_file_upload' ao persistir um novo FileAsset."""
    if not created:
        return
    log_security_event(
        event_type='sensitive_file_upload',
        user_id=instance.uploaded_by_id,
        payload=_upload_payload(instance),
    )


def on_file_downloaded(sender, file_asset, user_id=None, **kwargs):
    """AuditLog 'read' + SecurityLog 'sensitive_file_download' de um download.

    O download nao e operacao de ORM (ler nao dispara post_save); por isso a
    auditoria de leitura e explicita aqui, disparada pela view via `file_downloaded`.
    """
    record_audit(action='read', instance=file_asset, user_id=user_id)
    log_security_event(
        event_type='sensitive_file_download',
        user_id=user_id,
        payload={
            'file_id': file_asset.pk,
            'mime_type': file_asset.mime_type,
            'size_bytes': file_asset.size_bytes,
        },
    )
