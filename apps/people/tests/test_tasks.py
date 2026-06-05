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
from apps.people.tasks import import_persons_csv, purge_anonymized_persons

_CSV = (
    'name,email,phone,status,consent\n'
    'Ana Lima,ana@a.com,,member,sim\n'
    'Bruno Souza,,,visitor,\n'
)


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
    """Após anonimizar + purgar a Person, os vínculos para ela são limpos (RN-007).

    Com OD-019, liderança/coordenação são M2M (`Community.leaders`/
    `Ministry.coordinators`): deletar a Person remove esses vínculos, mas a
    comunidade e o ministério PERMANECEM. (FKs `SET_NULL` propriamente ditas para
    Person chegam com Attendance/Schedule nas Sprints 4/5.)
    """
    from apps.ministries.models import Ministry

    with schema_context(church_a.schema_name):
        person = Person.objects.create(name='Lider')
        community = Community.objects.create(name='Celula')
        community.leaders.add(person)
        ministry = Ministry.objects.create(name='Louvor')
        ministry.coordinators.add(person)
        services.anonymize_person(person=person)
        # Recua o anonymized_at para cair na janela de purge.
        Person.objects.filter(pk=person.pk).update(
            anonymized_at=timezone.now() - timedelta(days=31)
        )

    purge_anonymized_persons()

    with schema_context(church_a.schema_name):
        assert not Person.objects.filter(pk=person.pk).exists()
        assert community.leaders.count() == 0  # vínculo M2M removido
        assert ministry.coordinators.count() == 0  # vínculo M2M removido
        assert Community.objects.filter(pk=community.pk).exists()
        assert Ministry.objects.filter(pk=ministry.pk).exists()


# --- Importação CSV (RF-033) ------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_csv_import_creates_persons(church_a):
    result = import_persons_csv(church_a.schema_name, _CSV, 'lote-1')

    assert result['created'] == 2
    with schema_context(church_a.schema_name):
        ana = Person.objects.get(name='Ana Lima')
        assert ana.email == 'ana@a.com'
        assert ana.consent_given_at is not None
        assert ana.import_id == 'lote-1'
        # Bruno sem contato → sem consent exigido.
        assert Person.objects.get(name='Bruno Souza').consent_given_at is None


@pytest.mark.django_db(transaction=True)
def test_csv_import_idempotent(church_a):
    """Re-rodar o mesmo import_id é no-op — não duplica (RF-033)."""
    import_persons_csv(church_a.schema_name, _CSV, 'lote-1')
    second = import_persons_csv(church_a.schema_name, _CSV, 'lote-1')

    assert second['status'] == 'already_imported'
    with schema_context(church_a.schema_name):
        assert Person.objects.count() == 2


@pytest.mark.django_db(transaction=True)
def test_csv_import_enforces_consent(church_a):
    """Linha com email/telefone SEM consent é pulada e reportada (OPS-05)."""
    csv_no_consent = 'name,email,phone,status,consent\nCarlos,carlos@a.com,,member,\n'
    result = import_persons_csv(church_a.schema_name, csv_no_consent, 'lote-2')

    assert result['created'] == 0
    assert len(result['errors']) == 1
    assert result['errors'][0]['row'] == 2
    with schema_context(church_a.schema_name):
        assert not Person.objects.filter(name='Carlos').exists()


@pytest.mark.django_db(transaction=True)
def test_csv_import_skips_empty_name_and_falls_back_status(church_a):
    """Linha sem nome é pulada; status inválido cai para VISITOR."""
    csv_mixed = (
        'name,email,phone,status,consent\n'
        ',,,member,\n'  # nome vazio -> pulado (linha 2)
        'Joana,,,xpto,\n'  # status inválido -> VISITOR
    )
    result = import_persons_csv(church_a.schema_name, csv_mixed, 'lote-3')

    assert result['created'] == 1
    assert any(e['row'] == 2 for e in result['errors'])
    with schema_context(church_a.schema_name):
        assert Person.objects.get(name='Joana').status == Person.Status.VISITOR
