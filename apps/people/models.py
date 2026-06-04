"""Pessoa — model central da igreja, LGPD-aware (RF-030 / RN-005..007 / TECH_SPEC §5.4).

Vive no schema do TENANT (`apps.people` em TENANT_APPS): NÃO referencia User/Church
por FK — o próprio schema isola a igreja. Relaciona-se a `Community` (FK `SET_NULL`)
e `Ministry` (M2M); por isso este model nasce junto com communities/ministries (as
FKs são mutuamente referenciais — Community.leader e Ministry.coordinator apontam de
volta para Person).

LGPD:
- `consent_given_at` é obrigatório quando `email` ou `phone` está preenchido. A
  barreira EFETIVA é a camada de service (`create_person`/`import_csv`, OPS-05 /
  OD-018, Frente 2); o ModelForm apenas espelha para UX.
- `anonymized_at` registra o instante da anonimização (soft delete imediato +
  substituição de PII). O purge físico semanal (Celery Beat) remove a Person com
  `status=INACTIVE` cujo `anonymized_at` é mais antigo que 30 dias (RN-006).
- FKs de outros models para Person usam `on_delete=SET_NULL` para preservar a
  trilha de auditoria e a presença histórica (RN-007).
"""

from django.db import models

from apps.core.models import BaseModel


class Person(BaseModel):
    """Pessoa vinculada à igreja. LGPD-aware (TECH_SPEC §5.4)."""

    class Status(models.TextChoices):
        VISITOR = 'visitor', 'Visitante'
        CONGREGANT = 'congregant', 'Congregado'
        MEMBER = 'member', 'Membro'
        LEADER = 'leader', 'Lider'
        INACTIVE = 'inactive', 'Inativo'

    name = models.CharField(max_length=120)
    # null=True (não só blank) é deliberado (TECH_SPEC §5.4): para a LGPD, distinguir
    # "PII ausente" (NULL) de valor preenchido torna o gate de consentimento e a
    # anonimização inequívocos. Por isso suprimimos DJ001 nestes dois campos.
    email = models.EmailField(null=True, blank=True)  # noqa: DJ001
    phone = models.CharField(max_length=20, null=True, blank=True)  # noqa: DJ001
    birth_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.VISITOR,
        db_index=True,
    )
    community = models.ForeignKey(
        'communities.Community',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members',
    )
    ministries = models.ManyToManyField(
        'ministries.Ministry',
        blank=True,
        related_name='members',
    )
    consent_given_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Obrigatorio quando email ou telefone esta preenchido (LGPD).',
    )
    # Soft delete LGPD: setado por `anonymize_person` (Frente 2). Alimenta o purge
    # fisico semanal (RN-006). Indexado para a query do job (status + anonymized_at).
    anonymized_at = models.DateTimeField(null=True, blank=True, db_index=True)
    notes = models.TextField(blank=True, default='')

    def __str__(self):
        return self.name
