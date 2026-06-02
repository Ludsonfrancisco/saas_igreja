"""Validador de politica de senha (SEC-02 / PRD §15.1).

Regras (alem dos validadores padrao do Django ja registrados):
  - minimo de 8 caracteres;
  - pelo menos 1 digito;
  - pelo menos 1 caractere especial (nao alfanumerico);
  - a senha NAO pode ser igual nem CONTER o email ou o nome do usuario.

Mensagens em pt-BR (interface 100% pt-BR; codigo em ingles). Este validador roda
no `validate_password` do Django, que e invocado pelos fluxos do allauth (signup,
reset, troca de senha) e por `User.set_password`-adjacent forms. Como User vive no
schema public, este validador nao toca tenant — e puro de regra de negocio.
"""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

# Caracteres considerados "especiais" (nao alfanumericos). Mantido explicito em
# vez de depender so de `str.isalnum()` para deixar a intencao clara e estavel.
_SPECIAL_CHARS = set('!@#$%^&*()_+-=[]{};:\'",.<>/?\\|`~')


class PasswordPolicyValidator:
    """Exige tamanho minimo, digito, caractere especial e diferenca do usuario.

    Registrado em `AUTH_PASSWORD_VALIDATORS`. `min_length` e parametrizavel para
    permitir politicas mais rigidas no futuro sem alterar o codigo.
    """

    def __init__(self, min_length=8):
        self.min_length = min_length

    def validate(self, password, user=None):
        errors = []

        if len(password) < self.min_length:
            errors.append(
                ValidationError(
                    _('A senha deve ter pelo menos %(min)d caracteres.'),
                    code='password_too_short',
                    params={'min': self.min_length},
                )
            )

        if not any(c.isdigit() for c in password):
            errors.append(
                ValidationError(
                    _('A senha deve conter pelo menos um numero.'),
                    code='password_no_number',
                )
            )

        if not any(c in _SPECIAL_CHARS for c in password):
            errors.append(
                ValidationError(
                    _('A senha deve conter pelo menos um caractere especial.'),
                    code='password_no_special',
                )
            )

        # A senha nao pode ser igual nem conter o email/nome do usuario. Usamos
        # comparacao case-insensitive e por substring: "Joao2024!" para um usuario
        # chamado "Joao" e rejeitada. Atributos vazios sao ignorados.
        if user is not None:
            password_lower = password.lower()
            attributes = []
            email = getattr(user, 'email', '') or ''
            if email:
                attributes.append(email)
                # Tambem a parte local do email (antes do @): "joao@x.com" -> "joao".
                local_part = email.split('@', 1)[0]
                if local_part:
                    attributes.append(local_part)
            for attr_name in ('first_name', 'last_name', 'get_full_name'):
                value = getattr(user, attr_name, '') or ''
                if callable(value):
                    value = value() or ''
                if value:
                    attributes.append(value)

            for attr in attributes:
                attr = str(attr).strip().lower()
                # Ignora fragmentos triviais (1-2 chars) para nao bloquear senhas
                # legitimas por causa de iniciais; o foco e o email/nome completo.
                if len(attr) >= 3 and attr in password_lower:
                    errors.append(
                        ValidationError(
                            _(
                                'A senha nao pode ser igual nem conter seu email '
                                'ou seu nome.'
                            ),
                            code='password_too_similar_to_user',
                        )
                    )
                    break

        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return _(
            'Sua senha deve ter pelo menos %(min)d caracteres, incluir ao menos '
            'um numero e um caractere especial, e nao pode conter seu email ou '
            'nome.'
        ) % {'min': self.min_length}
