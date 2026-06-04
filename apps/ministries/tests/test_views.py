"""Sprint 3 / Frente 3 (Bloco 3) — views CRUD de Ministério (ACCESS_MATRIX §3.5).

Cobre: barreira de papel (Criar/Excluir só Pastor; Listar Pastor+Líder/Coord;
Editar Coordenador escopado), auditoria de edição, e a trava "Coordenador não
define coordenadores" (campo some no form).
"""

import pytest
from django.db import connection
from django.test import Client
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.ministries.models import Ministry
from apps.people.models import Person

GOOD_PASSWORD = 'Senha@123'
LIST_URL = '/ministerios/'
CREATE_URL = '/ministerios/novo/'


@pytest.fixture
def tenant_client():
    client = Client(HTTP_HOST='a.testserver')
    yield client
    connection.set_schema_to_public()


def _make_user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


def _make_ministry(church, name):
    with schema_context(church.schema_name):
        return Ministry.objects.create(name=name)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    'roles,expected', [(['pastor'], 200), (['leader'], 200), (['member'], 403)]
)
def test_ministry_list_role_barrier(tenant_client, church_a, roles, expected):
    user = _make_user(church_a, f'{roles[0]}@a.com', roles)
    tenant_client.force_login(user)
    assert tenant_client.get(LIST_URL).status_code == expected


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    'roles,expected', [(['pastor'], 200), (['leader'], 403), (['member'], 403)]
)
def test_ministry_create_pastor_only(tenant_client, church_a, roles, expected):
    user = _make_user(church_a, f'{roles[0]}@a.com', roles)
    tenant_client.force_login(user)
    assert tenant_client.get(CREATE_URL).status_code == expected


@pytest.mark.django_db(transaction=True)
def test_ministry_create_via_view(tenant_client, church_a):
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    tenant_client.force_login(pastor)

    resp = tenant_client.post(CREATE_URL, {'name': 'Louvor', 'is_active': 'on'})
    assert resp.status_code == 302
    with schema_context(church_a.schema_name):
        assert Ministry.objects.filter(name='Louvor').exists()


@pytest.mark.django_db(transaction=True)
def test_ministry_update_audited(tenant_client, church_a):
    ministry = _make_ministry(church_a, 'Antigo')
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    tenant_client.force_login(pastor)

    resp = tenant_client.post(
        f'/ministerios/{ministry.pk}/editar/', {'name': 'Renomeado', 'is_active': 'on'}
    )
    assert resp.status_code == 302
    with schema_context(church_a.schema_name):
        ministry.refresh_from_db()
        assert ministry.name == 'Renomeado'
        assert AuditLog.objects.filter(
            model_name='Ministry', action='update', object_id=str(ministry.pk)
        ).exists()


@pytest.mark.django_db(transaction=True)
def test_coordinator_edits_only_own_ministry(tenant_client, church_a):
    coord_user = _make_user(church_a, 'coord@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        coord_person = Person.objects.create(name='Coord', user_id=coord_user.id)
        mine = Ministry.objects.create(name='Meu')
        mine.coordinators.add(coord_person)
        other = Ministry.objects.create(name='Outro')

    tenant_client.force_login(coord_user)
    assert tenant_client.get(f'/ministerios/{mine.pk}/editar/').status_code == 200
    assert tenant_client.get(f'/ministerios/{other.pk}/editar/').status_code == 404


@pytest.mark.django_db(transaction=True)
def test_coordinator_edit_form_has_no_coordinators_field(tenant_client, church_a):
    """Definir coordenadores é só do Pastor: o Coordenador não vê o campo."""
    coord_user = _make_user(church_a, 'coord@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        coord_person = Person.objects.create(name='Coord', user_id=coord_user.id)
        mine = Ministry.objects.create(name='Meu')
        mine.coordinators.add(coord_person)

    tenant_client.force_login(coord_user)
    resp = tenant_client.get(f'/ministerios/{mine.pk}/editar/')
    assert resp.status_code == 200
    assert 'coordinators' not in resp.context['form'].fields


@pytest.mark.django_db(transaction=True)
def test_ministry_delete_pastor_only(tenant_client, church_a):
    ministry = _make_ministry(church_a, 'Alvo')
    leader = _make_user(church_a, 'leader@a.com', ['leader'])
    tenant_client.force_login(leader)
    assert tenant_client.get(f'/ministerios/{ministry.pk}/excluir/').status_code == 403

    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    tenant_client.force_login(pastor)
    resp = tenant_client.post(f'/ministerios/{ministry.pk}/excluir/')
    assert resp.status_code == 302
    with schema_context(church_a.schema_name):
        assert not Ministry.objects.filter(pk=ministry.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_secretary_creates_but_cannot_delete_ministry(tenant_client, church_a):
    """OD-019: Secretário cria/edita ministério, mas não exclui (só Pastor)."""
    secretary = _make_user(church_a, 'sec@a.com', ['secretary'])
    ministry = _make_ministry(church_a, 'Alvo')
    tenant_client.force_login(secretary)

    assert tenant_client.get(CREATE_URL).status_code == 200
    assert tenant_client.get(f'/ministerios/{ministry.pk}/excluir/').status_code == 403
