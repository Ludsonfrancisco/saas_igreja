"""a11y automatizada (axe-core / WCAG 2 A+AA) das telas principais (Bloco 6).

Injeta o axe-core vendorizado (apps/e2e/axe.min.js) na página real (Playwright) e
falha se houver violação de impacto `serious`/`critical`. Cobre páginas públicas e
autenticadas (reusa a sessão do login).
"""

import pathlib

import pytest

from apps.e2e.conftest import login

_AXE = (pathlib.Path(__file__).parent / 'axe.min.js').read_text()
_FAIL_IMPACT = ('serious', 'critical')


def _violations(page):
    page.add_script_tag(content=_AXE)
    page.wait_for_function('() => !!window.axe')
    results = page.evaluate(
        "async () => await axe.run(document, "
        "{runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa']}})"
    )
    return [v for v in results['violations'] if v['impact'] in _FAIL_IMPACT]


def _summary(viols):
    return [
        {'id': v['id'], 'impact': v['impact'], 'nodes': len(v['nodes'])} for v in viols
    ]


@pytest.mark.django_db(transaction=True)
def test_a11y_login(page, e2e):
    page.goto(f"{e2e['live_server'].url}/contas/login/")
    v = _violations(page)
    assert not v, f'WCAG AA (login): {_summary(v)}'


@pytest.mark.django_db(transaction=True)
def test_a11y_home(page, e2e):
    """Home v3 "Painel Oikonos" (`/`, Sprint 6.6) — gate de a11y do shell novo."""
    ls = e2e['live_server']
    login(page, ls, 'pastor@e2e.com')
    page.goto(f'{ls.url}/')
    v = _violations(page)
    assert not v, f'WCAG AA (home v3): {_summary(v)}'


@pytest.mark.django_db(transaction=True)
def test_a11y_dashboard(page, e2e):
    ls = e2e['live_server']
    login(page, ls, 'pastor@e2e.com')
    page.goto(f'{ls.url}/painel/')
    v = _violations(page)
    assert not v, f'WCAG AA (painel): {_summary(v)}'


@pytest.mark.django_db(transaction=True)
def test_a11y_gatherings(page, e2e):
    """Encontros (`/encontros/`) com o calendário wirado (RF-102/OD-030)."""
    ls = e2e['live_server']
    login(page, ls, 'pastor@e2e.com')
    page.goto(f'{ls.url}/encontros/')
    v = _violations(page)
    assert not v, f'WCAG AA (encontros): {_summary(v)}'


@pytest.mark.django_db(transaction=True)
def test_a11y_ministry_list(page, e2e):
    """Ministérios (lista) com cards + barra "Saúde do Ministério" (GAP, RF-121)."""
    from django_tenants.utils import schema_context

    from apps.e2e.conftest import E2E_SCHEMA
    from apps.ministries.models import Ministry

    ls = e2e['live_server']
    with schema_context(E2E_SCHEMA):
        Ministry.objects.create(name='Louvor E2E', volunteers_needed=3)

    login(page, ls, 'pastor@e2e.com')
    page.goto(f'{ls.url}/ministerios/')
    v = _violations(page)
    assert not v, f'WCAG AA (ministérios): {_summary(v)}'


@pytest.mark.django_db(transaction=True)
def test_a11y_community_list(page, e2e):
    """Comunidades (lista) com os cards + gráfico de barra "Frequência por célula" (RF-119)."""
    from django_tenants.utils import schema_context

    from apps.communities.models import Community
    from apps.e2e.conftest import E2E_SCHEMA

    ls = e2e['live_server']
    with schema_context(E2E_SCHEMA):
        Community.objects.create(name='Célula E2E')

    login(page, ls, 'pastor@e2e.com')
    page.goto(f'{ls.url}/comunidades/')
    v = _violations(page)
    assert not v, f'WCAG AA (comunidades): {_summary(v)}'


@pytest.mark.django_db(transaction=True)
def test_a11y_community_session(page, e2e):
    """Comunidades v2 (RF-108): detalhe da célula + tela de lançamento de presença."""
    import datetime

    from django_tenants.utils import schema_context

    from apps.communities.models import Community
    from apps.e2e.conftest import E2E_SCHEMA
    from apps.gatherings.models import Gathering
    from apps.people.models import Person

    ls = e2e['live_server']
    with schema_context(E2E_SCHEMA):
        cell = Community.objects.create(name='Célula E2E')
        Person.objects.create(name='Membro E2E', community=cell)
        gathering = Gathering.objects.create(
            gathering_type=Gathering.Type.COMMUNITY,
            date=datetime.date.today(),
            community=cell,
            title='Reunião E2E',
        )
        cid, gid = cell.pk, gathering.pk

    login(page, ls, 'pastor@e2e.com')
    page.goto(f'{ls.url}/comunidades/{cid}/')
    v = _violations(page)
    assert not v, f'WCAG AA (detalhe da célula): {_summary(v)}'

    page.goto(f'{ls.url}/comunidades/{cid}/lancamento/{gid}/')
    v = _violations(page)
    assert not v, f'WCAG AA (lançamento da célula): {_summary(v)}'


@pytest.mark.django_db(transaction=True)
def test_a11y_schedule_events(page, e2e):
    """Escalas v2 (RF-111/112): tela por evento + modal de escalação aberto."""
    import datetime

    from django_tenants.utils import schema_context

    from apps.e2e.conftest import E2E_SCHEMA
    from apps.gatherings.models import Gathering
    from apps.ministries.models import Ministry
    from apps.people.models import Person

    ls = e2e['live_server']
    with schema_context(E2E_SCHEMA):
        ministry = Ministry.objects.create(name='Louvor E2E')
        member = Person.objects.create(name='Ana E2E')
        member.ministries.add(ministry)
        Gathering.objects.create(
            gathering_type=Gathering.Type.WORSHIP,
            date=datetime.date.today(),
            title='Culto E2E',
        )

    login(page, ls, 'pastor@e2e.com')
    page.goto(f'{ls.url}/escalas/eventos/')
    v = _violations(page)
    assert not v, f'WCAG AA (escalas por evento): {_summary(v)}'

    # Abre o modal de escalação e revalida com o diálogo aberto. Espera a transição
    # de fade do Alpine terminar (opacity 0→1, 200ms) — senão o axe mede cores
    # MESCLADAS (mid-fade) e acusa falso contraste.
    page.locator('button:has-text("Escalar")').first.click()
    page.wait_for_selector('input[name="person_ids"]')
    page.wait_for_timeout(500)
    v = _violations(page)
    assert not v, f'WCAG AA (modal de escalação): {_summary(v)}'


@pytest.mark.django_db(transaction=True)
def test_a11y_person_list(page, e2e):
    ls = e2e['live_server']
    login(page, ls, 'pastor@e2e.com')
    page.goto(f'{ls.url}/pessoas/')
    v = _violations(page)
    assert not v, f'WCAG AA (lista de pessoas): {_summary(v)}'


@pytest.mark.django_db(transaction=True)
def test_a11y_person_form(page, e2e):
    ls = e2e['live_server']
    login(page, ls, 'pastor@e2e.com')
    page.goto(f'{ls.url}/pessoas/nova/')
    v = _violations(page)
    assert not v, f'WCAG AA (form de pessoa): {_summary(v)}'
