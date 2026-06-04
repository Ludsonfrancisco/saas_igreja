"""Sprint 3 / Frente 1 — model `Community` (TECH_SPEC §5.5).

Prova o `__str__` e o `SET_NULL` do `leader`: anonimizar/apagar a Pessoa-líder não
apaga a comunidade (RN-007). Roda no schema do tenant (`in_tenant_a`).
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
def test_community_leader_set_null_on_person_delete(in_tenant_a):
    """Apagar a Pessoa-líder zera `leader` (SET_NULL) — comunidade preservada."""
    leader = Person.objects.create(name='Pr. Lucas')
    community = Community.objects.create(name='Celula Sul', leader=leader)

    leader.delete()
    community.refresh_from_db()

    assert community.leader is None
    assert Community.objects.filter(pk=community.pk).exists()
