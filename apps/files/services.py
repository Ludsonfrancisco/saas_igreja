"""Service layer de upload de arquivos (Sprint 6 / Bloco 2, P-ARQ-04).

`upload_file` concentra as regras de upload que nao podem viver so na view/form:
ordem de validacao (tamanho -> MIME real) antes de tocar o storage, e a
montagem dos metadados do `FileAsset`. Mantido leve: uma funcao, sem efeitos
colaterais alem de persistir o `FileAsset` no `STORAGES['default']`.

Validacao em ordem (falha cedo, barato antes de caro):
  1. Tamanho <= 10MB — rejeita antes de ler conteudo/escrever no storage.
  2. MIME real via `MagicValidator` (magic bytes, nao extensao).
  3. Persiste o `FileAsset`; o FileField grava o binario no storage.

Auditoria NAO e chamada aqui (P-ARQ-06): `FileAsset` herda `AuditLogMixin`, entao
o AuditLog de create sai automatico via signals globais do core. SecurityLog de
upload sensivel e Bloco 3 — fora de escopo aqui.

Mensagens de erro em pt-BR; `ValidationError` em qualquer violacao (STYLE-01).
"""

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

from apps.core.storage import sanitize_filename
from apps.core.validators import MagicValidator
from apps.files.models import FileAsset

# RNF de upload (Sprint 6): teto de 10MB por arquivo.
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024


def _resolve_size(uploaded_file, content: bytes) -> int:
    """Tamanho em bytes do arquivo (campo `.size` quando existir; senao len)."""
    size = getattr(uploaded_file, 'size', None)
    if size is None:
        return len(content)
    return size


def _read_content(uploaded_file) -> bytes:
    """Le o conteudo completo como bytes, preservando o ponteiro para o save."""
    if isinstance(uploaded_file, (bytes, bytearray)):
        return bytes(uploaded_file)

    if hasattr(uploaded_file, 'read'):
        if hasattr(uploaded_file, 'seek'):
            uploaded_file.seek(0)
        content = uploaded_file.read()
        if hasattr(uploaded_file, 'seek'):
            uploaded_file.seek(0)
        if isinstance(content, str):
            content = content.encode('latin-1', errors='ignore')
        return content

    raise ValidationError(
        'Nao foi possivel ler o conteudo do arquivo enviado.',
        code='unreadable',
    )


def upload_file(
    *,
    uploaded_file,
    uploaded_by_id,
    original_filename=None,
    related_model='',
    related_object_id='',
):
    """Valida e persiste um arquivo como `FileAsset` no storage padrao.

    Args:
        uploaded_file: `UploadedFile`/file-like/bytes com o conteudo enviado.
        uploaded_by_id: `User.id` (schema public) de quem enviou (TENANT-04).
        original_filename: nome original; derivado de `uploaded_file.name` se
            ausente.
        related_model / related_object_id: contexto opcional (Pessoa/Comunidade/
            Ministerio) para filtro futuro (Bloco 4). Strings, nao FKs.

    Returns:
        O `FileAsset` persistido.

    Raises:
        ValidationError (pt-BR): tamanho acima do limite, MIME fora da allowlist
            (inclui SVG), ou conteudo ilegivel.
    """
    content = _read_content(uploaded_file)
    size_bytes = _resolve_size(uploaded_file, content)

    if size_bytes > MAX_UPLOAD_SIZE_BYTES:
        raise ValidationError(
            'Arquivo muito grande. O tamanho maximo permitido e de 10MB.',
            code='too_large',
        )

    # MIME real pelo conteudo (magic bytes), nao pela extensao. Retorna o tipo
    # detectado para gravar nos metadados.
    mime_type = MagicValidator()(uploaded_file)

    raw_name = original_filename or getattr(uploaded_file, 'name', '') or 'arquivo'
    safe_name = sanitize_filename(raw_name)

    file_asset = FileAsset(
        filename=safe_name,
        mime_type=mime_type,
        size_bytes=size_bytes,
        uploaded_by_id=uploaded_by_id,
        related_model=related_model,
        related_object_id=related_object_id,
    )

    # Garante um UploadedFile (o FileField espera name + conteudo). Se vier bytes
    # crus, embrulha para o storage gravar com nome sanitizado.
    if isinstance(uploaded_file, (bytes, bytearray)):
        from io import BytesIO

        from django.core.files.base import File

        file_to_save = File(BytesIO(content), name=safe_name)
    else:
        if hasattr(uploaded_file, 'seek'):
            uploaded_file.seek(0)
        file_to_save = uploaded_file

    # Grava o binario no storage (caminho isolado por tenant via upload_to) e
    # persiste o FileAsset numa unica chamada de save.
    file_asset.file.save(safe_name, file_to_save, save=False)
    file_asset.storage_path = file_asset.file.name
    file_asset.save()

    return file_asset


# Reexport para callers que importem o tipo Django padrao de arquivo enviado.
__all__ = ['upload_file', 'MAX_UPLOAD_SIZE_BYTES', 'UploadedFile']
