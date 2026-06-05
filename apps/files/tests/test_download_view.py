"""Sprint 6 / Bloco 3 — download seguro por streaming + auditoria/seguranca.

OD-021: download e STREAMING pela view autenticada (nao URL assinada). Cobrimos:
- gate de papel (ACCESS_MATRIX §3.8): so papeis de igreja baixam; Platform Admin nao;
- isolamento de tenant: arquivo de outro tenant ou inexistente => 404 (sem vazar);
- "sem URL publica permanente": a resposta e streaming, sem redirect/`.url()`;
- delete de FileAsset auditado pelo mixin (nivel de objeto; a view de exclusao e
  Bloco 4);
- upload gera SecurityLog `sensitive_file_upload` (sinal novo);
- caminho feliz: 200 + bytes corretos + AuditLog 'read' + SecurityLog de download.

FileAsset vive no schema do tenant (TENANT-04) -> `schema_context` para ORM puro e
host `a.testserver`/`b.testserver` para requests. DDL de criar Church exige
`@pytest.mark.django_db(transaction=True)`.
"""

import pytest
from django.db import connection
from django.test import Client
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.core.models import AuditLog, SecurityLog
from apps.files import services

GOOD_PASSWORD = 'Senha@123'
PDF_BYTES = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< >>\nendobj\n'


@pytest.fixture
def tenant_client():
    client = Client(HTTP_HOST='a.testserver')
    yield client
    connection.set_schema_to_public()


def _user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


def _upload(uploaded_by_id=1):
    from django.core.files.uploadedfile import SimpleUploadedFile

    uploaded = SimpleUploadedFile('doc.pdf', PDF_BYTES, content_type='application/pdf')
    return services.upload_file(uploaded_file=uploaded, uploaded_by_id=uploaded_by_id)


def _download_url(pk):
    return f'/arquivos/{pk}/download/'


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    'roles,expected',
    [
        # Pastor/Secretario veem tudo -> baixam o arquivo geral (sem contexto).
        (['pastor'], 200),
        (['secretary'], 200),
        # Bloco 4: o escopo fino por contexto agora vale tambem no download. Um
        # arquivo GERAL (sem related_model) esta FORA do escopo de Lider/Tesoureiro
        # -> 404 (nao 403: nao revelamos a existencia, RISK-001). O 403 de papel so
        # sobra para quem nao tem papel de igreja algum (membro).
        (['leader'], 404),
        (['treasurer'], 404),
        (['member'], 403),
    ],
)
def test_download_requires_permission(tenant_client, church_a, roles, expected):
    """Gate de papel + escopo (ACCESS_MATRIX §3.8): membro 403; Lider/Tesoureiro
    sem contexto autorizado nao alcancam o arquivo geral (404, Bloco 4)."""
    user = _user(church_a, f'{roles[0]}@a.com', roles)
    with schema_context(church_a.schema_name):
        asset = _upload(uploaded_by_id=user.id)
    tenant_client.force_login(user)
    resp = tenant_client.get(_download_url(asset.pk))
    assert resp.status_code == expected


@pytest.mark.django_db(transaction=True)
def test_download_unauthorized_returns_404(tenant_client, church_a, church_b):
    """Arquivo de OUTRO tenant => 404 (nao 403): nao vazamos a existencia.

    RISK-001. O upload acontece no schema de B; o request chega no host de A, com
    um Pastor de A logado. O FileAsset de B nao existe no schema de A -> Http404.
    """
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_b.schema_name):
        asset_b = _upload(uploaded_by_id=999)
    tenant_client.force_login(pastor)

    resp = tenant_client.get(_download_url(asset_b.pk))
    assert resp.status_code == 404

    # Id inexistente tambem -> 404.
    assert tenant_client.get(_download_url(999999)).status_code == 404


@pytest.mark.django_db(transaction=True)
def test_no_permanent_public_url(tenant_client, church_a):
    """A resposta NAO contem URL publica do storage: e streaming, sem redirect.

    RNF-018 / RISK-005. Verificamos que (a) nao ha redirect (status 200, sem
    Location), (b) a resposta e streaming (`streaming=True`), e (c) o corpo nao
    expoe a URL do objeto no storage.
    """
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        asset = _upload(uploaded_by_id=pastor.id)
        storage_url = asset.file.url  # so para comparar; a view nunca a expoe

    tenant_client.force_login(pastor)
    resp = tenant_client.get(_download_url(asset.pk))

    assert resp.status_code == 200
    assert resp.streaming is True
    assert 'Location' not in resp
    body = b''.join(resp.streaming_content)
    assert body == PDF_BYTES
    # O corpo (bytes do PDF) jamais contem a URL do objeto no storage.
    assert storage_url.encode() not in body
    assert resp['Content-Type'] == 'application/pdf'
    assert 'attachment' in resp['Content-Disposition']


@pytest.mark.django_db(transaction=True)
def test_download_happy_path_audited(tenant_client, church_a):
    """200 + bytes corretos + AuditLog 'read' + SecurityLog de download."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        asset = _upload(uploaded_by_id=pastor.id)

    tenant_client.force_login(pastor)
    resp = tenant_client.get(_download_url(asset.pk))
    assert resp.status_code == 200
    assert b''.join(resp.streaming_content) == PDF_BYTES

    with schema_context(church_a.schema_name):
        read_logs = AuditLog.objects.filter(
            action='read', model_name='FileAsset', object_id=str(asset.pk)
        )
        assert read_logs.count() == 1
        assert read_logs.first().user_id == pastor.id

        dl_logs = SecurityLog.objects.filter(event_type='sensitive_file_download')
        assert dl_logs.count() == 1
        log = dl_logs.first()
        assert log.user_id == pastor.id
        assert log.payload['file_id'] == asset.pk
        # Sem PII no payload (TENANT-07): nao guardamos email/telefone.
        assert 'email' not in log.payload


@pytest.mark.django_db(transaction=True)
def test_delete_file_audited(church_a):
    """Apagar um FileAsset gera AuditLog action='delete' (via mixin global).

    Nivel de objeto/model — a VIEW de exclusao e Bloco 4.
    """
    with schema_context(church_a.schema_name):
        asset = _upload(uploaded_by_id=1)
        pk = asset.pk
        asset.delete()

        delete_logs = AuditLog.objects.filter(
            action='delete', model_name='FileAsset', object_id=str(pk)
        )
        assert delete_logs.count() == 1


@pytest.mark.django_db(transaction=True)
def test_file_upload_security_logged(church_a):
    """`upload_file` gera SecurityLog 'sensitive_file_upload' via o sinal novo."""
    with schema_context(church_a.schema_name):
        asset = _upload(uploaded_by_id=42)

        logs = SecurityLog.objects.filter(event_type='sensitive_file_upload')
        assert logs.count() == 1
        log = logs.first()
        assert log.user_id == 42
        assert log.payload['file_id'] == asset.pk
        assert log.payload['mime_type'] == 'application/pdf'
        assert log.payload['size_bytes'] == asset.size_bytes
        # Sem PII no payload (TENANT-07).
        assert 'email' not in log.payload
