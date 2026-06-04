"""Sprint 3 — model `Community` (TECH_SPEC §5.5 / OD-019).

Prova o `__str__` e o M2M `leaders` (OD-019): vários líderes por comunidade, e
apagar/anonimizar uma Pessoa-líder só remove o vínculo M2M (a comunidade
permanece, RN-007). Roda no schema do tenant (`in_tenant_a`).
"""

import pytest

from apps.communities.models import Community
from apps.people.models import Person


@pytest.mark.django_db(transaction=True)
def test_community_str(in_tenant_a):
    community = Community.objects.create(name='Celula Norte')
    assert str(community) == 'Celula Norte'
    assert community.is_active is True


@pytest.mark.django_db(transaction=True)
def test_community_multiple_leaders(in_tenant_a):
    """OD-019: uma comunidade pode ter VÁRIOS líderes (M2M)."""
    community = Community.objects.create(name='Celula Sul')
    a = Person.objects.create(name='Lider A')
    b = Person.objects.create(name='Lider B')

    community.leaders.add(a, b)

    assert set(community.leaders.values_list('name', flat=True)) == {
        'Lider A',
        'Lider B',
    }
    assert community in a.communities_led.all()  # reverse


@pytest.mark.django_db(transaction=True)
def test_deleting_leader_person_only_removes_link(in_tenant_a):
    """Apagar a Pessoa-líder remove o vínculo M2M; a comunidade permanece (RN-007)."""
    leader = Person.objects.create(name='Pr. Lucas')
    community = Community.objects.create(name='Celula Centro')
    community.leaders.add(leader)

    leader.delete()
    community.refresh_from_db()

    assert community.leaders.count() == 0
    assert Community.objects.filter(pk=community.pk).exists()
