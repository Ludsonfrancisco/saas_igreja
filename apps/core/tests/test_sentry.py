"""Sprint 2 — before_send: sanitizacao de PII em eventos do Sentry (TENANT-07).

Garante que email e telefone sejam mascarados em qualquer lugar do evento
(message, extra, request data, excecao) antes do envio (RISK-012 / §12.3). Sem
rede: alimentamos um dict de evento e inspecionamos o retorno.
"""

from apps.core.sentry import before_send


def test_before_send_masks_email_in_message_and_extra():
    event = {
        'message': 'Erro ao processar maria@example.com',
        'extra': {'contato': 'joao.silva+tag@igreja.org.br'},
    }

    result = before_send(event, {})

    assert 'maria@example.com' not in result['message']
    assert '[email removido]' in result['message']
    assert 'joao.silva+tag@igreja.org.br' not in result['extra']['contato']
    assert '[email removido]' in result['extra']['contato']


def test_before_send_masks_brazilian_phone():
    event = {
        'message': 'Falha no envio para +55 (11) 91234-5678',
        'extra': {'fone': '11912345678'},
    }

    result = before_send(event, {})

    assert '91234-5678' not in result['message']
    assert '[telefone removido]' in result['message']
    assert '11912345678' not in result['extra']['fone']
    assert '[telefone removido]' in result['extra']['fone']


def test_before_send_scrubs_nested_and_listed_values():
    event = {
        'exception': {
            'values': [
                {'value': 'usuario admin@tenant.com nao encontrado'},
            ]
        },
        'request': {'data': {'emails': ['a@b.com', 'c@d.com']}},
    }

    result = before_send(event, {})

    assert '[email removido]' in result['exception']['values'][0]['value']
    assert result['request']['data']['emails'] == [
        '[email removido]',
        '[email removido]',
    ]


def test_before_send_is_defensive_on_bad_event():
    # Forma inesperada nao deve estourar: devolve algo (never-raise).
    weird = object()
    assert before_send(weird, {}) is weird
