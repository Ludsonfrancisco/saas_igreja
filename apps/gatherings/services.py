"""Service layer de Encontros (Sprint 4 / Frente 1).

Camada fina (P-ARQ-04), mas concentra a regra que NÃO pode viver só na view/form:
a **permissão de criar por tipo × papel × escopo** (ACCESS_MATRIX §3.6):

- WORSHIP        → só Pastor/Secretário (admin).
- COMMUNITY      → admin OU Líder de uma comunidade (a comunidade escolhida tem de
                   ser uma que ele lidera); exige `Church.has_communities` (RN-010).
- EVENT/MEETING  → admin OU qualquer Líder/Coordenador (papel `leader`).

`created_by` recebe o `user_id` do ator (TENANT-04) — habilita a trava "editar
pelo criador" da §3.6. AuditLog é automático (AuditLogMixin); o service não chama
`record_audit`.
"""

from django.core.exceptions import ValidationError

from apps.communities.models import Community
from apps.gatherings.models import Gathering

ADMIN_ROLES = ('pastor', 'secretary')


def _leads_any_community(user):
    """True se `user` lidera ≥1 comunidade (M2M `Community.leaders` → user_id)."""
    return Community.objects.filter(leaders__user_id=user.id).exists()


def _leads_community(user, community):
    """True se `user` lidera a `community` específica (escopo COMMUNITY)."""
    return community.leaders.filter(user_id=user.id).exists()


def allowed_types(user, church):
    """Tipos de encontro que `user` pode criar nesta igreja (§3.6).

    Usado pelo form (limitar o dropdown) e pelo service (validar). Pastor e
    Secretário são admin (todos os tipos). COMMUNITY depende de `has_communities`.
    """
    is_admin = user.has_any_role(*ADMIN_ROLES)
    types = []
    if is_admin:
        types.append(Gathering.Type.WORSHIP)
    if church.has_communities and (is_admin or _leads_any_community(user)):
        types.append(Gathering.Type.COMMUNITY)
    if is_admin or user.has_any_role('leader'):
        types += [Gathering.Type.EVENT, Gathering.Type.MEETING]
    return types


def create_gathering(
    *, church, user, gathering_type, date, title=None, community=None, description=''
):
    """Cria um encontro aplicando a barreira de tipo×papel×escopo (§3.6).

    `user` é o ator (request.user). Levanta `ValidationError` quando o ator não
    pode criar o tipo pedido, ou quando um tipo COMMUNITY vem sem comunidade
    válida/escopada. Retorna o `Gathering` criado.
    """
    if gathering_type not in allowed_types(user, church):
        raise ValidationError(
            'Voce nao tem permissao para criar este tipo de encontro.'
        )

    if gathering_type == Gathering.Type.COMMUNITY:
        if community is None:
            raise ValidationError('Selecione a comunidade do encontro.')
        if not user.has_any_role(*ADMIN_ROLES) and not _leads_community(
            user, community
        ):
            raise ValidationError(
                'Voce so pode criar encontros de uma comunidade que lidera.'
            )
    else:
        # Só encontros COMMUNITY têm comunidade — os demais ignoram o campo.
        community = None

    return Gathering.objects.create(
        gathering_type=gathering_type,
        title=title or None,
        date=date,
        community=community,
        description=description or '',
        created_by=user.id,
    )
