"""Form de Comunidade (Frente 3 / Bloco 2).

`ModelForm` com `fields` explícito (AP-10). `leaders` é o M2M (OD-019, vários
líderes). Per ACCESS_MATRIX §3.4, **definir líderes é só do Pastor** — quando o
editor é um Líder (não-Pastor), o campo `leaders` é removido (`can_set_leaders`).
"""

from django import forms

from apps.communities.models import Community


class CommunityForm(forms.ModelForm):
    class Meta:
        model = Community
        fields = [
            'name',
            'category',
            'leaders',
            'meeting_day',
            'meeting_time',
            'max_members',
            'is_active',
        ]
        labels = {
            'name': 'Nome',
            'category': 'Tipo',
            'leaders': 'Líderes',
            'meeting_day': 'Dia da reunião',
            'meeting_time': 'Horário da reunião',
            'max_members': 'Lotação máxima (0 = sem limite)',
            'is_active': 'Ativa',
        }
        widgets = {'meeting_time': forms.TimeInput(attrs={'type': 'time'})}

    def __init__(self, *args, can_set_leaders=True, **kwargs):
        super().__init__(*args, **kwargs)
        # Definir líderes é prerrogativa do Pastor (ACCESS_MATRIX §3.4): para um
        # Líder editando a própria comunidade, o campo some.
        if not can_set_leaders:
            self.fields.pop('leaders')
