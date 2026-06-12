"""Campo do design Athos v3 em Pessoas (RF-125): data de entrada (membro desde)."""

import datetime

import pytest
from django_tenants.utils import schema_context

from apps.people import services


@pytest.mark.django_db(transaction=True)
def test_person_joined_at_field(church_a):
    joined = datetime.date(2020, 3, 1)
    with schema_context(church_a.schema_name):
        # Via service (caminho do form/CSV) — `joined_at` é aceito e persistido.
        p = services.create_person(church=church_a, name='Ana', joined_at=joined)
        assert p.joined_at == joined
        # update_person também aceita o campo (whitelist _EDITABLE_FIELDS).
        services.update_person(person=p, joined_at=datetime.date(2021, 1, 1))
        p.refresh_from_db()
        assert p.joined_at == datetime.date(2021, 1, 1)
        # opcional: pode ficar nulo.
        assert (
            services.create_person(church=church_a, name='Sem data').joined_at is None
        )
