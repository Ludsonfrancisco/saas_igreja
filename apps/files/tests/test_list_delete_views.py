"""Sprint 6 / Bloco 4 — listagem com escopo por contexto + exclusao (Pastor).

Cobertura (ACCESS_MATRIX §3.8 + RISK-001):
- Listagem: Pastor/Secretario veem TODOS os arquivos; Lider so os da(s) sua(s)
  comunidade(s)/ministerio(s) — sem vazamento intra-tenant.
- Filtro por contexto (`related_model`/`related_object_id`) funciona e NUNCA amplia
  o escopo do papel.
- Exclusao: Pastor exclui (302 + sumiu + AuditLog 'delete'); Secretario/Lider/
  Membro => 403; cross-tenant/inexistente => 404.
- Download escopado (fecha pendencia do Bloco 3): Lider NAO baixa arquivo fora do
  seu escopo => 404; Pastor baixa qualquer um.

FileAsset/Community/Ministry/Person vivem no schema do tenant (TENANT-04) ->
`schema_context` para ORM puro; host `a.testserver`/`b.testserver` nos requests.
DDL de criar Church exige `@pytest.mark.django_db(transaction=True)`.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client, override_settings
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.communities.models import Community
from apps.core.models import AuditLog
from apps.files import services
from apps.files.models import FileAsset
from apps.ministries.models import Ministry
from apps.people.models import Person

GOOD_PASSWORD = 'Senha@123'
PDF_BYTES = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< >>\nendobj\n'

LIST_URL = '/arquivos/'

# Os templates HTML sao do agente de frontend (fora do escopo do backend). Para
# exercitar a VIEW de listagem (escopo/filtro do queryset) sem depender desses
# arquivos, injetamos templates triviais via locmem loader. Assertamos sobre
# `resp.context` — a logica de backend — nao sobre o HTML renderizado.
_STUB_TEMPLATES = {
    'files/file_list.html': 'ok',
    'files/file_confirm_delete.html': 'ok',
}

stub_templates = override_settings(
    TEMPLATES=[
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [],
            'APP_DIRS': False,
            'OPTIONS': {
                'loaders': [
                    ('django.template.loaders.locmem.Loader', _STUB_TEMPLATES),
                ],
                'context_processors': [
                    'django.contrib.auth.context_processors.auth',
                    'django.contrib.messages.context_processors.messages',
                ],
            },
        }
    ]
)


@pytest.fixture
def tenant_client():
    client = Client(HTTP_HOST='a.testserver')
    yield client
    connection.set_schema_to_public()


def _user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


def _upload(uploaded_by_id=1, related_model='', related_object_id=''):
    uploaded = SimpleUploadedFile('doc.pdf', PDF_BYTES, content_type='application/pdf')
    return services.upload_file(
        uploaded_file=uploaded,
        uploaded_by_id=uploaded_by_id,
        related_model=related_model,
        related_object_id=related_object_id,
    )


def _delete_url(pk):
    return f'/arquivos/{pk}/excluir/'


def _download_url(pk):
    return f'/arquivos/{pk}/download/'


# --------------------------------------------------------------------------- #
# Listagem — escopo por papel/contexto
# --------------------------------------------------------------------------- #
@stub_templates
@pytest.mark.django_db(transaction=True)
def test_pastor_lists_all_files(tenant_client, church_a):
    """Pastor ve TODOS os arquivos do tenant, qualquer contexto (§3.8)."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        a = _upload(related_model='community', related_object_id='1')
        b = _upload(related_model='ministry', related_object_id='2')
        c = _upload()  # sem contexto (geral)

    tenant_client.force_login(pastor)
    resp = tenant_client.get(LIST_URL)
    assert resp.status_code == 200
    listed = {f.pk for f in resp.context['file_assets']}
    assert listed == {a.pk, b.pk, c.pk}


@stub_templates
@pytest.mark.django_db(transaction=True)
def test_secretary_lists_all_files(tenant_client, church_a):
    """Secretario tambem ve tudo (curto-circuita o escopo, igual ao Pastor)."""
    secretary = _user(church_a, 'sec@a.com', ['secretary'])
    with schema_context(church_a.schema_name):
        a = _upload(related_model='community', related_object_id='1')
        b = _upload()

    tenant_client.force_login(secretary)
    resp = tenant_client.get(LIST_URL)
    assert resp.status_code == 200
    assert {f.pk for f in resp.context['file_assets']} == {a.pk, b.pk}


@stub_templates
@pytest.mark.django_db(transaction=True)
def test_leader_lists_only_own_community_files(tenant_client, church_a):
    """Lider ve so os arquivos da(s) comunidade(s) que LIDERA — sem vazamento.

    Deriva o escopo do mesmo vinculo `Community.leaders -> Person.user_id` usado nas
    outras listas. Arquivo de OUTRA comunidade nao aparece.
    """
    leader = _user(church_a, 'leader@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        leader_person = Person.objects.create(name='Lider', user_id=leader.id)
        led = Community.objects.create(name='Celula do Lider')
        led.leaders.add(leader_person)
        other = Community.objects.create(name='Outra Celula')

        mine = _upload(related_model='community', related_object_id=str(led.pk))
        not_mine = _upload(related_model='community', related_object_id=str(other.pk))
        general = _upload()  # geral: fora do escopo de Lider

    tenant_client.force_login(leader)
    resp = tenant_client.get(LIST_URL)
    assert resp.status_code == 200
    listed = {f.pk for f in resp.context['file_assets']}
    assert mine.pk in listed
    assert not_mine.pk not in listed
    assert general.pk not in listed


@stub_templates
@pytest.mark.django_db(transaction=True)
def test_leader_lists_own_ministry_files(tenant_client, church_a):
    """`leader` como Coordenador ve arquivos do ministerio que coordena."""
    leader = _user(church_a, 'coord@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        person = Person.objects.create(name='Coord', user_id=leader.id)
        ministry = Ministry.objects.create(name='Louvor')
        ministry.coordinators.add(person)
        other = Ministry.objects.create(name='Diaconia')

        mine = _upload(related_model='ministry', related_object_id=str(ministry.pk))
        not_mine = _upload(related_model='ministry', related_object_id=str(other.pk))

    tenant_client.force_login(leader)
    resp = tenant_client.get(LIST_URL)
    listed = {f.pk for f in resp.context['file_assets']}
    assert mine.pk in listed
    assert not_mine.pk not in listed


@stub_templates
@pytest.mark.django_db(transaction=True)
def test_leader_without_links_sees_nothing(tenant_client, church_a):
    """Lider sem comunidade/ministerio vinculado nao ve arquivo algum (conservador).

    Garante que um predicado vazio NAO casa com tudo (evita vazamento intra-tenant).
    """
    leader = _user(church_a, 'lone@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        _upload(related_model='community', related_object_id='1')
        _upload()

    tenant_client.force_login(leader)
    resp = tenant_client.get(LIST_URL)
    assert resp.status_code == 200
    assert list(resp.context['file_assets']) == []


# --------------------------------------------------------------------------- #
# Filtro por contexto — nunca amplia escopo
# --------------------------------------------------------------------------- #
@stub_templates
@pytest.mark.django_db(transaction=True)
def test_filter_by_context_narrows_within_scope(tenant_client, church_a):
    """Filtro `?related_model=&related_object_id=` restringe DENTRO do escopo."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        comm = _upload(related_model='community', related_object_id='10')
        _upload(related_model='ministry', related_object_id='20')

    tenant_client.force_login(pastor)
    resp = tenant_client.get(
        LIST_URL, {'related_model': 'community', 'related_object_id': '10'}
    )
    assert {f.pk for f in resp.context['file_assets']} == {comm.pk}


@stub_templates
@pytest.mark.django_db(transaction=True)
def test_filter_cannot_widen_leader_scope(tenant_client, church_a):
    """Filtro pedindo um contexto FORA do escopo do papel retorna vazio (nao vaza).

    P-ARQ-08: o filtro intersecta o queryset ja escopado pelo papel. Um Lider que
    filtra por uma comunidade que NAO lidera nao consegue ver os arquivos dela.
    """
    leader = _user(church_a, 'leader@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        person = Person.objects.create(name='Lider', user_id=leader.id)
        led = Community.objects.create(name='Minha')
        led.leaders.add(person)
        other = Community.objects.create(name='Alheia')
        _upload(related_model='community', related_object_id=str(other.pk))

    tenant_client.force_login(leader)
    resp = tenant_client.get(
        LIST_URL,
        {'related_model': 'community', 'related_object_id': str(other.pk)},
    )
    assert list(resp.context['file_assets']) == []


# --------------------------------------------------------------------------- #
# Exclusao — apenas Pastor
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
def test_pastor_deletes_file(tenant_client, church_a):
    """Pastor exclui: 302 -> lista, o FileAsset some e gera AuditLog 'delete'."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        asset = _upload(uploaded_by_id=pastor.id)
        pk = asset.pk

    tenant_client.force_login(pastor)
    resp = tenant_client.post(_delete_url(pk))
    assert resp.status_code == 302
    assert resp['Location'] == LIST_URL

    with schema_context(church_a.schema_name):
        assert not FileAsset.objects.filter(pk=pk).exists()
        delete_logs = AuditLog.objects.filter(
            action='delete', model_name='FileAsset', object_id=str(pk)
        )
        assert delete_logs.count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    'roles', [['secretary'], ['leader'], ['treasurer'], ['member']]
)
def test_non_pastor_cannot_delete(tenant_client, church_a, roles):
    """Secretario/Lider/Tesoureiro/Membro => 403 (exclusao e Pastor-only, §3.8)."""
    user = _user(church_a, f'{roles[0]}@a.com', roles)
    with schema_context(church_a.schema_name):
        asset = _upload()
        pk = asset.pk

    tenant_client.force_login(user)
    resp = tenant_client.post(_delete_url(pk))
    assert resp.status_code == 403

    with schema_context(church_a.schema_name):
        assert FileAsset.objects.filter(pk=pk).exists()


@pytest.mark.django_db(transaction=True)
def test_delete_cross_tenant_returns_404(tenant_client, church_a, church_b):
    """Pastor de A nao exclui arquivo de B => 404 (RISK-001, sem vazar existencia)."""
    pastor_a = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_b.schema_name):
        asset_b = _upload()

    tenant_client.force_login(pastor_a)
    resp = tenant_client.post(_delete_url(asset_b.pk))
    assert resp.status_code == 404

    with schema_context(church_b.schema_name):
        assert FileAsset.objects.filter(pk=asset_b.pk).exists()

    # Id inexistente tambem -> 404.
    assert tenant_client.post(_delete_url(999999)).status_code == 404


# --------------------------------------------------------------------------- #
# Download escopado — fecha a pendencia do Bloco 3
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
def test_leader_cannot_download_out_of_scope(tenant_client, church_a):
    """Lider NAO baixa arquivo fora do seu escopo => 404 (fecha Bloco 3)."""
    leader = _user(church_a, 'leader@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        person = Person.objects.create(name='Lider', user_id=leader.id)
        led = Community.objects.create(name='Minha')
        led.leaders.add(person)
        other = Community.objects.create(name='Alheia')
        mine = _upload(related_model='community', related_object_id=str(led.pk))
        not_mine = _upload(related_model='community', related_object_id=str(other.pk))

    tenant_client.force_login(leader)
    # No escopo -> 200.
    assert tenant_client.get(_download_url(mine.pk)).status_code == 200
    # Fora do escopo -> 404 (sem revelar existencia).
    assert tenant_client.get(_download_url(not_mine.pk)).status_code == 404


@pytest.mark.django_db(transaction=True)
def test_pastor_downloads_any_file(tenant_client, church_a):
    """Pastor baixa qualquer arquivo do tenant (escopo curto-circuitado)."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        asset = _upload(related_model='community', related_object_id='999')

    tenant_client.force_login(pastor)
    resp = tenant_client.get(_download_url(asset.pk))
    assert resp.status_code == 200
    assert b''.join(resp.streaming_content) == PDF_BYTES
