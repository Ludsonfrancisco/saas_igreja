"""UI de upload de arquivo (RF-065/067 · ACCESS_MATRIX §3.8).

Cobre a `FileUploadView` (quick win pré-7): Pastor/Secretário enviam (geral +
contexto opcional via select agrupado); Líder/Membro => 403. A validação pesada
(MIME/tamanho) vive em `services.upload_file` e é testada à parte — aqui o foco é a
barreira de papel e a tradução do `context` em `related_model`/`related_object_id`.

Templates reais são do frontend; injetamos stubs via locmem e assertamos sobre o
efeito no banco (FileAsset criado) + status, não sobre o HTML.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client, override_settings
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.communities.models import Community
from apps.files.models import FileAsset

GOOD_PASSWORD = 'Senha@123'
PDF_BYTES = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< >>\nendobj\n'
UPLOAD_URL = '/arquivos/enviar/'

stub_templates = override_settings(
    TEMPLATES=[
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [],
            'APP_DIRS': False,
            'OPTIONS': {
                'loaders': [
                    (
                        'django.template.loaders.locmem.Loader',
                        {
                            'files/file_upload_form.html': 'ok',
                            'files/file_list.html': 'ok',
                        },
                    ),
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


def _pdf():
    return SimpleUploadedFile('doc.pdf', PDF_BYTES, content_type='application/pdf')


@stub_templates
@pytest.mark.django_db(transaction=True)
def test_pastor_uploads_general_file(tenant_client, church_a):
    """Pastor envia arquivo geral => 302 + FileAsset criado (sem contexto)."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    tenant_client.force_login(pastor)

    resp = tenant_client.post(UPLOAD_URL, {'file': _pdf(), 'context': ''})
    assert resp.status_code == 302
    with schema_context(church_a.schema_name):
        asset = FileAsset.objects.get()
        assert asset.uploaded_by_id == pastor.id
        assert asset.related_model == ''
        assert asset.related_object_id == ''


@stub_templates
@pytest.mark.django_db(transaction=True)
def test_upload_with_community_context(tenant_client, church_a):
    """O `context` 'community:<id>' grava related_model/related_object_id (§3.8)."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        community = Community.objects.create(name='Célula Alfa')
        cid = community.pk
    tenant_client.force_login(pastor)

    resp = tenant_client.post(
        UPLOAD_URL, {'file': _pdf(), 'context': f'community:{cid}'}
    )
    assert resp.status_code == 302
    with schema_context(church_a.schema_name):
        asset = FileAsset.objects.get()
        assert asset.related_model == 'community'
        assert asset.related_object_id == str(cid)


@stub_templates
@pytest.mark.django_db(transaction=True)
def test_secretary_can_upload(tenant_client, church_a):
    """Secretário envia (age como Pastor, OD-019)."""
    secretary = _user(church_a, 'sec@a.com', ['secretary'])
    tenant_client.force_login(secretary)
    resp = tenant_client.post(UPLOAD_URL, {'file': _pdf(), 'context': ''})
    assert resp.status_code == 302
    with schema_context(church_a.schema_name):
        assert FileAsset.objects.count() == 1


@stub_templates
@pytest.mark.django_db(transaction=True)
def test_leader_cannot_upload(tenant_client, church_a):
    """Líder não envia pela tela geral (upload geral é Pastor/Secretário) => 403."""
    leader = _user(church_a, 'leader@a.com', ['leader'])
    tenant_client.force_login(leader)
    assert tenant_client.get(UPLOAD_URL).status_code == 403
    resp = tenant_client.post(UPLOAD_URL, {'file': _pdf(), 'context': ''})
    assert resp.status_code == 403
    with schema_context(church_a.schema_name):
        assert FileAsset.objects.count() == 0
