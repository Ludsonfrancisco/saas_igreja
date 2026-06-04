"""Sprint 3 / Frente 2 (Bloco 2) — views CRUD de Pessoa (Pastor-only).

Cobre: barreira de papel (Pastor 200; Líder/Membro 403; anônimo → login), criação
via view passando pelo SERVICE (consent OPS-05), filtros/busca da lista e exclusão
de anonimizadas. O escopo de Líder (ver só a própria comunidade) é Frente 3.

Person é model de TENANT: as requests usam `Client(HTTP_HOST='a.testserver')`
(Domain de `church_a`) e os dados de apoio são criados via `schema_context`.
`transaction=True` por causa do DDL de criar Church.
"""

import pytest
from django.db import connection
from django.test import Client
from django.utils import timezone
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.people.models import Person

GOOD_PASSWORD = 'Senha@123'
LIST_URL = '/pessoas/'
CREATE_URL = '/pessoas/nova/'


@pytest.fixture
def tenant_client():
    client = Client(HTTP_HOST='a.testserver')
    yield client
    connection.set_schema_to_public()


def _make_user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


def _make_person(church, name, **kwargs):
    with schema_context(church.schema_name):
        return Person.objects.create(name=name, **kwargs)


def _count_persons(church, **filters):
    with schema_context(church.schema_name):
        return Person.objects.filter(**filters).count()


# --- Barreira de papel (ACCESS_MATRIX §3.3: listar todas = só Pastor) --------


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    'roles,expected',
    [(['pastor'], 200), (['leader'], 403), (['member'], 403)],
)
def test_person_list_role_barrier(tenant_client, church_a, roles, expected):
    user = _make_user(church_a, f'{roles[0]}@a.com', roles)
    tenant_client.force_login(user)
    assert tenant_client.get(LIST_URL).status_code == expected


@pytest.mark.django_db(transaction=True)
def test_person_list_requires_login(tenant_client, church_a):
    resp = tenant_client.get(LIST_URL)
    assert resp.status_code == 302
    assert resp.url.startswith('/contas/login/')


# --- Criação via view (passa pelo service: consent OPS-05) -------------------


@pytest.mark.django_db(transaction=True)
def test_create_person_via_view_requires_consent_for_contact(tenant_client, church_a):
    """POST com email mas sem marcar consentimento: form rejeita (200), nada criado."""
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    tenant_client.force_login(pastor)

    resp = tenant_client.post(
        CREATE_URL,
        {'name': 'Maria', 'status': 'visitor', 'email': 'maria@a.com'},
    )
    assert resp.status_code == 200
    assert _count_persons(church_a) == 0


@pytest.mark.django_db(transaction=True)
def test_create_person_via_view_success(tenant_client, church_a):
    """Pastor cria pessoa válida -> 302 e registro criado no tenant."""
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    tenant_client.force_login(pastor)

    resp = tenant_client.post(
        CREATE_URL,
        {
            'name': 'Joao',
            'status': 'member',
            'email': 'joao@a.com',
            'consent_given': 'on',
        },
    )
    assert resp.status_code == 302
    assert resp.url == LIST_URL
    assert _count_persons(church_a, name='Joao') == 1


@pytest.mark.django_db(transaction=True)
def test_create_person_via_view_member_forbidden(tenant_client, church_a):
    member = _make_user(church_a, 'membro@a.com', ['member'])
    tenant_client.force_login(member)
    assert tenant_client.get(CREATE_URL).status_code == 403


# --- Filtros, busca e exclusão de anonimizadas ------------------------------


@pytest.mark.django_db(transaction=True)
def test_person_list_filters_by_status_and_searches_by_name(tenant_client, church_a):
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    _make_person(church_a, 'Ana Lima', status=Person.Status.MEMBER)
    _make_person(church_a, 'Bruno Souza', status=Person.Status.VISITOR)
    tenant_client.force_login(pastor)

    by_status = tenant_client.get(LIST_URL, {'status': 'member'})
    names = {p.name for p in by_status.context['persons']}
    assert names == {'Ana Lima'}

    by_search = tenant_client.get(LIST_URL, {'q': 'bruno'})
    names = {p.name for p in by_search.context['persons']}
    assert names == {'Bruno Souza'}


@pytest.mark.django_db(transaction=True)
def test_person_list_excludes_anonymized(tenant_client, church_a):
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    _make_person(church_a, 'Ativa')
    _make_person(church_a, 'Removida', anonymized_at=timezone.now())
    tenant_client.force_login(pastor)

    resp = tenant_client.get(LIST_URL)
    names = {p.name for p in resp.context['persons']}
    assert names == {'Ativa'}


# --- Edição via view --------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_update_person_via_view(tenant_client, church_a):
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    person = _make_person(church_a, 'Carlos', status=Person.Status.VISITOR)
    tenant_client.force_login(pastor)

    resp = tenant_client.post(
        f'/pessoas/{person.pk}/editar/',
        {'name': 'Carlos Alberto', 'status': 'member'},
    )
    assert resp.status_code == 302

    with schema_context(church_a.schema_name):
        person.refresh_from_db()
    assert person.name == 'Carlos Alberto'
    assert person.status == Person.Status.MEMBER


@pytest.mark.django_db(transaction=True)
def test_person_list_filters_by_community_and_ministry(tenant_client, church_a):
    from apps.communities.models import Community
    from apps.ministries.models import Ministry

    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        community = Community.objects.create(name='Centro')
        ministry = Ministry.objects.create(name='Louvor')
        Person.objects.create(name='Da Comunidade', community=community)
        com_min = Person.objects.create(name='Do Ministerio')
        com_min.ministries.add(ministry)
        Person.objects.create(name='Sem Vinculo')
    tenant_client.force_login(pastor)

    by_community = tenant_client.get(LIST_URL, {'community': community.id})
    assert {p.name for p in by_community.context['persons']} == {'Da Comunidade'}

    by_ministry = tenant_client.get(LIST_URL, {'ministry': ministry.id})
    assert {p.name for p in by_ministry.context['persons']} == {'Do Ministerio'}


@pytest.mark.django_db(transaction=True)
def test_create_person_via_view_blocked_by_plan_limit(
    tenant_client, church_a, monkeypatch
):
    """Form válido, mas o SERVICE recusa pelo limite de plano -> 200, nada criado."""
    from apps.tenants.models import Plan

    monkeypatch.setitem(Plan.PLAN_LIMITS['free'], 'max_persons', 1)
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    _make_person(church_a, 'Existente')
    tenant_client.force_login(pastor)

    resp = tenant_client.post(CREATE_URL, {'name': 'Nova', 'status': 'visitor'})
    assert resp.status_code == 200
    assert _count_persons(church_a, name='Nova') == 0


@pytest.mark.django_db(transaction=True)
def test_edit_form_prechecks_consent_for_person_with_consent(tenant_client, church_a):
    """Ao editar quem já tem consentimento, o checkbox vem pré-marcado (UX)."""
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    person = _make_person(
        church_a, 'Com Consent', email='c@a.com', consent_given_at=timezone.now()
    )
    tenant_client.force_login(pastor)

    resp = tenant_client.get(f'/pessoas/{person.pk}/editar/')
    assert resp.context['form'].fields['consent_given'].initial is True
