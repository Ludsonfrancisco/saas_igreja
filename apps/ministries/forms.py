"""Form de Ministério (Frente 3 / Bloco 3).

`ModelForm` com `fields` explícito (AP-10). `coordinators` é o M2M (OD-019, vários
coordenadores). Per ACCESS_MATRIX §3.5, **definir coordenadores é só do Pastor** —
quando o editor é um Coordenador (não-Pastor), o campo some (`can_set_coordinators`).
"""

from django import forms

from apps.ministries.models import Ministry


class MinistryForm(forms.ModelForm):
    # `volunteers_needed` (OD-029): meta de voluntários do ministério, base do card
    # "Saúde do Ministério" (GAP). Opcional no form (omitir => 0 = "sem meta"); o
    # model é NOT NULL com default 0, então `clean` coage None/vazio para 0.
    volunteers_needed = forms.IntegerField(
        min_value=0, required=False, initial=0, label='Voluntários necessários'
    )

    class Meta:
        model = Ministry
        fields = ['name', 'coordinators', 'volunteers_needed', 'is_active']
        labels = {
            'name': 'Nome',
            'coordinators': 'Coordenadores',
            'is_active': 'Ativo',
        }

    def __init__(self, *args, can_set_coordinators=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not can_set_coordinators:
            self.fields.pop('coordinators')

    def clean_volunteers_needed(self):
        return self.cleaned_data.get('volunteers_needed') or 0
