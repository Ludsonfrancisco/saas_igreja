"""Sprint 2 / Frente 2 — PasswordPolicyValidator (SEC-02 / PRD §15.1).

Politica: 8+ chars, >=1 numero, >=1 caractere especial, e nao pode ser igual nem
conter o email/nome do usuario. Testamos o validador isolado (sem DB) e via
`validate_password` (cadeia completa de AUTH_PASSWORD_VALIDATORS).
"""

from types import SimpleNamespace

import pytest
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from apps.accounts.validators import PasswordPolicyValidator


def _user(email='joao.silva@a.com', first_name='Joao', last_name='Silva'):
    return SimpleNamespace(
        email=email,
        first_name=first_name,
        last_name=last_name,
        get_full_name=lambda: f'{first_name} {last_name}'.strip(),
    )


def test_password_policy_min_8_chars():
    validator = PasswordPolicyValidator(min_length=8)
    # 7 chars com numero e especial -> reprovado por tamanho.
    with pytest.raises(ValidationError) as exc:
        validator.validate('Ab@1xyz')
    assert any('caracteres' in m for m in exc.value.messages)
    # 8 chars validos -> passa.
    validator.validate('Ab@1xyzz')


def test_password_requires_number():
    with pytest.raises(ValidationError) as exc:
        PasswordPolicyValidator().validate('SenhaSem@Numero')
    assert any('numero' in m for m in exc.value.messages)


def test_password_requires_special_char():
    with pytest.raises(ValidationError) as exc:
        PasswordPolicyValidator().validate('SenhaSemEspecial1')
    assert any('especial' in m for m in exc.value.messages)


def test_password_cannot_be_email_or_name():
    validator = PasswordPolicyValidator()
    user = _user(email='joao.silva@a.com', first_name='Joao', last_name='Silva')

    # Contem a parte local do email.
    with pytest.raises(ValidationError):
        validator.validate('joao.silva@1!', user=user)

    # Contem o primeiro nome.
    with pytest.raises(ValidationError):
        validator.validate('Joao2024!', user=user)

    # Sem relacao com email/nome -> passa.
    validator.validate('Zk7#mPq2w', user=user)


def test_password_policy_registered_in_validate_password():
    """A cadeia oficial AUTH_PASSWORD_VALIDATORS aplica nossa politica."""
    user = _user()
    # Senha fraca (sem especial) deve falhar na cadeia completa.
    with pytest.raises(ValidationError):
        validate_password('semespecial123', user=user)
    # Senha forte e sem relacao com o usuario passa.
    validate_password('Zk7#mPq2wL', user=user)


def test_get_help_text_is_ptbr():
    text = PasswordPolicyValidator().get_help_text()
    assert 'caracteres' in text
    assert 'numero' in text
    assert 'especial' in text
