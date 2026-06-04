"""Sprint 3 / Frente 3 (Bloco 2) — service de Comunidade (plano + has_communities)."""

import pytest
from django.core.exceptions import ValidationError

from apps.communities import services
from apps.communities.models import Community
from apps.tenants.models import Plan


@pytest.mark.django_db(transaction=True)
def test_create_community_respects_plan_limit(in_tenant_a, monkeypatch):
    """Atingido `max_communities` do plano -> recusa (limite reduzido p/ 2)."""
    monkeypatch.setitem(Plan.PLAN_LIMITS['free'], 'max_communities', 2)

    services.create_community(church=in_tenant_a, name='C1')
    services.create_community(church=in_tenant_a, name='C2')
    with pytest.raises(ValidationError):
        services.create_community(church=in_tenant_a, name='C3')

    assert Community.objects.count() == 2


@pytest.mark.django_db(transaction=True)
def test_create_community_blocked_when_has_communities_false(in_tenant_a):
    """Igreja sem comunidades não cria comunidade (barreira de service)."""
    in_tenant_a.has_communities = False
    in_tenant_a.save()

    with pytest.raises(ValidationError):
        services.create_community(church=in_tenant_a, name='X')

    assert Community.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_create_community_with_leaders(in_tenant_a):
    """OD-019: cria já com vários líderes (M2M)."""
    from apps.people.models import Person

    a = Person.objects.create(name='Lider A')
    b = Person.objects.create(name='Lider B')

    community = services.create_community(church=in_tenant_a, name='C', leaders=[a, b])
    assert community.leaders.count() == 2
