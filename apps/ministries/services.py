"""Service layer de Ministérios — analytics da tela (RF-121).

Camada fina (P-ARQ-04). Reusa `ministry_volunteer_gaps` (OD-029 / dashboard) — a
mesma agregação do card "Saúde do Ministério" da home — para os cards/gráfico da
tela de Ministérios.
"""

from apps.dashboard.services import ministry_volunteer_gaps


def ministries_page_stats():
    """KPIs + gráfico da tela de Ministérios (RF-121). Church-wide (§3.5: todos os
    papéis de gestão veem todos os ministérios), por isso sem recorte de escopo.

    Reusa `ministry_volunteer_gaps()` (1 query agregada, sem N+1). Cards: ministérios,
    voluntários ao todo, GAP total (quantos faltam), ministérios sem meta. Gráfico de
    barra: voluntários faltando (GAP) por ministério (OD-029).
    """
    gaps = ministry_volunteer_gaps()
    cards = [
        {'label': 'Ministérios', 'value': len(gaps), 'icon': 'heart-handshake'},
        {
            'label': 'Voluntários',
            'value': sum(g['current'] for g in gaps),
            'icon': 'users',
        },
        {
            'label': 'Faltam (GAP)',
            'value': sum(g['gap'] for g in gaps),
            'icon': 'user-plus',
        },
        {
            'label': 'Sem meta definida',
            'value': sum(1 for g in gaps if not g['needed']),
            'icon': 'target',
        },
    ]
    chart = {
        'labels': [g['name'] for g in gaps],
        'values': [g['gap'] for g in gaps],
    }
    return {'cards': cards, 'chart': chart}
