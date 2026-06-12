"""Campo do design Athos v3 em Ministérios (RF-124): tipo/categoria."""

import pytest
from django_tenants.utils import schema_context

from apps.ministries.models import Ministry


@pytest.mark.django_db(transaction=True)
def test_ministry_category_field(church_a):
    with schema_context(church_a.schema_name):
        m = Ministry.objects.create(name='Louvor', category=Ministry.Category.WORSHIP)
        assert m.category == 'worship'
        # default é Outro.
        assert Ministry.objects.create(name='X').category == 'other'
