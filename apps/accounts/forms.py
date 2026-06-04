"""Forms da app accounts (Frente 4 — Convites / RN-003a).

Forms explicitos (`forms.Form`), nunca `ModelForm` com `fields='__all__'`
(AP-10): cada campo e declarado e validado de forma controlada. Labels em
pt-BR; codigo em ingles.
"""

from django import forms
from django.contrib.auth.password_validation import validate_password

from apps.accounts.models import User
from apps.tenants.models import Church


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


class GrantSupportAccessForm(forms.Form):
    """Formulario de concessao de SupportAccess (Frente 5 — RN-015 / RISK-009).

    `forms.Form` explicito (nunca ModelForm `__all__`, AP-10): igreja-alvo +
    justificativa. A janela de 4h e o vinculo ao admin sao definidos no service
    (`grant_support_access`), nao no form. A `justification` e obrigatoria (motivo
    do suporte) e fica apenas no model — nunca no log (TENANT-07).
    """

    church = forms.ModelChoiceField(queryset=Church.objects.all(), label='Igreja')
    justification = forms.CharField(widget=forms.Textarea, label='Justificativa')


class UserAccessForm(forms.Form):
    """Gestão de Acessos (OD-019): funções (multi-role) + ativo/inativo de um usuário.

    `forms.Form` explícito (AP-10). As barreiras efetivas (RN-004, travas RISK-015)
    vivem no service layer (`change_roles`/`deactivate_user`); aqui só coletamos a
    entrada. O `pastor` aparece nas opções, mas só um Pastor pode concedê-lo/removê-lo
    — a trava no service rejeita um Secretário que tente.
    """

    roles = forms.MultipleChoiceField(
        choices=User.Role.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Funções',
    )
    is_active = forms.BooleanField(required=False, label='Conta ativa')
