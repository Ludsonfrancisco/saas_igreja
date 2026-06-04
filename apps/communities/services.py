"""Service layer de Comunidades (Frente 3 / Bloco 2).

Camada fina (P-ARQ-04). A regra que NÃO pode viver só na view/form é o **limite de
plano** (OPS-04): `create_community` recusa quando a igreja atinge
`Plan.PLAN_LIMITS[church.plan]['max_communities']` (0 = ilimitado). Também barra a
criação quando a igreja não usa comunidades (`has_communities=False`).

AUDITORIA: `Community` herda `AuditLogMixin` → create/update/delete já geram
AuditLog automático (core signals). Edição/exclusão não têm regra de negócio extra,
então passam direto pelas CBVs (form.save / delete); só o create centraliza aqui.
"""

from django.core.exceptions import ValidationError

from apps.communities.models import Community
from apps.tenants.models import Plan


def create_community(
    *,
    church,
    name,
    leaders=None,
    meeting_day=None,
    meeting_time=None,
    is_active=True,
):
    """Cria uma comunidade respeitando `has_communities` e o limite de plano (OPS-04).

    `leaders` é um iterável de `Person` (M2M, OD-019 — pode ter vários). AuditLog
    automático (AuditLogMixin). Retorna a Community criada.
    """
    if not church.has_communities:
        raise ValidationError('Esta igreja nao utiliza comunidades.')

    max_communities = Plan.PLAN_LIMITS.get(church.plan, {}).get('max_communities', 0)
    if max_communities:
        active = Community.objects.filter(is_active=True).count()
        if active >= max_communities:
            raise ValidationError(
                f'Limite do plano atingido: {max_communities} comunidades. '
                'Faca upgrade para criar mais.'
            )

    community = Community.objects.create(
        name=name,
        meeting_day=meeting_day,
        meeting_time=meeting_time,
        is_active=is_active,
    )
    if leaders:
        community.leaders.set(leaders)
    return community
