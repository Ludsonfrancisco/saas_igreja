"""Formulário de upload de arquivo (RF-065/067 · ACCESS_MATRIX §3.8).

Recorte do quick win: a UI de envio para **Pastor/Secretário** (geral + qualquer
contexto). O service `upload_file` (validação de MIME/tamanho, R2, auditoria) já
existia desde a Sprint 6 — aqui só montamos a entrada na interface.

`context` é um ÚNICO select agrupado (optgroups) que codifica modelo+id no value
(`''`=geral, `community:<id>`, `ministry:<id>`, `finance`) — evita o usuário ter de
digitar um ID. O upload escopado de Líder/Coordenador (só a sua comunidade/ministério)
fica para o Comunidades v2 (escopo fino).
"""

from django import forms


class FileUploadForm(forms.Form):
    file = forms.FileField(
        label='Arquivo',
        help_text='Até 10MB. PDF, imagens ou documentos (SVG não é aceito).',
    )
    context = forms.ChoiceField(
        label='Contexto',
        required=False,
        help_text='Onde este arquivo se encaixa. "Geral" fica visível conforme o '
        'acesso.',
    )

    def __init__(self, *args, communities=None, ministries=None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [('', '— Geral (igreja toda) —')]
        if communities:
            choices.append(
                ('Comunidades', [(f'community:{c.pk}', c.name) for c in communities])
            )
        if ministries:
            choices.append(
                ('Ministérios', [(f'ministry:{m.pk}', m.name) for m in ministries])
            )
        choices.append(('finance', 'Financeiro'))
        self.fields['context'].choices = choices

    def related(self):
        """Traduz o `context` escolhido em `(related_model, related_object_id)` para o
        service. Geral => ('', ''); `finance` => ('finance', ''); `model:id` => split.
        """
        value = self.cleaned_data.get('context') or ''
        if not value:
            return '', ''
        if value == 'finance':
            return 'finance', ''
        related_model, _, related_object_id = value.partition(':')
        return related_model, related_object_id
