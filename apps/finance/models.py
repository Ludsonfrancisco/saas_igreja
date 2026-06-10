"""Financeiro básico — models do TENANT (Sprint 6.7 / OD-024a).

Tesouraria básica do MVP (o produto nasceu de uma necessidade financeira):
lançamentos de entrada/saída, dízimos/ofertas e saldo. Avançado (recibo PDF,
conciliação, relatório, doação online) é a Sprint 8 (OD-024b).

Vive no schema do tenant (TENANT-04: nada de FK para User/Church). O ator de um
lançamento é guardado em `created_by` (`user_id` do User público), não FK.

Modelagem (decisão do dono): **`Category.kind` é a FONTE DA VERDADE** de
entrada/saída — `Transaction` NÃO tem `kind` redundante (deriva da categoria). O
saldo = Σ(valor de categorias-entrada) − Σ(valor de categorias-saída). `amount` é
sempre positivo; o sinal vem do `kind` da categoria.
"""

from django.db import models

from apps.core.models import AuditLogMixin, BaseModel


class Category(BaseModel, AuditLogMixin):
    """Categoria de lançamento (dízimo, oferta, aluguel, energia…).

    `kind` (entrada/saída) é a fonte da verdade do sinal. Herda `AuditLogMixin`
    (create/update/delete auditados pelos signals do core).
    """

    class Kind(models.TextChoices):
        INCOME = 'income', 'Entrada'
        EXPENSE = 'expense', 'Saída'

    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=8, choices=Kind.choices, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('kind', 'name')
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'kind'], name='finance_category_unique_name_kind'
            )
        ]

    def __str__(self):
        return f'{self.name} ({self.get_kind_display()})'


class Transaction(BaseModel, AuditLogMixin):
    """Lançamento financeiro (entrada ou saída, conforme a categoria).

    `amount` é sempre POSITIVO; o sinal é dado por `category.kind`. `contributor`
    (FK→Person, `SET_NULL`) registra o doador de um dízimo/oferta — `SET_NULL` por
    LGPD/RN-007: o purge físico da Pessoa preserva o lançamento (a identidade some,
    o valor histórico fica). `category` é `PROTECT`: não se apaga uma categoria que
    já tem lançamentos. Herda `AuditLogMixin` (lançamentos auditados — RNF financeiro).
    """

    class PaymentMethod(models.TextChoices):
        CASH = 'cash', 'Dinheiro'
        PIX = 'pix', 'Pix'
        CARD = 'card', 'Cartão'
        TRANSFER = 'transfer', 'Transferência'
        OTHER = 'other', 'Outro'

    category = models.ForeignKey(
        'Category', on_delete=models.PROTECT, related_name='transactions'
    )
    date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=200, blank=True, default='')
    payment_method = models.CharField(
        max_length=12, choices=PaymentMethod.choices, default=PaymentMethod.CASH
    )
    # Dízimo/oferta: contribuinte opcional. SET_NULL preserva o lançamento no purge
    # da Pessoa (RN-007/LGPD). NULL = lançamento sem contribuinte nominal.
    contributor = models.ForeignKey(
        'people.Person',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contributions',
    )
    # user_id do criador (TENANT-04: id do User público, não FK). NULL p/ seed.
    created_by = models.IntegerField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ('-date', '-created_at')

    def __str__(self):
        return f'{self.category.name} · {self.amount} ({self.date})'
