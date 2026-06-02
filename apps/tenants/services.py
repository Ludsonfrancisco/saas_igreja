"""Service layer de provisionamento de tenants (P-ARQ-04).

`create_church_with_admin` provisiona uma igreja (schema PostgreSQL dedicado),
seu dominio primario e o usuario Pastor inicial. Usado pelo comando de gestao
`create_church` (TECH_SPEC §2 / §4).
"""

from dataclasses import dataclass

from django.contrib.auth import get_user_model

from apps.tenants.models import Church, Domain

PUBLIC_SCHEMA_NAME = 'public'
PUBLIC_DOMAIN = 'localhost'


@dataclass
class ProvisionResult:
    """Resumo do provisionamento, para mensagens do comando."""

    church: Church
    domain: Domain
    pastor_created: bool
    pastor_email: str
    public_bootstrapped: bool


def ensure_public_tenant():
    """Garante que o tenant `public` e seu dominio `localhost` existam.

    O `TenantMiddleware` (TenantMainMiddleware) so consegue servir qualquer
    request se o tenant publico estiver registrado. Idempotente: nao recria se
    ja existir.

    Retorna True se algo foi criado nesta chamada, False caso contrario.
    """
    created = False

    public_church = Church.objects.filter(schema_name=PUBLIC_SCHEMA_NAME).first()
    if public_church is None:
        # auto_create_schema cuida do schema `public` no save.
        public_church = Church(
            schema_name=PUBLIC_SCHEMA_NAME,
            name='Public',
            slug='public',
        )
        public_church.save()
        created = True

    if not Domain.objects.filter(domain=PUBLIC_DOMAIN).exists():
        Domain.objects.create(
            domain=PUBLIC_DOMAIN,
            tenant=public_church,
            is_primary=True,
        )
        created = True

    return created


def create_church_with_admin(
    *,
    slug,
    name,
    leader_title,
    has_communities,
    domain,
    pastor_email,
    pastor_password,
):
    """Provisiona uma igreja completa: schema, dominio e Pastor inicial.

    O save da `Church` dispara `auto_create_schema=True`, que roda as migracoes
    de TENANT_APPS no novo schema. django-tenants cria o schema fora do controle
    transacional do request, entao NAO envolvemos esse save em `atomic` (faze-lo
    pode deixar schema orfao em rollback).

    Levanta `ValueError` se ja existir uma `Church` com o mesmo slug.
    """
    if Church.objects.filter(slug=slug).exists():
        raise ValueError(f'Ja existe uma igreja com o slug "{slug}".')

    public_bootstrapped = ensure_public_tenant()

    church = Church(
        schema_name=f'tenant_{slug}',
        name=name,
        slug=slug,
        leader_title=leader_title,
        has_communities=has_communities,
    )
    church.save()

    domain_obj = Domain.objects.create(
        domain=domain,
        tenant=church,
        is_primary=True,
    )

    # User e model PUBLICO (TENANT-04): nao e preciso entrar no schema do tenant.
    user_model = get_user_model()
    pastor_created = False
    if user_model.objects.filter(email=pastor_email).exists():
        pastor_created = False
    else:
        pastor = user_model(
            email=pastor_email,
            church=church,
            roles=[user_model.Role.PASTOR],
            is_staff=False,
        )
        pastor.set_password(pastor_password)
        pastor.save()
        pastor_created = True

    return ProvisionResult(
        church=church,
        domain=domain_obj,
        pastor_created=pastor_created,
        pastor_email=pastor_email,
        public_bootstrapped=public_bootstrapped,
    )
