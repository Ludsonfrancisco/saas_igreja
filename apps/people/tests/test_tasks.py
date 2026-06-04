"""Sprint 3 / Frente 2 (Bloco 3) — task de purge LGPD (RN-006).

`purge_anonymized_persons` remove fisicamente a Person anonimizada há > 30 dias.
Testa o corte de 30 dias e o SET_NULL das FKs após o purge (RN-007). A task gere
o próprio `schema_context`; os dados de apoio são criados via `schema_context`.
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from django_tenants.utils import schema_context

from apps.communities.models import Community
from apps.core.models import AuditLog
from apps.people import services
from apps.people.models import Person
from apps.people.tasks import purge_anonymized_persons


@pytest.mark.django_db(transaction=True)
def test_celery_beat_purge_after_30_days(church_a):
    """Só a anonimizada há mais de 30 dias é removida; recente e ativa permanecem."""
    with schema_context(church_a.schema_name):
        old = Person.objects.create(
            name='Velho', anonymized_at=timezone.now() - timedelta(days=31)
        )
        recent = Person.objects.create(
            name='Recente', anonymized_at=timezone.now() - timedelta(days=5)
        )
        active = Person.objects.create(name='Ativo')

    removed = purge_anonymized_persons()

    with schema_context(church_a.schema_name):
        assert not Person.objects.filter(pk=old.pk).exists()
        assert Person.objects.filter(pk=recent.pk).exists()
        assert Person.objects.filter(pk=active.pk).exists()
    assert removed == 1


@pytest.mark.django_db(transaction=True)
def test_purge_audits_delete(church_a):
    """O delete do purge gera AuditLog('delete') automático (AuditLogMixin)."""
    with schema_context(church_a.schema_name):
        person = Person.objects.create(
            name='Velho', anonymized_at=timezone.now() - timedelta(days=40)
        )
        pk = person.pk

    purge_anonymized_persons()

    with schema_context(church_a.schema_name):
        assert AuditLog.objects.filter(
            model_name='Person', action='delete', object_id=str(pk)
        ).exists()


@pytest.mark.django_db(transaction=True)
def test_person_fk_set_null_after_anonymize(church_a):
    """Anonimizar + purgar a líder zera `community.leader` (SET_NULL, RN-007)."""
    with schema_context(church_a.schema_name):
        leader = Person.objects.create(name='Lider')
        community = Community.objects.create(name='Celula', leader=leader)
        services.anonymize_person(person=leader)
        # Recua o anonymized_at para cair na janela de purge.
        Person.objects.filter(pk=leader.pk).update(
            anonymized_at=timezone.now() - timedelta(days=31)
        )

    purge_anonymized_persons()

    with schema_context(church_a.schema_name):
        community.refresh_from_db()
        assert not Person.objects.filter(pk=leader.pk).exists()
        assert community.leader is None
