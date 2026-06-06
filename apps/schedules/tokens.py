"""Token assinado do magic-link do voluntário (Sprint 6.5 / Bloco 5.3 — OD-022).

Stateless: `signing.dumps` carrega `person_id` + `tenant` (schema). O **bind de
tenant** impede que um link de uma igreja resolva no subdomínio de outra mesmo se
os PKs coincidirem (isolamento, RISK-001). TTL via `max_age` na leitura.

Trade-off (documentado): por ser stateless, o link **não é revogável
individualmente** — só rotacionando o salt/SECRET_KEY (invalida todos). Aceitável
para um acesso READ-ONLY de baixa sensibilidade (as próprias escalas do
voluntário, sem conta/senha/MFA — distinto do Membro geral, OD-004).
"""

from django.core import signing

_SALT = 'oikonos.volunteer-schedule'


def make_volunteer_token(*, person_id, tenant):
    """Gera o token assinado para o `person_id` no `tenant` (schema)."""
    return signing.dumps({'pid': person_id, 'tenant': tenant}, salt=_SALT)


def read_volunteer_token(token, *, tenant, max_age):
    """Valida o token e devolve o `person_id`, ou None se inválido/expirado/de
    outro tenant. `max_age` em segundos (SignatureExpired herda de BadSignature)."""
    try:
        data = signing.loads(token, salt=_SALT, max_age=max_age)
    except signing.BadSignature:
        return None
    if not isinstance(data, dict) or data.get('tenant') != tenant:
        return None
    return data.get('pid')
