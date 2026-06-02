"""Sanitizacao de PII para eventos do Sentry (TENANT-07 / TECH_SPEC §12.3).

`before_send(event, hint)` percorre o evento antes do envio e mascara qualquer
email ou telefone brasileiro que tenha escapado para mensagens, excecoes, dados
de request ou `extra`. Isso e a ultima barreira contra vazamento de PII para um
servico externo (RISK-012); combinado com `send_default_pii=False`.

Abordagem (judgment call): mascaramento por REGEX aplicado recursivamente a todo
o dict do evento (strings em qualquer profundidade), em vez de tentar listar
campos especificos. Generico e resiliente: se um email aparece dentro de um
breadcrumb, num frame de stack ou num `extra` arbitrario, ainda e mascarado.
Substituimos pelo placeholder em vez de remover a chave, para nao quebrar a
estrutura do evento nem perder o contexto de que "havia um email aqui".
"""

import re

_EMAIL_MASK = '[email removido]'
_PHONE_MASK = '[telefone removido]'

# Email: padrao usual. Mascara antes do telefone para nao confundir o dominio.
_EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')

# Telefone BR: cobre formatos comuns com/sem DDI (+55), DDD entre parenteses,
# separadores (espaco, ponto, hifen) e o nono digito. Exemplos casados:
# '+55 (11) 91234-5678', '11912345678', '(11) 1234-5678', '1234-5678'.
_PHONE_RE = re.compile(
    r'(?<!\d)'
    r'(?:\+?55[\s.-]?)?'  # DDI opcional
    r'(?:\(?\d{2}\)?[\s.-]?)?'  # DDD opcional
    r'\d{4,5}[\s.-]?\d{4}'  # numero (8 ou 9 digitos)
    r'(?!\d)'
)


def _scrub_text(value):
    """Mascara email e telefone em uma string."""
    value = _EMAIL_RE.sub(_EMAIL_MASK, value)
    value = _PHONE_RE.sub(_PHONE_MASK, value)
    return value


def _scrub(obj):
    """Aplica `_scrub_text` recursivamente a strings dentro de dict/list/tuple."""
    if isinstance(obj, str):
        return _scrub_text(obj)
    if isinstance(obj, dict):
        return {key: _scrub(val) for key, val in obj.items()}
    if isinstance(obj, list):
        return [_scrub(item) for item in obj]
    if isinstance(obj, tuple):
        return tuple(_scrub(item) for item in obj)
    return obj


def before_send(event, hint):
    """Hook do Sentry: devolve o evento com email/telefone mascarados.

    Defensivo (never-raise): se a sanitizacao falhar por um evento com forma
    inesperada, ainda assim devolvemos o evento original — perder telemetria por
    um erro de scrub seria pior do que deixar passar um evento. O grosso do PII
    ja e barrado por `send_default_pii=False`.
    """
    try:
        return _scrub(event)
    except Exception:
        return event
