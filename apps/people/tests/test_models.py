"""Sprint 3 / Frente 1 — model `Person` e suas relações (TECH_SPEC §5.4).

Foundational: prova os contratos do model antes das regras de service (Frente 2):
defaults, `__str__`, FK `community` com `SET_NULL` e M2M `ministries`. O `SET_NULL`
é requisito LGPD (RN-007): apagar a comunidade NÃO apaga a pessoa.

Models de TENANT_APPS vivem no schema do tenant — os testes rodam dentro de
`in_tenant_a` (fixture do conftest).
"""

import pytest

from apps.communities.models import Community
from apps.ministries.models import Ministry
from apps.people.models import Person


@pytest.mark.django_db(transaction=True)
def test_person_defaults_and_str(in_tenant_a):
    """Person nova: status VISITOR, sem consent/anonimização, __str__ = nome."""
    person = Person.objects.create(name='Maria Silva')

    assert person.status == Person.Status.VISITOR
    assert person.consent_given_at is None
    assert person.anonymized_at is None
    assert str(person) == 'Maria Silva'


@pytest.mark.django_db(transaction=True)
def test_person_community_fk_set_null_on_delete(in_tenant_a):
    """Apagar a comunidade zera o FK na pessoa (SET_NULL); pessoa fica (RN-007)."""
    community = Community.objects.create(name='Celula Centro')
    person = Person.objects.create(name='Joao', community=community)

    community.delete()
    person.refresh_from_db()

    assert person.community is None
    assert Person.objects.filter(pk=person.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_person_ministries_m2m(in_tenant_a):
    """M2M Pessoa↔Ministério dos dois lados (reverse `ministry.members`)."""
    person = Person.objects.create(name='Ana')
    louvor = Ministry.objects.create(name='Louvor')
    midia = Ministry.objects.create(name='Midia')

    person.ministries.add(louvor, midia)

    assert set(person.ministries.values_list('name', flat=True)) == {'Louvor', 'Midia'}
    assert person in louvor.members.all()
