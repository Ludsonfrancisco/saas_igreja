"""Sprint 1 — service layer de provisionamento de tenants (P-ARQ-04).

Cobre `apps.tenants.services` (RN-001 / TENANT-01 / TENANT-04, TECH_SPEC §2/§4):

- `ensure_public_tenant`: bootstrap idempotente do tenant publico + dominio
  `localhost`.
- `create_church_with_admin`: provisiona schema dedicado, dominio primario e o
  Pastor inicial (User publico), retornando um `ProvisionResult`.

Particularidades django-tenants
-------------------------------
`Church.save()` dispara `auto_create_schema=True` (DDL + COMMIT imediato), que
o rollback transacional padrao NAO desfaz. Por isso os testes que provisionam
schema usam `@pytest.mark.django_db(transaction=True)` e fazem teardown manual
(DROP SCHEMA do tenant criado + DELETE das linhas Church/Domain/User).

O bootstrap publico cria uma linha Church(schema_name='public') + Domain
('localhost') — o schema `public` ja existe, entao nenhum schema novo e feito.
No teardown removemos apenas essas LINHAS; NUNCA derrubamos o schema `public`.
Usamos slugs distintos ('svc', 'svc2', 'tradicional') para nao colidir com
tenants pre-existentes (athos/bethel) nem com as fixtures (a/b).
"""

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django_tenants.utils import get_public_schema_name

from apps.tenants.models import Church, Domain
from apps.tenants.services import (
    PUBLIC_DOMAIN,
    PUBLIC_SCHEMA_NAME,
    ProvisionResult,
    create_church_with_admin,
    ensure_public_tenant,
)


def _schema_exists(schema_name):
    """True se o schema existe fisicamente em information_schema.schemata."""
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT 1 FROM information_schema.schemata WHERE schema_name = %s',
            [schema_name],
        )
        return cursor.fetchone() is not None


def _drop_schema(schema_name):
    """Remove fisicamente um schema de tenant (teardown de DDL nao-transacional)."""
    with connection.cursor() as cursor:
        cursor.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')


def _delete_tenant_rows(slug):
    """Remove as linhas Church/Domain/User criadas por um teste (por slug)."""
    user_model = get_user_model()
    user_model.objects.filter(church__slug=slug).delete()
    Domain.objects.filter(tenant__slug=slug).delete()
    Church.objects.filter(slug=slug).delete()


@pytest.mark.django_db(transaction=True)
def test_ensure_public_tenant_creates_public_church_and_domain():
    # Pre-condicao: garante ausencia para exercitar o ramo de criacao.
    # NUNCA derrubamos o schema public; removemos apenas as LINHAS.
    Domain.objects.filter(domain=PUBLIC_DOMAIN).delete()
    Church.objects.filter(schema_name=PUBLIC_SCHEMA_NAME).delete()

    try:
        created = ensure_public_tenant()

        assert created is True
        public_church = Church.objects.get(schema_name=PUBLIC_SCHEMA_NAME)
        assert public_church.name == 'Public'
        assert public_church.slug == 'public'
        assert Domain.objects.filter(domain=PUBLIC_DOMAIN, is_primary=True).exists()

        # Idempotente: segunda chamada nao cria nada.
        assert ensure_public_tenant() is False
    finally:
        Domain.objects.filter(domain=PUBLIC_DOMAIN).delete()
        Church.objects.filter(schema_name=PUBLIC_SCHEMA_NAME).delete()


@pytest.mark.django_db(transaction=True)
def test_create_church_with_admin_provisions_schema_domain_and_pastor():
    slug = 'svc'
    try:
        result = create_church_with_admin(
            slug=slug,
            name='Igreja Service',
            leader_title='Pastor',
            has_communities=True,
            domain='svc.localhost',
            pastor_email='pastor@svc.localhost',
            pastor_password='Test1234!',
        )

        assert isinstance(result, ProvisionResult)

        # Church persistida com schema dedicado fisicamente criado.
        assert result.church.schema_name == 'tenant_svc'
        assert result.church.slug == slug
        assert result.church.name == 'Igreja Service'
        assert result.church.leader_title == 'Pastor'
        assert result.church.has_communities is True
        assert _schema_exists('tenant_svc')
        assert Church.objects.filter(slug=slug).exists()

        # Dominio primario registrado.
        assert result.domain.domain == 'svc.localhost'
        assert result.domain.is_primary is True
        assert Domain.objects.filter(
            domain='svc.localhost', tenant=result.church
        ).exists()

        # Pastor criado: User publico com FK simples + role 'pastor'.
        assert result.pastor_created is True
        assert result.pastor_email == 'pastor@svc.localhost'
        user_model = get_user_model()
        pastor = user_model.objects.get(email='pastor@svc.localhost')
        assert pastor.church_id == result.church.pk
        assert pastor.roles == [user_model.Role.PASTOR]
        assert pastor.is_staff is False
        assert pastor.check_password('Test1234!')
    finally:
        _delete_tenant_rows(slug)
        _drop_schema('tenant_svc')


@pytest.mark.django_db(transaction=True)
def test_create_church_with_admin_duplicate_slug_raises_valueerror():
    slug = 'svc2'
    try:
        create_church_with_admin(
            slug=slug,
            name='Igreja Dup',
            leader_title='Pastor',
            has_communities=True,
            domain='svc2.localhost',
            pastor_email='pastor@svc2.localhost',
            pastor_password='Test1234!',
        )

        with pytest.raises(ValueError):
            create_church_with_admin(
                slug=slug,
                name='Igreja Dup 2',
                leader_title='Pastor',
                has_communities=True,
                domain='svc2-other.localhost',
                pastor_email='pastor2@svc2.localhost',
                pastor_password='Test1234!',
            )
    finally:
        _delete_tenant_rows(slug)
        _drop_schema('tenant_svc2')


@pytest.mark.django_db(transaction=True)
def test_create_church_with_admin_skips_pastor_when_email_exists():
    slug = 'svc3'
    existing_email = 'pastor@svc3.localhost'
    user_model = get_user_model()
    # Email e unico globalmente: pre-cria um User com esse email (sem church).
    user_model.objects.create_user(
        email=existing_email,
        password='Existing1!',
        roles=['pastor'],
    )

    try:
        result = create_church_with_admin(
            slug=slug,
            name='Igreja Skip',
            leader_title='Pastor',
            has_communities=True,
            domain='svc3.localhost',
            pastor_email=existing_email,
            pastor_password='Test1234!',
        )

        assert result.pastor_created is False
        # Nenhum duplicado foi criado para esse email.
        assert user_model.objects.filter(email=existing_email).count() == 1
        # A church/dominio ainda assim foram provisionados.
        assert _schema_exists('tenant_svc3')
        assert Domain.objects.filter(domain='svc3.localhost').exists()
    finally:
        user_model.objects.filter(email=existing_email).delete()
        _delete_tenant_rows(slug)
        _drop_schema('tenant_svc3')


@pytest.mark.django_db(transaction=True)
def test_create_church_with_admin_respects_has_communities_false():
    slug = 'tradicional'
    try:
        result = create_church_with_admin(
            slug=slug,
            name='Igreja Tradicional',
            leader_title='Padre',
            has_communities=False,
            domain='tradicional.localhost',
            pastor_email='padre@tradicional.localhost',
            pastor_password='Test1234!',
        )

        assert result.church.has_communities is False
        assert result.church.leader_title == 'Padre'
        # Persistido como False no banco, nao apenas no objeto em memoria.
        assert Church.objects.get(slug=slug).has_communities is False
    finally:
        _delete_tenant_rows(slug)
        _drop_schema('tenant_tradicional')


@pytest.mark.django_db(transaction=True)
def test_schema_resets_to_public_after_provisioning():
    """Provisionar nao deve deixar o search_path apontando para o tenant."""
    slug = 'svc4'
    try:
        create_church_with_admin(
            slug=slug,
            name='Igreja Reset',
            leader_title='Pastor',
            has_communities=True,
            domain='svc4.localhost',
            pastor_email='pastor@svc4.localhost',
            pastor_password='Test1234!',
        )
        assert connection.schema_name == get_public_schema_name()
    finally:
        _delete_tenant_rows(slug)
        _drop_schema('tenant_svc4')
