"""Sprint 3 / Frente 1 — model `Ministry` (TECH_SPEC §5.5).

Prova o `__str__` e o `SET_NULL` do `coordinator`: apagar a Pessoa-coordenadora não
apaga o ministério (RN-007). Roda no schema do tenant (`in_tenant_a`).
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
def test_ministry_coordinator_set_null_on_person_delete(in_tenant_a):
    """Apagar a Pessoa-coordenadora zera `coordinator` (SET_NULL); ministério fica."""
    coordinator = Person.objects.create(name='Carla')
    ministry = Ministry.objects.create(name='Acolhimento', coordinator=coordinator)

    coordinator.delete()
    ministry.refresh_from_db()

    assert ministry.coordinator is None
    assert Ministry.objects.filter(pk=ministry.pk).exists()
