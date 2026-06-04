"""Form de Ministério (Frente 3 / Bloco 3).

`ModelForm` com `fields` explícito (AP-10). `coordinators` é o M2M (OD-019, vários
coordenadores). Per ACCESS_MATRIX §3.5, **definir coordenadores é só do Pastor** —
quando o editor é um Coordenador (não-Pastor), o campo some (`can_set_coordinators`).
"""

from django import forms

from apps.ministries.models import Ministry


class MinistryForm(forms.ModelForm):
    class Meta:
        model = Ministry
        fields = ['name', 'coordinators', 'is_active']

    def __init__(self, *args, can_set_coordinators=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not can_set_coordinators:
            self.fields.pop('coordinators')
