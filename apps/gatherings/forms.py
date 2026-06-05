"""Form de Encontro (Sprint 4 / Frente 1).

`ModelForm` com `fields` explícito (AP-10). Espelha a barreira da §3.6 na UX:

- o dropdown de `gathering_type` mostra só os tipos que o ator pode criar
  (`services.allowed_types`); a barreira EFETIVA continua no service;
- `community` é escopada (Pastor/Secretário veem todas; Líder só as que lidera) e
  some quando a igreja não usa comunidades (`has_communities=False`, RN-010);
- na EDIÇÃO o tipo é travado (`disabled`) — não se converte um EVENT em WORSHIP
  por aqui (escalonamento); e a comunidade só aparece em encontros COMMUNITY.
"""

from django import forms

from apps.communities.models import Community
from apps.gatherings import services
from apps.gatherings.models import Gathering

ADMIN_ROLES = ('pastor', 'secretary')


class GatheringForm(forms.ModelForm):
    class Meta:
        model = Gathering
        fields = ['gathering_type', 'title', 'date', 'community', 'description']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, user, church, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.church = church
        editing = self.instance.pk is not None

        # Tipo: no create, só os tipos permitidos; na edição, trava no valor atual.
        if editing:
            self.fields['gathering_type'].disabled = True
        else:
            allowed = services.allowed_types(user, church)
            self.fields['gathering_type'].choices = [
                (value, label)
                for value, label in Gathering.Type.choices
                if value in allowed
            ]

        # Comunidade: escopada por papel; some se a igreja não usa comunidades, ou
        # (na edição) se este encontro não é do tipo COMMUNITY.
        hide_community = not church.has_communities or (
            editing and self.instance.gathering_type != Gathering.Type.COMMUNITY
        )
        if hide_community:
            self.fields.pop('community')
        else:
            qs = Community.objects.all()
            if not user.has_any_role(*ADMIN_ROLES):
                qs = qs.filter(leaders__user_id=user.id).distinct()
            self.fields['community'].queryset = qs
            self.fields['community'].required = False
