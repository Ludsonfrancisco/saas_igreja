"""Sprint 3 — model `Ministry` (TECH_SPEC §5.5 / OD-019).

Prova o `__str__` e o M2M `coordinators` (OD-019): vários coordenadores por
ministério, e apagar/anonimizar uma Pessoa-coordenadora só remove o vínculo M2M
(o ministério permanece, RN-007). Roda no schema do tenant (`in_tenant_a`).
"""

import pytest

from apps.ministries.models import Ministry
from apps.people.models import Person


@pytest.mark.django_db(transaction=True)
def test_ministry_str(in_tenant_a):
    ministry = Ministry.objects.create(name='Diaconia')
    assert str(ministry) == 'Diaconia'
    assert ministry.is_active is True


@pytest.mark.django_db(transaction=True)
def test_ministry_multiple_coordinators(in_tenant_a):
    """OD-019: um ministério pode ter VÁRIOS coordenadores (M2M)."""
    ministry = Ministry.objects.create(name='Louvor')
    a = Person.objects.create(name='Coord A')
    b = Person.objects.create(name='Coord B')

    ministry.coordinators.add(a, b)

    assert set(ministry.coordinators.values_list('name', flat=True)) == {
        'Coord A',
        'Coord B',
    }
    assert ministry in a.ministries_led.all()  # reverse


@pytest.mark.django_db(transaction=True)
def test_deleting_coordinator_person_only_removes_link(in_tenant_a):
    """Apagar a Pessoa-coordenadora remove o vínculo M2M; o ministério fica (RN-007)."""
    coordinator = Person.objects.create(name='Carla')
    ministry = Ministry.objects.create(name='Acolhimento')
    ministry.coordinators.add(coordinator)

    coordinator.delete()
    ministry.refresh_from_db()

    assert ministry.coordinators.count() == 0
    assert Ministry.objects.filter(pk=ministry.pk).exists()
