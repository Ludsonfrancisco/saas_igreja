"""Sprint 6 / Bloco 2 — MagicValidator (deteccao de MIME por conteudo real).

Testes puros (sem banco/tenant): o validator so depende do libmagic e dos bytes.
Cobre a allowlist (PDF/PNG/JPEG), a recusa explicita de SVG (RISK-005) e a
imunidade a extensoes enganosas.
"""

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.core.validators import MagicValidator, detect_mime_type

PDF_BYTES = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n'
# PNG minimo valido: assinatura + chunk IHDR (libmagic exige o IHDR para classificar).
PNG_BYTES = (
    b'\x89PNG\r\n\x1a\n'
    b'\x00\x00\x00\rIHDR'
    b'\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
)
JPEG_BYTES = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01' + b'\x00' * 16
SVG_BYTES = b'<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg"></svg>'


def test_detect_mime_type_reads_content_not_extension():
    assert detect_mime_type(PDF_BYTES) == 'application/pdf'
    assert detect_mime_type(PNG_BYTES) == 'image/png'
    assert detect_mime_type(JPEG_BYTES) == 'image/jpeg'


@pytest.mark.parametrize(
    'content,expected',
    [
        (PDF_BYTES, 'application/pdf'),
        (PNG_BYTES, 'image/png'),
        (JPEG_BYTES, 'image/jpeg'),
    ],
)
def test_validator_accepts_allowed_types(content, expected):
    assert MagicValidator()(content) == expected


def test_validator_rejects_svg():
    with pytest.raises(ValidationError) as exc:
        MagicValidator()(SVG_BYTES)
    assert exc.value.code == 'mime_denied'


def test_validator_rejects_type_outside_allowlist():
    with pytest.raises(ValidationError) as exc:
        MagicValidator()(b'plain text content, not a pdf')
    assert exc.value.code == 'mime_not_allowed'


def test_validator_ignores_misleading_extension():
    fake_pdf = SimpleUploadedFile('doc.pdf', PNG_BYTES, content_type='application/pdf')
    # Conteudo PNG com nome .pdf: detecta PNG (esta na allowlist) e devolve o real.
    assert MagicValidator()(fake_pdf) == 'image/png'


def test_validator_preserves_file_pointer():
    uploaded = SimpleUploadedFile('doc.pdf', PDF_BYTES, content_type='application/pdf')
    MagicValidator()(uploaded)
    # Service precisa reler o arquivo integro apos validar.
    uploaded.seek(0)
    assert uploaded.read() == PDF_BYTES


def test_validator_is_deconstructible_for_migrations():
    path, args, kwargs = MagicValidator().deconstruct()
    assert path == 'apps.core.validators.MagicValidator'
    assert list(args) == []
    assert kwargs == {}
