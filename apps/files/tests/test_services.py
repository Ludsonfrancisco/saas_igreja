"""Sprint 6 / Bloco 2 — service de upload (validacao MIME real + tamanho + isolamento).

`FileAsset` vive no schema do tenant (TENANT-04): os testes operam dentro de
`schema_context` para alcancar a tabela do tenant. DDL de criar Church exige
`@pytest.mark.django_db(transaction=True)` (rollback transacional nao desfaz DDL).

Bytes minimos validos por tipo (magic bytes) bastam para o libmagic classificar:
  - PDF  : header '%PDF-1.4'
  - PNG  : assinatura b'\\x89PNG\\r\\n\\x1a\\n'
  - JPEG : SOI b'\\xff\\xd8\\xff' + segmento APP0/JFIF
"""

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django_tenants.utils import schema_context

from apps.files import services
from apps.files.models import FileAsset

PDF_BYTES = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< >>\nendobj\n'
# PNG minimo valido: assinatura + chunk IHDR (libmagic exige o IHDR para classificar).
PNG_BYTES = (
    b'\x89PNG\r\n\x1a\n'
    b'\x00\x00\x00\rIHDR'
    b'\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
)
JPEG_BYTES = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01' + b'\x00' * 32
SVG_BYTES = (
    b'<?xml version="1.0"?>\n'
    b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
)


def _upload(content, name, mime='application/octet-stream', uploaded_by_id=1):
    uploaded = SimpleUploadedFile(name, content, content_type=mime)
    return services.upload_file(uploaded_file=uploaded, uploaded_by_id=uploaded_by_id)


@pytest.mark.django_db(transaction=True)
def test_upload_validates_mime_via_magic(church_a):
    """Extensao enganosa nao engana: o tipo real (magic bytes) e que vale."""
    with schema_context(church_a.schema_name):
        # Conteudo nao-PDF com nome .pdf -> rejeitado pelo tipo REAL.
        with pytest.raises(ValidationError):
            _upload(b'isto nao e um pdf de verdade', 'fatura.pdf')

        # PDF/PNG/JPEG reais passam e gravam o MIME detectado.
        pdf = _upload(PDF_BYTES, 'doc.pdf')
        png = _upload(PNG_BYTES, 'foto.png')
        jpg = _upload(JPEG_BYTES, 'foto.jpg')

        assert pdf.mime_type == 'application/pdf'
        assert png.mime_type == 'image/png'
        assert jpg.mime_type == 'image/jpeg'
        assert FileAsset.objects.count() == 3


@pytest.mark.django_db(transaction=True)
def test_upload_rejects_file_above_10mb(church_a):
    """Arquivo acima de 10MB e rejeitado antes de tocar o storage."""
    with schema_context(church_a.schema_name):
        oversized = PDF_BYTES + b'\x00' * (10 * 1024 * 1024 + 1)
        with pytest.raises(ValidationError):
            _upload(oversized, 'grande.pdf')
        assert FileAsset.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_upload_rejects_svg(church_a):
    """SVG e rejeitado explicitamente (vetor de XSS, RISK-005)."""
    with schema_context(church_a.schema_name):
        with pytest.raises(ValidationError):
            _upload(SVG_BYTES, 'logo.svg', mime='image/svg+xml')
        # Mesmo com nome .png disfarcando, o conteudo SVG e barrado.
        with pytest.raises(ValidationError):
            _upload(SVG_BYTES, 'logo.png')
        assert FileAsset.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_r2_path_isolated_per_tenant(church_a, church_b):
    """Upload em A e em B: o caminho do objeto comeca pelo schema do tenant.

    RISK-001 — nenhum vazamento cross-tenant na chave do storage.
    """
    with schema_context(church_a.schema_name):
        asset_a = _upload(PDF_BYTES, 'a.pdf')
        path_a = asset_a.file.name

    with schema_context(church_b.schema_name):
        asset_b = _upload(PDF_BYTES, 'b.pdf')
        path_b = asset_b.file.name

    assert path_a.startswith(f'{church_a.schema_name}/')
    assert path_b.startswith(f'{church_b.schema_name}/')
    assert not path_a.startswith(f'{church_b.schema_name}/')
    assert not path_b.startswith(f'{church_a.schema_name}/')
    assert path_a != path_b
    # storage_path persistido espelha a chave real no storage.
    assert asset_a.storage_path == path_a
    assert asset_b.storage_path == path_b
