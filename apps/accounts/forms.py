"""Forms da app accounts (Frente 4 — Convites / RN-003a).

Forms explicitos (`forms.Form`), nunca `ModelForm` com `fields='__all__'`
(AP-10): cada campo e declarado e validado de forma controlada. Labels em
pt-BR; codigo em ingles.
"""

from django import forms
from django.contrib.auth.password_validation import validate_password

from apps.accounts.models import User


class InviteForm(forms.Form):
    """Formulario de criacao de convite: email + um ou mais papeis (multi-role).

    `roles` usa CheckboxSelectMultiple sobre `User.Role.choices` — o usuario
    marca quantos papeis quiser; a uniao define as permissoes (RN-003a). A
    normalizacao final do email (lower/strip) e responsabilidade do service.
    """

    email = forms.EmailField(label='Email do convidado')
    roles = forms.MultipleChoiceField(
        label='Papeis',
        choices=User.Role.choices,
        widget=forms.CheckboxSelectMultiple,
        help_text='Selecione ao menos um papel. As permissoes sao somadas.',
    )


class AcceptInviteForm(forms.Form):
    """Formulario de aceite: define a senha e (opcionalmente) o nome.

    A senha passa pelo `validate_password` do projeto (PasswordPolicyValidator),
    garantindo a politica de forca configurada. `password1`/`password2` devem
    coincidir. `first_name`/`last_name` sao opcionais.
    """

    first_name = forms.CharField(label='Nome', max_length=150, required=False)
    last_name = forms.CharField(label='Sobrenome', max_length=150, required=False)
    password1 = forms.CharField(label='Senha', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirme a senha', widget=forms.PasswordInput)

    def clean_password1(self):
        password = self.cleaned_data['password1']
        validate_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'As senhas nao coincidem.')
        return cleaned
