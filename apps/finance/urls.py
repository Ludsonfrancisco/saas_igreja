"""URLs do Financeiro (namespace 'finance'), tenant-scoped sob `financeiro/`.

Sprint 6.7 (OD-024a). Toda view aplica `TenantRequiredMixin` + `TreasurerOrPastorMixin`.
"""

from django.urls import path

from apps.finance import views

app_name = 'finance'

urlpatterns = [
    path('financeiro/', views.FinanceDashboardView.as_view(), name='dashboard'),
    path('financeiro/lancamentos/', views.TransactionListView.as_view(), name='list'),
    path(
        'financeiro/lancamentos/novo/',
        views.TransactionCreateView.as_view(),
        name='create',
    ),
    path(
        'financeiro/lancamentos/<int:pk>/editar/',
        views.TransactionUpdateView.as_view(),
        name='edit',
    ),
    path(
        'financeiro/lancamentos/<int:pk>/excluir/',
        views.TransactionDeleteView.as_view(),
        name='delete',
    ),
    path(
        'financeiro/lancamentos/csv/',
        views.TransactionExportCSVView.as_view(),
        name='export_csv',
    ),
    path(
        'financeiro/categorias/', views.CategoryListView.as_view(), name='category_list'
    ),
    path(
        'financeiro/categorias/nova/',
        views.CategoryCreateView.as_view(),
        name='category_create',
    ),
    path(
        'financeiro/categorias/<int:pk>/editar/',
        views.CategoryUpdateView.as_view(),
        name='category_edit',
    ),
]
