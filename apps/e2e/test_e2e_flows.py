"""E2E Playwright dos fluxos-chave por papel (Sprint 6.5 / Bloco 6).

Fluxos (SPRINTS Bloco 6): login, marcar presença (mobile), criar pessoa (desktop),
aprovar exceção de conflito. Rodam contra o `live_server` no tenant E2E (conftest).
JS real (HTMX/Alpine) — por isso Playwright, não o test client.
"""

import datetime

import pytest
from django_tenants.utils import schema_context

from apps.e2e.conftest import E2E_SCHEMA, login

FUTURE = datetime.date.today() + datetime.timedelta(days=14)


@pytest.mark.django_db(transaction=True)
def test_login_flow(page, e2e):
    """Login por email → cai na home "Painel Oikonos" (LOGIN_REDIRECT_URL='/').

    Pós-pivô da Sprint 6.6 a landing pós-login é a home nova em `/` (RF-102/103),
    não mais `/painel` (que virou métricas por papel, §3.9)."""
    ls = e2e['live_server']
    login(page, ls, 'pastor@e2e.com')
    assert page.url.rstrip('/') == ls.url.rstrip('/')  # caiu na home (/)
    assert 'Painel Oikonos' in page.inner_text('body')


@pytest.mark.django_db(transaction=True)
def test_criar_pessoa_desktop(page, e2e):
    """Pastor cria uma pessoa pelo formulário (desktop)."""
    from apps.people.models import Person

    ls = e2e['live_server']
    page.set_viewport_size({'width': 1280, 'height': 900})
    login(page, ls, 'pastor@e2e.com')

    page.goto(f'{ls.url}/pessoas/nova/')
    page.fill('input[name="name"]', 'Maria E2E')
    page.click('button[type="submit"]')
    page.wait_for_load_state('networkidle')

    with schema_context(E2E_SCHEMA):
        assert Person.objects.filter(name='Maria E2E').exists()


@pytest.mark.django_db(transaction=True)
def test_marcar_presenca_mobile(page, e2e):
    """Líder marca presença em lote (mobile) → Attendance persistida."""
    from apps.gatherings.models import Attendance, Gathering
    from apps.people.models import Person

    ls = e2e['live_server']
    with schema_context(E2E_SCHEMA):
        person = Person.objects.create(name='Ana E2E', status='member')
        gathering = Gathering.objects.create(
            gathering_type='worship', date=FUTURE, title='Culto E2E'
        )
        gid, pid = gathering.pk, person.pk

    page.set_viewport_size({'width': 360, 'height': 640})
    login(page, ls, 'pastor@e2e.com')

    page.goto(f'{ls.url}/encontros/{gid}/presenca/')
    # UI v3: o checkbox `present` é sr-only e alternado pela LABEL (toque na linha) —
    # clicar a label marca a presença, como um usuário real faz no mobile.
    page.click(f'label:has(input[name="present"][value="{pid}"])')
    page.click('button[type="submit"]')
    page.wait_for_load_state('networkidle')

    with schema_context(E2E_SCHEMA):
        assert Attendance.objects.filter(
            gathering_id=gid, person_id=pid, is_present=True
        ).exists()


@pytest.mark.django_db(transaction=True)
def test_aprovar_excecao(page, e2e):
    """Pastor aprova exceção de conflito com justificativa → 2ª escala criada."""
    from apps.gatherings.models import Gathering
    from apps.ministries.models import Ministry
    from apps.people.models import Person
    from apps.schedules.models import Schedule

    ls = e2e['live_server']
    with schema_context(E2E_SCHEMA):
        ministry = Ministry.objects.create(name='Louvor E2E')
        person = Person.objects.create(name='João E2E')
        person.ministries.add(ministry)
        g1 = Gathering.objects.create(
            gathering_type='worship', date=FUTURE, title='Culto A'
        )
        g2 = Gathering.objects.create(
            gathering_type='event', date=FUTURE, title='Evento B'
        )
        # 1ª escala (sem conflito); a 2ª na mesma data exige aprovação de exceção.
        Schedule.objects.create(ministry=ministry, person=person, gathering=g1)
        mid, pid, g2id = ministry.pk, person.pk, g2.pk

    page.set_viewport_size({'width': 1280, 'height': 900})
    login(page, ls, 'pastor@e2e.com')

    page.goto(f'{ls.url}/escalas/excecao/nova/')
    page.select_option('select[name="ministry"]', str(mid))
    page.select_option('select[name="person"]', str(pid))
    page.select_option('select[name="gathering"]', str(g2id))
    page.fill('textarea[name="justification"]', 'Voluntário disponível nos dois.')
    page.click('button[type="submit"]')
    page.wait_for_load_state('networkidle')

    with schema_context(E2E_SCHEMA):
        assert Schedule.objects.filter(person_id=pid, gathering_id=g2id).exists()
