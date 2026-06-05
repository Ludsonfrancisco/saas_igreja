"""Validacao de upload por conteudo real (magic bytes), nao por extensao.

`MagicValidator` (Sprint 6 / Bloco 2) detecta o MIME REAL do arquivo lendo os
primeiros bytes via `python-magic` (libmagic), ignorando a extensao informada
pelo cliente — um `.pdf` com payload de script e rejeitado, pois o conteudo nao
e PDF. Allowlist conservadora: PDF, PNG, JPEG (RF de upload da Sprint 6).

SVG e rejeitado de forma explicita (image/svg+xml): por ser XML, e vetor de XSS
quando servido inline (RISK-005). Ja cairia fora da allowlist, mas o tratamento
explicito torna a intencao clara e o erro mais informativo.

Mensagens de erro em pt-BR (interface), codigo em ingles (STYLE-01).
"""

import magic
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible

# MIMEs aceitos no upload. Conservador de proposito: so o que a Sprint 6 exige.
ALLOWED_MIME_TYPES = frozenset(
    {
        'application/pdf',
        'image/png',
        'image/jpeg',
    }
)

# Negados de forma explicita para mensagem clara (subconjunto do "fora da
# allowlist"). SVG e o caso critico (XSS / RISK-005).
EXPLICITLY_DENIED_MIME_TYPES = frozenset(
    {
        'image/svg+xml',
    }
)

# libmagic so precisa do cabecalho para classificar; 2KB cobre os tipos da
# allowlist sem carregar o arquivo inteiro em memoria.
_SNIFF_BYTES = 2048


def detect_mime_type(content: bytes) -> str:
    """Retorna o MIME real de `content` lido pelo libmagic (nunca a extensao)."""
    return magic.from_buffer(content[:_SNIFF_BYTES], mime=True)


@deconstructible
class MagicValidator:
    """Valida que o conteudo do arquivo bate com a allowlist de MIME.

    Usavel como `validators=[MagicValidator()]` num FileField ou chamado direto
    no service layer. Le os magic bytes do arquivo (nao a extensao) e levanta
    `ValidationError` (pt-BR) para qualquer tipo fora da allowlist.

    `@deconstructible` torna o validator serializavel em migracoes: quando usado
    com o default, `allowed_mime_types` fica `None` e a migracao nao precisa
    serializar a allowlist (evita depender da ordem de um set).
    """

    def __init__(self, allowed_mime_types=None):
        self._explicit_allowed = allowed_mime_types
        resolved = (
            ALLOWED_MIME_TYPES if allowed_mime_types is None else allowed_mime_types
        )
        self.allowed_mime_types = frozenset(resolved)

    def deconstruct(self):
        path = 'apps.core.validators.MagicValidator'
        if self._explicit_allowed is None:
            return path, [], {}
        return path, [], {'allowed_mime_types': sorted(self._explicit_allowed)}

    def __call__(self, value):
        content = self._read_head(value)
        detected = detect_mime_type(content)

        if detected in EXPLICITLY_DENIED_MIME_TYPES:
            raise ValidationError(
                'Arquivos SVG nao sao permitidos por motivos de seguranca.',
                code='mime_denied',
            )

        if detected not in self.allowed_mime_types:
            raise ValidationError(
                'Tipo de arquivo nao permitido. Envie um PDF, PNG ou JPEG.',
                code='mime_not_allowed',
            )

        return detected

    @staticmethod
    def _read_head(value) -> bytes:
        """Le os primeiros bytes de `value` (bytes, UploadedFile ou file-like).

        Preserva a posicao do ponteiro de leitura para que o service consiga
        persistir o arquivo integro depois da validacao.
        """
        if isinstance(value, (bytes, bytearray)):
            return bytes(value[:_SNIFF_BYTES])

        # Arquivos do Django (UploadedFile/File) e file-like objects.
        if hasattr(value, 'read'):
            pointer = value.tell() if hasattr(value, 'tell') else None
            if hasattr(value, 'seek'):
                value.seek(0)
            head = value.read(_SNIFF_BYTES)
            if hasattr(value, 'seek'):
                value.seek(pointer if pointer is not None else 0)
            if isinstance(head, str):
                head = head.encode('latin-1', errors='ignore')
            return head

        raise ValidationError(
            'Nao foi possivel ler o conteudo do arquivo enviado.',
            code='unreadable',
        )

    def __eq__(self, other):
        return (
            isinstance(other, MagicValidator)
            and self.allowed_mime_types == other.allowed_mime_types
        )

    def __hash__(self):
        return hash(('MagicValidator', self.allowed_mime_types))
