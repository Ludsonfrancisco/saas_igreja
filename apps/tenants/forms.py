"""Formulário de Configurações da Igreja (RF-002 parcial / RF-126-127 · F2).

ModelForm com `fields` explícito (AP-10). Edita os RÓTULOS configuráveis exibidos na
UI (Comunidade/Ministério) + o título do líder principal. Pastor-only na view.
"""

from django import forms

from apps.tenants.models import Church


class ChurchSettingsForm(forms.ModelForm):
    class Meta:
        model = Church
        fields = [
            'leader_title',
            'community_label',
            'community_label_plural',
            'ministry_label',
            'ministry_label_plural',
        ]
        labels = {
            'leader_title': 'Título do líder principal',
            'community_label': 'Nome de "Comunidade" (singular)',
            'community_label_plural': 'Nome de "Comunidade" (plural)',
            'ministry_label': 'Nome de "Ministério" (singular)',
            'ministry_label_plural': 'Nome de "Ministério" (plural)',
        }
        help_texts = {
            'community_label': 'Ex.: Célula, Grupo, GC. Aparece em toda a interface.',
            'ministry_label': 'Ex.: Departamento, Equipe. Aparece em toda a interface.',
        }
