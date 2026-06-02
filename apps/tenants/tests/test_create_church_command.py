"""Sprint 1 — comando de gestao `create_church` (TECH_SPEC §2/§4, RN-001).

Cobre `apps.tenants.management.commands.create_church`: provisionamento de
tenant via CLI, conversao de `ValueError` em `CommandError`, aviso de senha
padrao de dev e aplicacao das opcoes (--name/--leader-title/--no-communities/
--pastor-email).

Particularidades django-tenants
-------------------------------
`call_command('create_church', ...)` dispara `auto_create_schema=True` (DDL +
COMMIT). Por isso usamos `@pytest.mark.django_db(transaction=True)` e fazemos
teardown manual (DROP SCHEMA do tenant criado + DELETE de Church/Domain/User).
Slugs distintos ('cmd', 'cmd2', 'cmd3', 'cmdopt') evitam colisao com tenants
pre-existentes e com as fixtures.
"""

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from apps.tenants.models import Church, Domain


def _schema_exists(schema_name):
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT 1 FROM information_schema.schemata WHERE schema_name = %s',
            [schema_name],
        )
        return cursor.fetchone() is not None


def _drop_schema(schema_name):
    with connection.cursor() as cursor:
        cursor.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')


def _delete_tenant_rows(slug):
    user_model = get_user_model()
    user_model.objects.filter(church__slug=slug).delete()
    Domain.objects.filter(tenant__slug=slug).delete()
    Church.objects.filter(slug=slug).delete()


@pytest.mark.django_db(transaction=True)
def test_create_church_command_provisions_tenant():
    slug = 'cmd'
    out = StringIO()
    try:
        call_command(
            'create_church',
            slug,
            '--name',
            'Igreja Comando',
            '--pastor-email',
            'pastor@cmd.localhost',
            '--pastor-password',
            'Test1234!',
            stdout=out,
        )

        church = Church.objects.get(slug=slug)
        assert church.schema_name == 'tenant_cmd'
        assert church.name == 'Igreja Comando'
        assert _schema_exists('tenant_cmd')
        assert Domain.objects.filter(
            domain='cmd.localhost', tenant=church, is_primary=True
        ).exists()

        user_model = get_user_model()
        pastor = user_model.objects.get(email='pastor@cmd.localhost')
        assert pastor.church_id == church.pk
        assert pastor.roles == [user_model.Role.PASTOR]

        output = out.getvalue()
        assert 'tenant_cmd' in output
        assert 'cmd.localhost' in output
        assert 'pastor@cmd.localhost' in output
        assert 'provisionada com sucesso' in output
    finally:
        _delete_tenant_rows(slug)
        _drop_schema('tenant_cmd')


@pytest.mark.django_db(transaction=True)
def test_create_church_command_duplicate_slug_raises_commanderror():
    slug = 'cmd2'
    out = StringIO()
    try:
        call_command(
            'create_church',
            slug,
            '--pastor-password',
            'Test1234!',
            stdout=out,
        )

        with pytest.raises(CommandError):
            call_command(
                'create_church',
                slug,
                '--pastor-password',
                'Test1234!',
                stdout=StringIO(),
            )
    finally:
        _delete_tenant_rows(slug)
        _drop_schema('tenant_cmd2')


@pytest.mark.django_db(transaction=True)
def test_create_church_command_default_password_warns():
    slug = 'cmd3'
    out = StringIO()
    err = StringIO()
    try:
        # Sem --pastor-password: usa o default de dev e deve avisar.
        call_command('create_church', slug, stdout=out, stderr=err)

        combined = out.getvalue() + err.getvalue()
        assert 'AVISO' in combined
        assert 'senha padrao de dev' in combined
    finally:
        _delete_tenant_rows(slug)
        _drop_schema('tenant_cmd3')


@pytest.mark.django_db(transaction=True)
def test_create_church_command_custom_options():
    slug = 'cmdopt'
    out = StringIO()
    try:
        call_command(
            'create_church',
            slug,
            '--name',
            'Paroquia Custom',
            '--leader-title',
            'Padre',
            '--no-communities',
            '--pastor-email',
            'padre@cmdopt.localhost',
            '--pastor-password',
            'Test1234!',
            stdout=out,
        )

        church = Church.objects.get(slug=slug)
        assert church.name == 'Paroquia Custom'
        assert church.leader_title == 'Padre'
        assert church.has_communities is False

        user_model = get_user_model()
        assert user_model.objects.filter(
            email='padre@cmdopt.localhost', church=church
        ).exists()
    finally:
        _delete_tenant_rows(slug)
        _drop_schema('tenant_cmdopt')
