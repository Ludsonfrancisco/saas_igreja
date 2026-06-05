"""Gate de permissões por papel (P-ARQ-08 / ACCESS_MATRIX) — atualizado p/ OD-019.

`test_permissions_matrix` (TEST_STRATEGY §6.2): uma linha por célula (papel × view)
das views autenticadas. Cobre Pastor / Secretário / Líder-Coordenador / Membro.

Padrões de barreira (a checagem roda no `dispatch`, então um GET basta):
- **admin** (Pastor+Secretário): criar pessoa/comunidade/ministério, importar CSV,
  Gestão de Acessos, convites. Líder/Membro → 403.
- **staff escopado** (Pastor+Secretário+Líder/Coord): listar pessoas/comunidades/
  ministérios. Membro → 403. (Líder vê escopado; aqui só checamos o gate de papel.)
- **login-only**: Segurança da conta — qualquer papel autenticado.

Conforme novas views/ações nascem, acrescente as células.
`transaction=True` por causa do DDL de criar Church.
"""

import pytest
from django.db import connection
from django.test import Client

from apps.accounts.models import User

GOOD_PASSWORD = 'Senha@123'

USER_LIST = '/configuracoes/usuarios/'
INVITE_LIST = '/configuracoes/convites/'
INVITE_CREATE = '/configuracoes/convites/novo/'
PEOPLE_LIST = '/pessoas/'
PEOPLE_CREATE = '/pessoas/nova/'
PEOPLE_IMPORT = '/pessoas/importar/'
COMM_LIST = '/comunidades/'
COMM_CREATE = '/comunidades/nova/'
MIN_LIST = '/ministerios/'
MIN_CREATE = '/ministerios/novo/'
GATHERING_LIST = '/encontros/'
GATHERING_CREATE = '/encontros/novo/'
SCHEDULE_LIST = '/escalas/'
SCHEDULE_CREATE = '/escalas/nova/'
SCHEDULE_EXCEPTION = '/escalas/excecao/nova/'
FILES_LIST = '/arquivos/'
DASHBOARD_PASTOR = '/painel/'
DASHBOARD_LEADER = '/painel/comunidade/'
DASHBOARD_COORDINATOR = '/painel/ministerio/'
ACCOUNT_SECURITY = '/contas/seguranca/'


def _admin(url):
    """Pastor + Secretário liberados; Líder e Membro negados."""
    return [
        ('pastor', url, 200),
        ('secretary', url, 200),
        ('leader', url, 403),
        ('member', url, 403),
    ]


def _staff_scoped(url):
    """Pastor + Secretário + Líder/Coordenador liberados (escopo refinado no qs)."""
    return [
        ('pastor', url, 200),
        ('secretary', url, 200),
        ('leader', url, 200),
        ('member', url, 403),
    ]


def _pastor_or_coordinator(url):
    """Pastor + Líder/Coordenador liberados; Secretário NEGADO (Sprint 5 §3.7).

    O Secretário é admin no CRUD de escala, mas NÃO aprova exceção de conflito —
    daí 403 aqui, ao contrário de `_staff_scoped`. A competência fina por
    ministério (Coordenador só o seu) é revalidada no service.
    """
    return [
        ('pastor', url, 200),
        ('secretary', url, 403),
        ('leader', url, 200),
        ('member', url, 403),
    ]


def _files_access(url):
    """Acesso a arquivos (ACCESS_MATRIX §3.8): Pastor/Secretário/Líder/Tesoureiro
    liberados (escopo fino por contexto refinado no queryset); Membro → 403.

    Inclui `treasurer` — único da matriz de Arquivos (contexto financeiro). O gate
    é só de papel; o recorte por comunidade/ministério/financeiro é testado em
    apps/files/tests.
    """
    return [
        ('pastor', url, 200),
        ('secretary', url, 200),
        ('leader', url, 200),
        ('treasurer', url, 200),
        ('member', url, 403),
    ]


def _pastor_only(url):
    """Pastor exclusivo (ACCESS_MATRIX §3.9 "Dashboard completo"): só Pastor 200.

    Difere de `_admin`: aqui o Secretário também é NEGADO (`PastorRequiredMixin`,
    não `LeaderOrPastorMixin`)."""
    return [
        ('pastor', url, 200),
        ('secretary', url, 403),
        ('leader', url, 403),
        ('member', url, 403),
    ]


def _login_only(url):
    return [(role, url, 200) for role in ('pastor', 'secretary', 'leader', 'member')]


PERMISSION_CASES = (
    _admin(USER_LIST)
    + _admin(INVITE_LIST)
    + _admin(INVITE_CREATE)
    + _staff_scoped(PEOPLE_LIST)
    + _admin(PEOPLE_CREATE)
    + _admin(PEOPLE_IMPORT)
    + _staff_scoped(COMM_LIST)
    + _admin(COMM_CREATE)
    + _staff_scoped(MIN_LIST)
    + _admin(MIN_CREATE)
    # Encontros (§3.6): Listar e Criar liberados a Pastor/Secretário/Líder
    # (Líder/Coord criam EVENT/MEETING; o tipo fino é filtrado no form/service).
    # Membro → 403. O escopo por encontro (detalhe/editar/presença, com pk) é
    # coberto em apps/gatherings/tests.
    + _staff_scoped(GATHERING_LIST)
    + _staff_scoped(GATHERING_CREATE)
    # Escalas (§3.7): Listar/Criar liberados a Pastor/Secretário/Líder-Coordenador
    # (escopo por ministério refinado no qs/form). A aprovação de EXCEÇÃO de
    # conflito exclui o Secretário — só Pastor ou Coordenador.
    + _staff_scoped(SCHEDULE_LIST)
    + _staff_scoped(SCHEDULE_CREATE)
    + _pastor_or_coordinator(SCHEDULE_EXCEPTION)
    # Arquivos (§3.8): Listar liberado a Pastor/Secretário/Líder/Tesoureiro (escopo
    # por contexto no qs). Download/Excluir são rotas com `pk` (escopo fino + Pastor-
    # only) → testadas em apps/files/tests, não nesta matriz de rotas sem objeto.
    + _files_access(FILES_LIST)
    # Dashboard (§3.9): completo = SÓ Pastor; simplificados (comunidade/ministério)
    # = Pastor/Secretário/Líder-Coordenador (escopo no service). Membro → 403.
    + _pastor_only(DASHBOARD_PASTOR)
    + _staff_scoped(DASHBOARD_LEADER)
    + _staff_scoped(DASHBOARD_COORDINATOR)
    + _login_only(ACCOUNT_SECURITY)
)


@pytest.fixture
def tenant_client():
    client = Client(HTTP_HOST='a.testserver')
    yield client
    connection.set_schema_to_public()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('role,url,expected', PERMISSION_CASES)
def test_permissions_matrix(tenant_client, church_a, role, url, expected):
    """Cada célula (papel × view): o status confirma a barreira de papel."""
    user = User.objects.create_user(
        email=f'{role}@a.com', password=GOOD_PASSWORD, roles=[role], church=church_a
    )
    tenant_client.force_login(user)

    resp = tenant_client.get(url)
    assert resp.status_code == expected
