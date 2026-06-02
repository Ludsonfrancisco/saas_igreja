"""Sprint 1 — BaseModel: auditoria temporal nao-opcional (P-ARQ-02).

`BaseModel` e abstrato; exercitamos via uma subclasse concreta que ja existe:
`Invite` (accounts). Cobre `test_baseModel_created_updated_at`: created_at e
updated_at sao preenchidos, timezone-aware, e updated_at avanca a cada save
enquanto created_at permanece fixo.

Nota de design (judgment call): Invite exige FK obrigatoria para Church e para
o usuario que convida. Criar uma Church dispara `auto_create_schema` (DDL com
commit proprio), entao este teste usa `@pytest.mark.django_db(transaction=True)`
e as fixtures church_a/pastor_a (que fazem DROP SCHEMA no teardown). Nao ha
como instanciar Invite sem uma Church.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import Invite


@pytest.mark.django_db(transaction=True)
def test_baseModel_created_updated_at(church_a, pastor_a):
    invite = Invite.objects.create(
        church=church_a,
        email='convidado@a.com',
        roles=['member'],
        invited_by=pastor_a,
        expires_at=timezone.now() + timedelta(days=7),
    )

    # Ambos os timestamps sao preenchidos e timezone-aware (USE_TZ=True).
    assert invite.created_at is not None
    assert invite.updated_at is not None
    assert timezone.is_aware(invite.created_at)
    assert timezone.is_aware(invite.updated_at)

    created_before = invite.created_at
    updated_before = invite.updated_at

    # Altera um campo e salva de novo: updated_at (auto_now) deve avancar,
    # created_at (auto_now_add) deve permanecer fixo.
    invite.accepted_at = timezone.now()
    invite.save()
    invite.refresh_from_db()

    assert invite.created_at == created_before
    assert invite.updated_at > updated_before
