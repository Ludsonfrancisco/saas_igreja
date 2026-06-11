"""Form de Pessoa (Frente 2 / Bloco 2).

`ModelForm` com `fields` explícito — AP-10 proíbe `fields='__all__'`. O campo extra
`consent_given` (checkbox) espelha na UI a regra LGPD: quando email/telefone é
informado, o consentimento é obrigatório. A barreira EFETIVA continua na camada de
service (`create_person`/`update_person`, OPS-05); aqui é só UX. A view traduz o
checkbox em `consent_given_at` (datetime) ao chamar o service.
"""

from django import forms

from apps.accounts.models import User
from apps.people.models import Person


class PersonForm(forms.ModelForm):
    """Cadastro/edição de Pessoa. `consent_given` espelha a regra de consent (LGPD).

    `linked_user` (opcional) liga a Pessoa a um `User`-staff (líder/coordenador) da
    própria igreja — o queryset é escopado ao tenant via o kwarg `church`. A view
    traduz a escolha em `Person.user_id` (TENANT-04, não-FK).
    """

    consent_given = forms.BooleanField(
        required=False,
        label='Consentimento LGPD obtido (o titular autorizou guardar o contato)',
    )
    linked_user = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        label='Usuário vinculado (staff que loga: líder/coordenador)',
    )

    class Meta:
        model = Person
        fields = [
            'name',
            'status',
            'email',
            'phone',
            'birth_date',
            'community',
            'ministries',
            'notes',
        ]
        # Rótulos pt-BR (interface 100% pt-BR; nome do campo no código fica em inglês).
        labels = {
            'name': 'Nome',
            'status': 'Situação',
            'email': 'E-mail',
            'phone': 'Telefone',
            'birth_date': 'Data de nascimento',
            'community': 'Comunidade',
            'ministries': 'Ministérios',
            'notes': 'Observações',
        }
        widgets = {'birth_date': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, church=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Pré-marca o checkbox quando a pessoa já tem consentimento registrado.
        if self.instance and self.instance.pk and self.instance.consent_given_at:
            self.fields['consent_given'].initial = True
        # Escopa os Users selecionáveis à igreja atual; pré-seleciona o vínculo.
        if church is not None:
            self.fields['linked_user'].queryset = User.objects.filter(church=church)
        if self.instance and self.instance.pk and self.instance.user_id:
            self.fields['linked_user'].initial = self.instance.user_id
        # RN-019 (Comunidades v2): só Pastor/Secretário gerenciam o vínculo de célula
        # (= adicionar/remover membro). O Líder edita a pessoa, mas não muda a
        # comunidade — o campo sai do form para ele.
        if user is not None and not user.has_any_role('pastor', 'secretary'):
            self.fields.pop('community', None)

    def clean(self):
        cleaned = super().clean()
        has_contact = cleaned.get('email') or cleaned.get('phone')
        if has_contact and not cleaned.get('consent_given'):
            raise forms.ValidationError(
                'Consentimento (LGPD) e obrigatorio quando email ou telefone e '
                'informado.'
            )
        return cleaned


class PersonImportForm(forms.Form):
    """Upload de CSV para importação de pessoas (RF-033).

    Validação leve: extensão `.csv` + decodificação UTF-8 (na view). A validação de
    MIME forte via python-magic fica para a app de arquivos (Sprint 6); aqui o
    conteúdo é parseado linha a linha e erros são reportados.
    """

    file = forms.FileField(
        label='Arquivo CSV (colunas: name, email, phone, status, consent)'
    )

    def clean_file(self):
        upload = self.cleaned_data['file']
        if not upload.name.lower().endswith('.csv'):
            raise forms.ValidationError('Envie um arquivo .csv.')
        return upload
