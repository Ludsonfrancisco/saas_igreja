"""Sprint 3 / Frente 3 (Bloco 4a) — travas da Gestão de Acessos (OD-019 / RISK-015).

Garante o teto da concessão de papéis: Secretário NÃO concede `pastor` nem desativa
um Pastor; ninguém altera/desativa a própria conta. Operam sobre `User` (público) —
`church_a` fornece a igreja; `transaction=True` por causa do DDL de criar Church.
"""

import pytest
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.accounts.services import change_roles, deactivate_user

GOOD_PASSWORD = 'Senha@123'


def _user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


@pytest.mark.django_db(transaction=True)
def test_secretary_cannot_grant_pastor(church_a):
    secretary = _user(church_a, 'sec@a.com', ['secretary'])
    _user(church_a, 'pastor@a.com', ['pastor'])  # mantém um Pastor (RN-004)
    target = _user(church_a, 'alvo@a.com', ['member'])

    with pytest.raises(ValidationError):
        change_roles(user=target, new_roles=['pastor'], actor=secretary)

    target.refresh_from_db()
    assert 'pastor' not in target.roles


@pytest.mark.django_db(transaction=True)
def test_pastor_can_grant_pastor(church_a):
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    target = _user(church_a, 'alvo@a.com', ['member'])

    change_roles(user=target, new_roles=['pastor'], actor=pastor)

    target.refresh_from_db()
    assert 'pastor' in target.roles


@pytest.mark.django_db(transaction=True)
def test_no_self_role_escalation(church_a):
    secretary = _user(church_a, 'sec@a.com', ['secretary'])
    _user(church_a, 'pastor@a.com', ['pastor'])

    with pytest.raises(ValidationError):
        change_roles(user=secretary, new_roles=['secretary', 'pastor'], actor=secretary)

    secretary.refresh_from_db()
    assert 'pastor' not in secretary.roles


@pytest.mark.django_db(transaction=True)
def test_secretary_cannot_remove_pastor(church_a):
    """Trava nos dois sentidos: Secretário também não DEMOVE um Pastor (Bloco 4b)."""
    secretary = _user(church_a, 'sec@a.com', ['secretary'])
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    _user(church_a, 'pastor2@a.com', ['pastor'])  # 2º pastor: RN-004 não é o bloqueio

    with pytest.raises(ValidationError):
        change_roles(user=pastor, new_roles=['member'], actor=secretary)

    pastor.refresh_from_db()
    assert 'pastor' in pastor.roles


@pytest.mark.django_db(transaction=True)
def test_secretary_cannot_deactivate_pastor(church_a):
    secretary = _user(church_a, 'sec@a.com', ['secretary'])
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    _user(church_a, 'pastor2@a.com', ['pastor'])  # 2º pastor: RN-004 não é o bloqueio

    with pytest.raises(ValidationError):
        deactivate_user(user=pastor, actor=secretary)

    pastor.refresh_from_db()
    assert pastor.is_active is True


@pytest.mark.django_db(transaction=True)
def test_cannot_deactivate_self(church_a):
    secretary = _user(church_a, 'sec@a.com', ['secretary'])

    with pytest.raises(ValidationError):
        deactivate_user(user=secretary, actor=secretary)

    secretary.refresh_from_db()
    assert secretary.is_active is True
