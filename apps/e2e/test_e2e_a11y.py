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
