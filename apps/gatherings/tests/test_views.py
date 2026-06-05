"""Sprint 4 / Frente 1 — views CRUD de Encontro (ACCESS_MATRIX §3.6).

Cobre: barreira de papel (Listar = Pastor/Secretário/Líder; Membro 403), criação
por tipo (form filtra o dropdown), escopo de edição (criador OU comunidade que
lidera; fora → 404), exclusão só-Pastor, Secretário admin (cria WORSHIP, edita,
não exclui), e auditoria automática.
"""

import datetime

import pytest
from django.db import connection
from django.test import Client
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.communities.models import Community
from apps.core.models import AuditLog
from apps.gatherings.models import Gathering
from apps.people.models import Person

GOOD_PASSWORD = 'Senha@123'
LIST_URL = '/encontros/'
CREATE_URL = '/encontros/novo/'
TODAY = '2026-06-10'


@pytest.fixture
def tenant_client():
    client = Client(HTTP_HOST='a.testserver')
    yield client
    connection.set_schema_to_public()


def _make_user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


def _leader_with_community(church, user, name='Minha'):
    """Cria a Person-líder (vinculada ao user) + a comunidade que ela lidera."""
    with schema_context(church.schema_name):
        person = Person.objects.create(name='Lider', user_id=user.id)
        community = Community.objects.create(name=name)
        community.leaders.add(person)
        return community


def _make_gathering(church, gtype='event', created_by=None, community=None, **extra):
    with schema_context(church.schema_name):
        return Gathering.objects.create(
            gathering_type=gtype,
            date=datetime.date(2026, 6, 10),
            created_by=created_by,
            community=community,
            **extra,
        )


# --- Barreira de papel -------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    'roles,expected',
    [(['pastor'], 200), (['secretary'], 200), (['leader'], 200), (['member'], 403)],
)
def test_gathering_list_role_barrier(tenant_client, church_a, roles, expected):
    user = _make_user(church_a, f'{roles[0]}@a.com', roles)
    tenant_client.force_login(user)
    assert tenant_client.get(LIST_URL).status_code == expected


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    'roles,expected',
    [(['pastor'], 200), (['secretary'], 200), (['leader'], 200), (['member'], 403)],
)
def test_gathering_create_role_barrier(tenant_client, church_a, roles, expected):
    user = _make_user(church_a, f'{roles[0]}@a.com', roles)
    tenant_client.force_login(user)
    assert tenant_client.get(CREATE_URL).status_code == expected


@pytest.mark.django_db(transaction=True)
def test_gathering_list_shows_all(tenant_client, church_a):
    """Líder vê TODOS os encontros na listagem (§3.6), não só os seus."""
    _make_gathering(church_a, gtype='worship')
    leader = _make_user(church_a, 'leader@a.com', ['leader'])
    tenant_client.force_login(leader)
    resp = tenant_client.get(LIST_URL)
    assert resp.status_code == 200
    assert len(resp.context['gatherings']) == 1


# --- Criação por tipo --------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_pastor_creates_worship(tenant_client, church_a):
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    tenant_client.force_login(pastor)
    resp = tenant_client.post(
        CREATE_URL, {'gathering_type': 'worship', 'date': TODAY, 'title': 'Culto'}
    )
    assert resp.status_code == 302
    with schema_context(church_a.schema_name):
        g = Gathering.objects.get(gathering_type='worship')
        assert g.created_by == pastor.id


@pytest.mark.django_db(transaction=True)
def test_leader_worship_choice_not_offered(tenant_client, church_a):
    """O dropdown do Líder não oferece WORSHIP (form filtra por papel)."""
    leader = _make_user(church_a, 'leader@a.com', ['leader'])
    tenant_client.force_login(leader)
    resp = tenant_client.get(CREATE_URL)
    choices = dict(resp.context['form'].fields['gathering_type'].choices)
    assert 'worship' not in choices
    assert 'event' in choices


@pytest.mark.django_db(transaction=True)
def test_leader_cannot_post_worship(tenant_client, church_a):
    """Mesmo forjando o POST, o Líder não cria WORSHIP (form inválido, nada criado)."""
    leader = _make_user(church_a, 'leader@a.com', ['leader'])
    tenant_client.force_login(leader)
    resp = tenant_client.post(CREATE_URL, {'gathering_type': 'worship', 'date': TODAY})
    assert resp.status_code == 200
    with schema_context(church_a.schema_name):
        assert not Gathering.objects.filter(gathering_type='worship').exists()


@pytest.mark.django_db(transaction=True)
def test_community_type_hidden_when_no_communities(tenant_client, church_a):
    """RN-010: igreja sem comunidades não oferece o tipo COMMUNITY."""
    church_a.has_communities = False
    church_a.save()
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    tenant_client.force_login(pastor)
    resp = tenant_client.get(CREATE_URL)
    choices = dict(resp.context['form'].fields['gathering_type'].choices)
    assert 'community' not in choices
    assert 'community' not in resp.context['form'].fields  # campo de comunidade some


@pytest.mark.django_db(transaction=True)
def test_leader_creates_community_gathering_of_own_community(tenant_client, church_a):
    leader = _make_user(church_a, 'leader@a.com', ['leader'])
    community = _leader_with_community(church_a, leader)
    tenant_client.force_login(leader)
    resp = tenant_client.post(
        CREATE_URL,
        {'gathering_type': 'community', 'date': TODAY, 'community': community.pk},
    )
    assert resp.status_code == 302
    with schema_context(church_a.schema_name):
        assert Gathering.objects.filter(
            gathering_type='community', community=community
        ).exists()


# --- Escopo de edição --------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_leader_edits_own_creation(tenant_client, church_a):
    leader = _make_user(church_a, 'leader@a.com', ['leader'])
    g = _make_gathering(church_a, gtype='event', created_by=leader.id, title='X')
    tenant_client.force_login(leader)
    resp = tenant_client.post(
        f'/encontros/{g.pk}/editar/',
        {'gathering_type': 'event', 'date': TODAY, 'title': 'Renomeado'},
    )
    assert resp.status_code == 302
    with schema_context(church_a.schema_name):
        g.refresh_from_db()
        assert g.title == 'Renomeado'


@pytest.mark.django_db(transaction=True)
def test_leader_edits_gathering_of_own_community(tenant_client, church_a):
    leader = _make_user(church_a, 'leader@a.com', ['leader'])
    community = _leader_with_community(church_a, leader)
    # encontro criado por OUTRA pessoa, mas da comunidade que o líder lidera.
    g = _make_gathering(
        church_a, gtype='community', created_by=999, community=community
    )
    tenant_client.force_login(leader)
    assert tenant_client.get(f'/encontros/{g.pk}/editar/').status_code == 200


@pytest.mark.django_db(transaction=True)
def test_leader_cannot_edit_foreign_gathering(tenant_client, church_a):
    """Encontro que o líder não criou e não é da sua comunidade → 404."""
    leader = _make_user(church_a, 'leader@a.com', ['leader'])
    _leader_with_community(church_a, leader)
    g = _make_gathering(church_a, gtype='event', created_by=999)
    tenant_client.force_login(leader)
    assert tenant_client.get(f'/encontros/{g.pk}/editar/').status_code == 404


@pytest.mark.django_db(transaction=True)
def test_edit_locks_type(tenant_client, church_a):
    """Na edição o tipo é travado (disabled) — sem conversão de EVENT→WORSHIP."""
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    g = _make_gathering(church_a, gtype='event', created_by=pastor.id)
    tenant_client.force_login(pastor)
    resp = tenant_client.get(f'/encontros/{g.pk}/editar/')
    assert resp.context['form'].fields['gathering_type'].disabled is True


# --- Exclusão (só Pastor) ----------------------------------------------------


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    'roles,expected', [(['pastor'], 302), (['secretary'], 403), (['leader'], 403)]
)
def test_gathering_delete_pastor_only(tenant_client, church_a, roles, expected):
    user = _make_user(church_a, f'{roles[0]}@a.com', roles)
    g = _make_gathering(church_a, gtype='event', created_by=user.id)
    tenant_client.force_login(user)
    resp = tenant_client.post(f'/encontros/{g.pk}/excluir/')
    assert resp.status_code == expected
    with schema_context(church_a.schema_name):
        assert Gathering.objects.filter(pk=g.pk).exists() is (expected != 302)


# --- Secretário admin --------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_secretary_creates_worship_and_edits_any_but_cannot_delete(
    tenant_client, church_a
):
    secretary = _make_user(church_a, 'sec@a.com', ['secretary'])
    tenant_client.force_login(secretary)

    # cria WORSHIP (admin como Pastor)
    resp = tenant_client.post(
        CREATE_URL, {'gathering_type': 'worship', 'date': TODAY, 'title': 'Culto'}
    )
    assert resp.status_code == 302
    with schema_context(church_a.schema_name):
        g = Gathering.objects.get(gathering_type='worship')

    # edita qualquer encontro (sem escopo)
    assert tenant_client.get(f'/encontros/{g.pk}/editar/').status_code == 200
    # NÃO exclui (só Pastor)
    assert tenant_client.get(f'/encontros/{g.pk}/excluir/').status_code == 403


# --- Auditoria ---------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_gathering_create_audited(tenant_client, church_a):
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    tenant_client.force_login(pastor)
    tenant_client.post(
        CREATE_URL, {'gathering_type': 'meeting', 'date': TODAY, 'title': 'Reuniao'}
    )
    with schema_context(church_a.schema_name):
        g = Gathering.objects.get(gathering_type='meeting')
        assert AuditLog.objects.filter(
            model_name='Gathering', action='create', object_id=str(g.pk)
        ).exists()
