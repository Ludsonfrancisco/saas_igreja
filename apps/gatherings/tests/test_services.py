"""Sprint 4 / Frente 1 — service de Encontros (barreira tipo×papel×escopo, §3.6).

Testa a regra de negócio pura (`allowed_types` / `create_gathering`) dentro do
schema do tenant, sem passar pela camada HTTP. O ator (`User`) é público; o
`Community`/`Gathering` vivem no schema do tenant (TENANT-04).
"""

import datetime

import pytest
from django.core.exceptions import ValidationError
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.communities.models import Community
from apps.gatherings import services
from apps.gatherings.models import Gathering

GOOD_PASSWORD = 'Senha@123'
TODAY = datetime.date(2026, 6, 10)


def _make_user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


# --- allowed_types -----------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_allowed_types_pastor_sees_all(church_a):
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        types = services.allowed_types(pastor, church_a)
    assert set(types) == {
        Gathering.Type.WORSHIP,
        Gathering.Type.COMMUNITY,
        Gathering.Type.EVENT,
        Gathering.Type.MEETING,
    }


@pytest.mark.django_db(transaction=True)
def test_allowed_types_secretary_is_admin_like_pastor(church_a):
    """OD-019: Secretário = admin; vê todos os tipos (incl. WORSHIP)."""
    sec = _make_user(church_a, 'sec@a.com', ['secretary'])
    with schema_context(church_a.schema_name):
        types = services.allowed_types(sec, church_a)
    assert Gathering.Type.WORSHIP in types
    assert Gathering.Type.COMMUNITY in types


@pytest.mark.django_db(transaction=True)
def test_allowed_types_leader_without_community_has_no_worship_no_community(church_a):
    leader = _make_user(church_a, 'leader@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        types = services.allowed_types(leader, church_a)
    assert Gathering.Type.WORSHIP not in types
    assert Gathering.Type.COMMUNITY not in types
    assert set(types) == {Gathering.Type.EVENT, Gathering.Type.MEETING}


@pytest.mark.django_db(transaction=True)
def test_allowed_types_community_leader_gets_community(church_a):
    leader = _make_user(church_a, 'leader@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        person = Person_factory(leader.id)
        community = Community.objects.create(name='Celula')
        community.leaders.add(person)
        types = services.allowed_types(leader, church_a)
    assert Gathering.Type.COMMUNITY in types
    assert Gathering.Type.WORSHIP not in types


@pytest.mark.django_db(transaction=True)
def test_allowed_types_community_hidden_when_church_has_no_communities(church_a):
    church_a.has_communities = False
    church_a.save()
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        types = services.allowed_types(pastor, church_a)
    assert Gathering.Type.COMMUNITY not in types
    assert Gathering.Type.WORSHIP in types


# --- create_gathering: barreira ----------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_leader_cannot_create_worship(church_a):
    leader = _make_user(church_a, 'leader@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        with pytest.raises(ValidationError):
            services.create_gathering(
                church=church_a,
                user=leader,
                gathering_type=Gathering.Type.WORSHIP,
                date=TODAY,
            )


@pytest.mark.django_db(transaction=True)
def test_leader_cannot_create_gathering_rn018(church_a):
    """RN-018 (Comunidades v2): criar encontro é só Pastor/Secretário. Mesmo na
    própria comunidade, o Líder é recusado pelo service (defesa em profundidade)."""
    leader = _make_user(church_a, 'leader@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        person = Person_factory(leader.id)
        mine = Community.objects.create(name='Minha')
        mine.leaders.add(person)
        with pytest.raises(ValidationError):
            services.create_gathering(
                church=church_a,
                user=leader,
                gathering_type=Gathering.Type.COMMUNITY,
                date=TODAY,
                community=mine,
            )


@pytest.mark.django_db(transaction=True)
def test_leader_cannot_create_community_gathering_of_other_community(church_a):
    leader = _make_user(church_a, 'leader@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        person = Person_factory(leader.id)
        mine = Community.objects.create(name='Minha')
        mine.leaders.add(person)
        other = Community.objects.create(name='Outra')
        with pytest.raises(ValidationError):
            services.create_gathering(
                church=church_a,
                user=leader,
                gathering_type=Gathering.Type.COMMUNITY,
                date=TODAY,
                community=other,
            )


@pytest.mark.django_db(transaction=True)
def test_community_gathering_requires_community(church_a):
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        with pytest.raises(ValidationError):
            services.create_gathering(
                church=church_a,
                user=pastor,
                gathering_type=Gathering.Type.COMMUNITY,
                date=TODAY,
                community=None,
            )


@pytest.mark.django_db(transaction=True)
def test_non_community_type_ignores_community(church_a):
    """Um EVENT nunca guarda comunidade, mesmo se uma for passada."""
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        community = Community.objects.create(name='Celula')
        gathering = services.create_gathering(
            church=church_a,
            user=pastor,
            gathering_type=Gathering.Type.EVENT,
            date=TODAY,
            community=community,
        )
        assert gathering.community_id is None


def Person_factory(user_id):
    """Cria uma Person-líder vinculada ao `user_id` (atalho dos testes)."""
    from apps.people.models import Person

    return Person.objects.create(name='Lider', user_id=user_id)
