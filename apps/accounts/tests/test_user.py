"""Sprint 1 — unicidade de email no User (P-ARQ-03 / login por email).

Cobre o teste minimo `test_user_email_unique` (SPRINTS Sprint 1): o email e
a credencial de login (USERNAME_FIELD), logo nao pode haver duplicata.
"""

import pytest
from django.db import IntegrityError, transaction

from apps.accounts.models import User


@pytest.mark.django_db
def test_user_email_unique():
    User.objects.create_user(
        email='dup@example.com',
        password='Test1234!',
        roles=['pastor'],
    )

    # Segundo User com o mesmo email viola a unique constraint no banco.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            User.objects.create_user(
                email='dup@example.com',
                password='Test1234!',
                roles=['member'],
            )
