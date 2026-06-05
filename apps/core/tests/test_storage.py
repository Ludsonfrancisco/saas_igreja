"""Sprint 6 / Bloco 1 — esquema de caminho de upload por tenant.

Cobre `apps.core.storage`: o callable `tenant_upload_path` (usado pelo
`FileAsset.upload_to` no Bloco 2) e o sanitizador de nome de arquivo. Foco em
duas garantias criticas:
  - isolamento por tenant: o caminho carrega o `connection.schema_name`, entao
    o mesmo objeto em schemas diferentes gera chaves distintas (RISK-001 /
    RISK-005 / RN-013).
  - seguranca do nome: sem path traversal (RISK-005).

Funcao pura: nao toca storage real (FileSystemStorage em dev/teste, R2 so em
prod), so calcula a string do caminho.
"""

from django_tenants.utils import schema_context

from apps.core.storage import sanitize_filename, tenant_upload_path


class FileAsset:
    """Stand-in do FileAsset (Bloco 2): so precisa de __class__.__name__ e pk."""

    def __init__(self, pk=None):
        self.pk = pk


def test_sanitize_filename_strips_path_components():
    # Path traversal e separadores (POSIX e Windows) nao escapam do diretorio.
    assert sanitize_filename('../../etc/passwd') == 'passwd'
    assert sanitize_filename('a/b/c.txt') == 'c.txt'
    assert sanitize_filename('a\\b\\c.txt') == 'c.txt'
    assert sanitize_filename('/abs/path/file.pdf') == 'file.pdf'


def test_sanitize_filename_replaces_unsafe_chars():
    assert sanitize_filename('relatório financeiro.pdf') == 'relat_rio_financeiro.pdf'
    assert sanitize_filename('a b;c&d.png') == 'a_b_c_d.png'


def test_sanitize_filename_handles_empty_and_dot_names():
    assert sanitize_filename('') == 'arquivo'
    assert sanitize_filename('.') == 'arquivo'
    assert sanitize_filename('..') == 'arquivo'
    # Nome oculto perde o ponto de borda (nao queremos chaves ocultas).
    assert sanitize_filename('.htaccess') == 'htaccess'


def test_upload_path_format_with_pk():
    obj = FileAsset(pk=42)
    # Fora de qualquer tenant resolvido, o schema corrente e 'public'.
    path = tenant_upload_path(obj, 'foto.png')
    assert path == 'public/fileasset/42/foto.png'


def test_upload_path_uses_tmp_before_pk():
    obj = FileAsset(pk=None)
    path = tenant_upload_path(obj, 'doc.pdf')
    assert path == 'public/fileasset/tmp/doc.pdf'


def test_upload_path_sanitizes_filename():
    obj = FileAsset(pk=7)
    path = tenant_upload_path(obj, '../../../escape.pdf')
    assert path == 'public/fileasset/7/escape.pdf'


def test_upload_path_isolated_per_tenant(db):
    """Mesmo objeto em schemas distintos -> chaves distintas (no cross-tenant)."""
    obj = FileAsset(pk=1)

    with schema_context('public'):
        public_path = tenant_upload_path(obj, 'x.png')

    # schema_context aceita um schema arbitrario para fins de resolucao do
    # connection.schema_name; nao precisamos criar o tenant fisico para validar
    # que o prefixo do caminho acompanha o schema corrente.
    with schema_context('tenant_a'):
        path_a = tenant_upload_path(obj, 'x.png')
    with schema_context('tenant_b'):
        path_b = tenant_upload_path(obj, 'x.png')

    assert public_path == 'public/fileasset/1/x.png'
    assert path_a == 'tenant_a/fileasset/1/x.png'
    assert path_b == 'tenant_b/fileasset/1/x.png'
    assert path_a != path_b
