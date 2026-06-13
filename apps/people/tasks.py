"""Tasks Celery de Pessoas (Frente 2 / Bloco 3).

`purge_anonymized_persons`: purge físico semanal do soft delete LGPD (RN-006).
Roda via Celery Beat (schedule em settings). Itera TODOS os schemas de tenant
(o Person só existe no tenant — o public é excluído) e remove as pessoas
anonimizadas há mais de 30 dias.

O `delete()` dispara `post_delete` → AuditLog('delete') automático (AuditLogMixin)
e zera (SET_NULL) as FKs que apontam para a pessoa (community.leader,
ministry.coordinator, etc.) — preservando o restante da trilha (RN-007).
"""

import csv
import io
import unicodedata
from datetime import timedelta

from celery import shared_task
from django.core.exceptions import ValidationError
from django.utils import timezone
from django_tenants.utils import get_public_schema_name, schema_context

_PURGE_AFTER = timedelta(days=30)
_CONSENT_TRUTHY = {'sim', 'yes', 'true', '1', 's', 'y'}

# Aliases de cabeçalho (pt-BR primário + inglês como compatibilidade). A interface é
# 100% pt-BR, então a planilha usa Nome/E-mail/Telefone/Situação/Consentimento; mas
# arquivos antigos em inglês continuam funcionando.
_HEADER_ALIASES = {
    'name': ('nome', 'name'),
    'email': ('e-mail', 'email'),
    'phone': ('telefone', 'celular', 'fone', 'phone'),
    'status': ('situacao', 'status'),
    'consent': ('consentimento', 'consent'),
}


def _ascii_key(text):
    """minúsculas + sem acento — p/ casar cabeçalho/situação digitados em pt-BR."""
    text = (text or '').strip().lower()
    return ''.join(
        c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn'
    )


@shared_task
def purge_anonymized_persons():
    """Remove Person anonimizada há > 30 dias em todos os tenants. Retorna o total."""
    from apps.people.models import Person
    from apps.tenants.models import Church

    cutoff = timezone.now() - _PURGE_AFTER
    public = get_public_schema_name()
    total = 0
    for church in Church.objects.exclude(schema_name=public):
        with schema_context(church.schema_name):
            stale = Person.objects.filter(
                anonymized_at__isnull=False, anonymized_at__lte=cutoff
            )
            count = stale.count()
            stale.delete()
            total += count
    return total


@shared_task
def import_persons_csv(church_schema, content, import_id):
    """Importa pessoas de um CSV (RF-033). Roda no schema do tenant.

    **Idempotente por `import_id`**: se o lote já foi importado, é no-op (re-rodar
    não duplica). Colunas (pt-BR): `Nome` (obrigatório), `E-mail`, `Telefone`,
    `Situação`, `Consentimento` — também aceita os nomes em inglês (name/email/...).
    A `Situação` aceita o rótulo pt (Membro, Visitante, Congregado, Líder, Inativo)
    ou o código (member/visitor/...). Consentimento (OPS-05/RN-005): linha com
    email/telefone SEM consentimento afirmativo é pulada e reportada (não cria).
    Respeita o limite de plano (OPS-04) via `create_person`. Retorna
    `{status, created, errors}`.
    """
    from apps.people.models import Person
    from apps.people.services import create_person
    from apps.tenants.models import Church

    # Situação: aceita código (member) OU rótulo pt (Membro/Líder...), sem acento.
    status_by_key = {}
    for value, label in Person.Status.choices:
        status_by_key[_ascii_key(value)] = value
        status_by_key[_ascii_key(label)] = value

    def _cell(norm_row, field):
        """Valor da coluna `field` tentando os aliases pt/en (chave sem acento)."""
        for alias in _HEADER_ALIASES[field]:
            value = norm_row.get(_ascii_key(alias))
            if value:
                return value.strip()
        return ''

    with schema_context(church_schema):
        if Person.objects.filter(import_id=import_id).exists():
            return {'status': 'already_imported', 'created': 0, 'errors': []}

        church = Church.objects.get(schema_name=church_schema)
        created = 0
        errors = []
        reader = csv.DictReader(io.StringIO(content))
        # start=2: a linha 1 do arquivo é o cabeçalho.
        for line, row in enumerate(reader, start=2):
            # Normaliza as chaves do cabeçalho (sem acento/minúsculas) p/ casar pt/en.
            norm = {_ascii_key(k): v for k, v in row.items() if k}
            name = _cell(norm, 'name')
            if not name:
                errors.append({'row': line, 'error': 'nome obrigatorio'})
                continue
            email = _cell(norm, 'email') or None
            phone = _cell(norm, 'phone') or None
            consent = _cell(norm, 'consent').lower() in _CONSENT_TRUTHY
            status = status_by_key.get(
                _ascii_key(_cell(norm, 'status')), Person.Status.VISITOR
            )
            try:
                create_person(
                    church=church,
                    name=name,
                    email=email,
                    phone=phone,
                    status=status,
                    consent_given_at=timezone.now() if consent else None,
                    import_id=import_id,
                )
                created += 1
            except ValidationError as exc:
                errors.append({'row': line, 'error': exc.messages[0]})
        return {'status': 'done', 'created': created, 'errors': errors}
