"""E2E do shell de navegação Athos v3 (Sprint 6.6 — gate de browser).

Valida o comportamento do shell "Painel Oikonos" (`templates/app_base.html`):

- Mobile (360×640): a sidebar flutuante fica escondida; o HAMBÚRGUER abre um DRAWER
  off-canvas (Alpine `x-data="{ open }"`), que fecha por TRÊS caminhos — botão X,
  clique no overlay e tecla Escape — e fecha ao navegar por um link.
- Desktop (1280×900): a sidebar fixa aparece e o hambúrguer some.

JS real (Alpine + transições) — por isso Playwright. O drawer usa `x-show`+`x-cloak`
(display:none quando fechado), então `state='visible'/'hidden'` reflete o estado.
"""

import pytest

from apps.e2e.conftest import login

DRAWER = '#mobile-drawer'
HAMBURGER = 'button[aria-label="Abrir menu de navegação"]'
CLOSE_BTN = 'button[aria-label="Fechar menu"]'
DESKTOP_SIDEBAR = 'aside[aria-label="Navegação principal"]'


def _open_drawer(page):
    page.click(HAMBURGER)
    page.locator(DRAWER).wait_for(state='visible')


@pytest.mark.django_db(transaction=True)
def test_mobile_drawer_open_and_close_paths(page, e2e):
    """Mobile: hambúrguer abre o drawer; fecha por X, overlay e Escape."""
    ls = e2e['live_server']
    page.set_viewport_size({'width': 360, 'height': 640})
    login(page, ls, 'pastor@e2e.com')

    drawer = page.locator(DRAWER)
    # Estado inicial: hambúrguer visível, drawer escondido.
    assert page.locator(HAMBURGER).is_visible()
    drawer.wait_for(state='hidden')

    # 1) Fecha pelo botão X.
    _open_drawer(page)
    page.click(CLOSE_BTN)
    drawer.wait_for(state='hidden')

    # 2) Fecha clicando no overlay (área fora do drawer de 270px — x=340).
    _open_drawer(page)
    page.mouse.click(340, 300)
    drawer.wait_for(state='hidden')

    # 3) Fecha com Escape.
    _open_drawer(page)
    page.keyboard.press('Escape')
    drawer.wait_for(state='hidden')


@pytest.mark.django_db(transaction=True)
def test_mobile_drawer_navigates_and_closes(page, e2e):
    """Mobile: clicar num link do drawer navega e fecha o menu (nav fecha no clique)."""
    ls = e2e['live_server']
    page.set_viewport_size({'width': 360, 'height': 640})
    login(page, ls, 'pastor@e2e.com')

    _open_drawer(page)
    page.locator(DRAWER).get_by_text('Encontros', exact=True).click()
    page.wait_for_load_state('networkidle')

    assert page.url.rstrip('/').endswith('/encontros')
    # Após navegar (full load), o drawer volta ao estado fechado.
    page.locator(DRAWER).wait_for(state='hidden')


@pytest.mark.django_db(transaction=True)
def test_desktop_sidebar_visible_without_hamburger(page, e2e):
    """Desktop (lg+): sidebar fixa visível e hambúrguer escondido."""
    ls = e2e['live_server']
    page.set_viewport_size({'width': 1280, 'height': 900})
    login(page, ls, 'pastor@e2e.com')

    assert page.locator(DESKTOP_SIDEBAR).is_visible()
    assert not page.locator(HAMBURGER).is_visible()
