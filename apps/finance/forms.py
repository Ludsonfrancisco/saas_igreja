"""Forms do Financeiro (Sprint 6.7 / Bloco 2).

`ModelForm` com `fields` explícito (AP-10). `TransactionForm` filtra a categoria por
`kind` (entrada/saída) — o botão "Nova Entrada"/"Nova Despesa" abre o form já no tipo
certo — e oferece como contribuinte apenas Pessoas ativas não-anonimizadas.
"""

from django import forms

from apps.finance.models import Category, Transaction
from apps.people.models import Person


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'kind', 'is_active']


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = [
            'category',
            'date',
            'amount',
            'description',
            'payment_method',
            'contributor',
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.TextInput(),
        }

    def __init__(self, *args, kind=None, **kwargs):
        """`kind` (opcional) trava as categorias a entrada OU saída."""
        super().__init__(*args, **kwargs)
        cat_qs = Category.objects.filter(is_active=True)
        if kind is not None:
            cat_qs = cat_qs.filter(kind=kind)
        self.fields['category'].queryset = cat_qs
        # Contribuinte: opcional, só Pessoas ativas não-anonimizadas.
        self.fields['contributor'].queryset = Person.objects.filter(
            anonymized_at__isnull=True
        ).order_by('name')
        self.fields['contributor'].required = False

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise forms.ValidationError('O valor deve ser maior que zero.')
        return amount
