"""Metadados de arquivos (Sprint 6 / Bloco 2). Arquivo real vive no storage.

`FileAsset` e model de TENANT (vive no schema do tenant via TENANT_APPS): cada
igreja so enxerga seus proprios arquivos. O binario fica no `STORAGES['default']`
(FileSystemStorage em dev, Cloudflare R2 em prod) — aqui guardamos apenas os
metadados + o ponteiro logico.

TENANT-04: nenhuma FK para `User`. Quem fez o upload e `uploaded_by_id`
(IntegerField puro com o `User.id` do schema public), nunca uma FK cross-schema.

Vinculo de contexto (Pessoa / Comunidade / Ministerio) segue a TECH_SPEC §5.8:
campos string `related_model` + `related_object_id`, e nao FKs nem
GenericForeignKey. Isso evita FKs cross-model frageis e mantem o filtro futuro
(Bloco 4) desacoplado dos models de dominio — o app `files` nao precisa importar
people/communities/ministries. Como sao strings, RN-007 (anonimizacao de Person)
nao deixa FK pendente.
"""

from django.conf import settings
from django.db import models

from apps.core.models import AuditLogMixin, BaseModel
from apps.core.storage import tenant_upload_path
from apps.core.validators import MagicValidator


class FileAsset(AuditLogMixin, BaseModel):
    """Metadados de arquivo. O binario real fica no storage configurado."""

    file = models.FileField(
        upload_to=tenant_upload_path,
        max_length=500,
        validators=[MagicValidator()],
        verbose_name='arquivo',
    )
    filename = models.CharField(max_length=255, verbose_name='nome original')
    mime_type = models.CharField(max_length=80, verbose_name='tipo MIME detectado')
    size_bytes = models.PositiveIntegerField(verbose_name='tamanho em bytes')
    storage_path = models.CharField(
        max_length=500,
        blank=True,
        default='',
        verbose_name='caminho no storage',
    )
    # TENANT-04: id do User publico que enviou; NUNCA FK cross-schema.
    uploaded_by_id = models.IntegerField(
        null=True,
        help_text=f'{settings.AUTH_USER_MODEL}.id no schema public',
        verbose_name='enviado por',
    )
    # Vinculo de contexto desacoplado (TECH_SPEC §5.8). Strings, nao FKs.
    related_model = models.CharField(
        max_length=80,
        blank=True,
        default='',
        verbose_name='model relacionado',
    )
    related_object_id = models.CharField(
        max_length=40,
        blank=True,
        default='',
        verbose_name='id do objeto relacionado',
    )

    class Meta(BaseModel.Meta):
        verbose_name = 'arquivo'
        verbose_name_plural = 'arquivos'
        indexes = [
            models.Index(fields=['related_model', 'related_object_id']),
        ]

    def __str__(self):
        return self.filename
