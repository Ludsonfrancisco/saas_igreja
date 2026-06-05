"""Service layer de Escalas (Sprint 5 / Frente 1).

Concentra as regras que não podem viver só na view/form (P-ARQ-04):

- `create_schedule` valida que a `person` pertence ao `ministry` (M2M
  `Ministry.members`) e **bloqueia conflito** (mesma pessoa em outro encontro na
  mesma data) — salvo `allow_conflict=True`, usado pela aprovação de exceção
  (Frente 2).
- `detect_conflict` devolve as escalas conflitantes (mesma pessoa, mesma data,
  encontro diferente). `Gathering` só tem `date` (sem hora) → o conflito é por
  data.

AuditLog é automático (Schedule herda `AuditLogMixin`); o service não chama
`record_audit`.
"""

from django.core.exceptions import ValidationError

from apps.schedules.models import Schedule


def detect_conflict(*, person, gathering, exclude_schedule=None):
    """Escalas conflitantes: mesma pessoa, mesma data, em OUTRO encontro.

    Estar escalada duas vezes no MESMO encontro (ministérios distintos) não é
    conflito — a pessoa está no mesmo lugar. Conflito é precisar estar em dois
    encontros diferentes na mesma data. Retorna um queryset (vazio = sem conflito).
    """
    qs = Schedule.objects.filter(person=person, gathering__date=gathering.date).exclude(
        gathering=gathering
    )
    if exclude_schedule is not None:
        qs = qs.exclude(pk=exclude_schedule.pk)
    return qs.select_related('gathering', 'ministry')


def create_schedule(
    *, ministry, person, gathering, role='', notes='', allow_conflict=False
):
    """Cria uma escala validando vínculo ao ministério e bloqueando conflito.

    - `person` precisa pertencer ao `ministry` (M2M `Ministry.members`), senão
      `ValidationError`.
    - Se houver conflito (mesma pessoa/data, outro encontro) e `allow_conflict` for
      `False`, `ValidationError` — o override só vem da aprovação de exceção
      (Frente 2), que chama com `allow_conflict=True`.

    Retorna o `Schedule` criado.
    """
    if not ministry.members.filter(pk=person.pk).exists():
        raise ValidationError(
            'A pessoa precisa pertencer ao ministerio para ser escalada.'
        )

    if (
        not allow_conflict
        and detect_conflict(person=person, gathering=gathering).exists()
    ):
        raise ValidationError(
            'Conflito: a pessoa ja esta escalada em outro encontro nesta data. '
            'Use a aprovacao de excecao para autorizar.'
        )

    return Schedule.objects.create(
        ministry=ministry,
        person=person,
        gathering=gathering,
        role=role or '',
        notes=notes or '',
    )
