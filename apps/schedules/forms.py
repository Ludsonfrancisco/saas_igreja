"""Form de Escala (Sprint 5 / Frente 1).

`ModelForm` com `fields` explícito (AP-10). Escopa os campos por papel:

- `ministry`: Pastor/Secretário veem todos; Coordenador só os que coordena.
- `person`/`gathering`: pessoas ativas / encontros (o service valida o vínculo ao
  ministério e o conflito).
- Na EDIÇÃO, a alocação (ministry/person/gathering) é travada — só `role`/`notes`
  são editáveis. Reatribuir = excluir + recriar (mantém o conflito só no create).
"""

from django import forms

from apps.gatherings.models import Gathering
from apps.ministries.models import Ministry
from apps.people.models import Person
from apps.schedules.models import Schedule

ADMIN_ROLES = ('pastor', 'secretary')
LOCKED_ON_EDIT = ('ministry', 'person', 'gathering')


class ScheduleForm(forms.ModelForm):
    class Meta:
        model = Schedule
        fields = ['ministry', 'person', 'gathering', 'role', 'notes']
        labels = {
            'ministry': 'Ministério',
            'person': 'Pessoa',
            'gathering': 'Encontro',
            'role': 'Função',
            'notes': 'Observações',
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        ministries = Ministry.objects.filter(is_active=True)
        if not user.has_any_role(*ADMIN_ROLES):
            ministries = ministries.filter(coordinators__user_id=user.id).distinct()
        self.fields['ministry'].queryset = ministries
        self.fields['person'].queryset = Person.objects.filter(
            anonymized_at__isnull=True
        ).order_by('name')
        self.fields['gathering'].queryset = Gathering.objects.order_by('-date')

        if self.instance.pk:
            for name in LOCKED_ON_EDIT:
                self.fields[name].disabled = True


class ScheduleExceptionForm(ScheduleForm):
    """`ScheduleForm` + justificativa, para a aprovação de exceção de conflito (§3.7).

    `justification` é campo de form (não do model) — vai em `cleaned_data` e é
    consumido por `services.approve_exception` (não há `save()` aqui). A escolha de
    `ministry` já fica escopada pela base (Coordenador só os que coordena), o que
    casa com "Coordenador competente".
    """

    justification = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        label='Justificativa',
        help_text='Obrigatoria — registra por que o conflito foi autorizado.',
    )
