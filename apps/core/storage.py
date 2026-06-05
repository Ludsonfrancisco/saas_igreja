"""Esquema de caminho de upload por tenant (schema-per-tenant).

Gera o caminho `{tenant_schema}/{model}/{object_id}/{filename}` exigido pela
TECH_SPEC §20.1 e SPRINTS Sprint 6 (Storage). O `tenant_schema` vem de
`django.db.connection.schema_name` (injetado pelo django-tenants via
TenantMiddleware), garantindo que arquivos de tenants distintos nunca colidam
no bucket compartilhado — defesa de isolamento cross-tenant (RISK-001 / RISK-005,
RN-013, RNF-018).

Backend de storage (Bloco 1):
  - dev/teste : FileSystemStorage local (MEDIA_ROOT), sem dependencia de R2 real.
  - prod      : Cloudflare R2 (S3) via django-storages (OD-003a / OD-007).
A escolha do BACKEND vive em settings (STORAGES['default']); ESTE modulo so
calcula o CAMINHO logico do objeto, identico nos dois backends.

Este callable sera usado pelo `FileAsset.upload_to` no Bloco 2 — aqui ele e
mantido puro e testavel (recebe `instance` + `filename`), sem criar o model.
"""

import posixpath
import re

from django.db import connection

# Caracteres aceitos no nome do arquivo apos sanitizacao. Tudo fora disso vira
# '_'. Conservador de proposito: barra path traversal ('/', '\\', '..') e
# qualquer separador/byte de controle (RISK-005).
_SAFE_FILENAME_RE = re.compile(r'[^A-Za-z0-9._-]+')
_MAX_FILENAME_LEN = 255


def sanitize_filename(filename: str) -> str:
    """Reduz `filename` ao basename e remove qualquer componente de caminho.

    Evita path traversal (`../`, caminhos absolutos, separadores Windows) e
    nomes vazios/ocultos. Sempre retorna um nome nao-vazio e seguro para compor
    a chave do objeto no storage.
    """
    # Normaliza separadores Windows e fica so com o ultimo componente: nem
    # 'a/b.txt', 'a\\b.txt', nem '../../etc/passwd' escapam do diretorio do
    # objeto. posixpath.basename apos a troca de '\\' cobre os dois mundos.
    base = posixpath.basename(filename.replace('\\', '/')).strip()

    # '..' e '.' nao sao nomes de arquivo validos; trata como vazio.
    if base in ('', '.', '..'):
        return 'arquivo'

    safe = _SAFE_FILENAME_RE.sub('_', base)
    # Remove pontos/underscores/hifens de borda que possam ter sobrado (ex.:
    # '.htaccess' -> 'htaccess'; nomes ocultos nao sao desejaveis na chave).
    safe = safe.strip('._-')
    if not safe:
        return 'arquivo'

    return safe[:_MAX_FILENAME_LEN]


def tenant_upload_path(instance, filename: str) -> str:
    """`upload_to` callable: caminho do objeto no storage, isolado por tenant.

    Formato: `{tenant_schema}/{model}/{object_id}/{filename}` (TECH_SPEC §20.1).

    - `tenant_schema`: `connection.schema_name` (django-tenants). No schema
      `public` resulta em 'public/...' — arquivos de tenant sempre caem sob o
      schema resolvido pelo TenantMiddleware, nunca cruzam tenants (RISK-001).
    - `model`: nome do model em minusculas (ex.: 'fileasset'), derivado do
      `instance` de forma defensiva (funciona mesmo antes do model existir).
    - `object_id`: PK do `instance` quando ja persistido; 'tmp' antes do save
      (o caminho final e recalculado quando o objeto ganha PK).
    - `filename`: sanitizado (sem path traversal).

    Funcao pura para fins de teste: depende apenas de `connection.schema_name`,
    do `instance` e do `filename`.
    """
    schema = connection.schema_name or 'public'

    model_name = instance.__class__.__name__.lower() if instance is not None else 'file'

    object_id = getattr(instance, 'pk', None) if instance is not None else None
    object_segment = str(object_id) if object_id is not None else 'tmp'

    safe_name = sanitize_filename(filename)

    # posixpath garante separador '/' tambem no Windows: chaves S3/R2 usam '/'.
    return posixpath.join(schema, model_name, object_segment, safe_name)
