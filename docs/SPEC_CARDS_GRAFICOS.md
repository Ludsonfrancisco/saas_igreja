# SPEC — Cards e gráficos por página (analytics contextual)

> **Status:** 📝 DRAFT — aguardando aprovação das MÉTRICAS pelo dono (G-02). Decisões já
> tomadas (2026-06-11): **telas = Pessoas, Comunidades, Encontros, Ministérios**;
> **profundidade = cards (KPIs) + 1 gráfico Chart.js por tela**. Item #3 do backlog pré-7.
> Reusa `dashboard.services` + agregações da Comunidades v2 e o padrão Chart.js de
> `dashboard/_metrics.html` (cor = acento da igreja). **Regra dura: nenhum número
> fictício** — cada métrica mapeia para uma query real (espelha OD-029/OD-030).

---

## 1. Contexto e problema

As telas de **lista** (Pessoas/Comunidades/Encontros/Ministérios) hoje só mostram a
tabela/cards de registros. O dono quer, no topo de cada uma, uma faixa de **KPIs** + **1
gráfico** no estilo do design de referência (`referencias/templates/igreja_saas_personalizado.html`)
— dando leitura rápida do que importa naquele contexto, **sem inventar número** e
**respeitando o escopo de papel** (P-ARQ-08: Pastor/Secretário veem tudo; Líder/Coordenador
só o seu).

## 2. Princípios (herdados)

- **Dado real** — toda métrica vem de uma agregação no banco (P-ARQ-09, sem N+1). Onde não
  há dado, **não** inventa card (sem placeholder fictício; segue OD-030).
- **Escopo por papel** — os cards/gráficos usam o MESMO recorte da lista da página
  (Líder → sua comunidade; Coordenador → seus ministérios; Pastor/Secretário → tudo).
- **Chart.js já no projeto** (`dashboard/_metrics.html`): `{{ data|json_script }}` + `<canvas>`
  + cor = acento da igreja; ícones Lucide; re-render em `htmx:afterSwap`. A11y: `<canvas>`
  com `role="img"` + `aria-label`, e um resumo textual para leitores de tela.

## 3. Requisitos funcionais novos

| ID | Tela | Cards (KPIs) | Gráfico |
|---|---|---|---|
| **RF-118** | **Pessoas** (`/pessoas/`) | Total (escopo) · Membros · Visitantes · Aniversariantes do mês | **Rosca** "Pessoas por situação" (Membro/Visitante/Inativo) |
| **RF-119** | **Comunidades** (`/comunidades/`) | Células (escopo) · Frequência média geral · Células com lançamento pendente · Total de membros | **Barra** "Frequência por célula" (média das últimas reuniões por célula) |
| **RF-120** | **Encontros** (`/encontros/`) | Encontros no mês · Presenças no mês · Frequência média (presenças/encontro) · Próximo encontro | **Linha** "Presença nos últimos 6 meses" (total de presenças por mês) |
| **RF-121** | **Ministérios** (`/ministerios/`) | Ministérios (escopo) · Voluntários ao todo · GAP total de voluntários · Ministérios sem meta | **Barra** "Saúde do Ministério" = GAP por ministério (atuais × meta, OD-029) |

## 4. Fonte de cada número (rastreabilidade — nada fictício)

### RF-118 Pessoas
- Total/Membros/Visitantes/Inativos → `Person.status` (counts; reusa `_people_by_status`).
- Aniversariantes do mês → `Person.birth_date__month = hoje.month` (exclui anonimizadas).
- Gráfico rosca → os mesmos counts por `status`.
- **Escopo:** mesmo `_scoped_person_queryset` do dashboard (comunidade/ministério do papel).

### RF-119 Comunidades
- Células → `Community` no escopo (Líder = `leaders__user_id`; admin = todas; RF-106).
- Frequência média geral → média de `cell_frequencies(communities)` (Comunidades v2).
- Pendentes → contagem de células com `cell_pending_days` > 0.
- Total de membros → `Person.objects.filter(community__in=escopo)`.
- Gráfico barra → `cell_frequencies` (uma barra por célula).

### RF-120 Encontros
- Encontros no mês → `Gathering.date` no mês corrente.
- Presenças no mês → `Attendance.is_present=True` em encontros do mês.
- Frequência média → presenças ÷ nº de encontros do mês (0 se sem encontro).
- Próximo encontro → `upcoming_gatherings(limit=1)` (já existe).
- Gráfico linha → **nova agg** `monthly_attendance_series(months=6)` (`TruncMonth` sobre
  `Attendance` presente; espelha `home_growth_series`).

### RF-121 Ministérios
- Ministérios/Voluntários/GAP → `ministry_volunteer_gaps` (já existe; usado na home).
- Ministérios sem meta → `Ministry.volunteers_needed = 0`.
- Gráfico barra → GAP por ministério (atuais × `volunteers_needed`, OD-029).
- **Escopo:** Coordenador → `coordinators__user_id`; admin → todos.

## 5. Modelo de dados

**Nenhum model novo.** Tudo são agregações sobre models existentes (`Person`,
`Community`, `Gathering`, `Attendance`, `Ministry`, `Schedule`). Uma única agregação nova
de **service** (`monthly_attendance_series`, RF-120).

## 6. Camada de serviço (onde cada agg vive)

- `apps/people/services.py` → `people_page_stats(*, scope)` (counts + aniversariantes).
- `apps/communities/services.py` → `communities_page_stats(*, scope)` (reusa `cell_frequencies`/`cell_pending_days`).
- `apps/gatherings/services.py` → `gatherings_page_stats()` + `monthly_attendance_series(*, months=6)`.
- `apps/ministries/services.py` (ou reusa `dashboard.services`) → `ministries_page_stats(*, scope)` via `ministry_volunteer_gaps`.

Cada stats devolve um dict pronto pro template (KPIs + série do gráfico em formato
`json_script`). Escopo recebido das views (mesmo recorte da list-view).

## 7. Frontend (design Athos)

- Componente reutilizável `components/_stat_cards.html` (faixa de KPIs, grid responsivo
  2/4 colunas, ícone Lucide + número `tnum` + rótulo) — já há base em `dashboard/_metrics.html`.
- Componente `components/_chart.html` (canvas + `json_script` + init Chart.js parametrizável:
  tipo, labels, data, cor=acento). Carrega Chart.js uma vez (guard `typeof Chart`).
- Cada list-view ganha um bloco no topo: `{% include 'components/_stat_cards.html' %}` +
  `{% include 'components/_chart.html' %}`. Mobile-first; gráfico com altura fixa; estados
  vazios ("sem dados ainda") quando a agg vem zerada.

## 8. Acesso / escopo

Sem rota nova — os cards/gráficos vivem DENTRO das list-views já existentes, herdando o
gate de papel e o escopo de queryset delas. O isolamento cross-tenant já é coberto pelas
matrizes dessas páginas; acrescentar asserção leve de que a faixa de stats também é
escopada (Líder não vê número de fora do seu vínculo).

## 9. Fatiamento em blocos (1 por tela)

- **Bloco 1 — Pessoas (RF-118):** `people_page_stats` + cards + rosca; componentes
  `_stat_cards`/`_chart`. Testes (counts escopados, aniversariantes, render).
- **Bloco 2 — Comunidades (RF-119):** `communities_page_stats` + cards + barra frequência.
- **Bloco 3 — Encontros (RF-120):** `gatherings_page_stats` + `monthly_attendance_series` +
  cards + linha.
- **Bloco 4 — Ministérios (RF-121):** `ministries_page_stats` + cards + barra GAP.
- Cada bloco: service + template + testes; para sob revisão (G-02). Matrizes não mudam
  (sem rota nova); regressão + a11y dos gráficos ao final.

## 10. Testes mínimos

- `test_people_page_stats_scoped` (Líder só conta o seu vínculo; admin tudo).
- `test_people_birthdays_this_month`.
- `test_communities_page_stats_uses_cell_frequencies` / pendentes.
- `test_gatherings_monthly_attendance_series` (6 meses, presença por mês).
- `test_ministries_page_stats_gap` (reusa GAP).
- a11y (axe) de cada tela com o gráfico renderizado (`<canvas role=img>` + resumo textual).
- Sem N+1 (nplusone) nas aggs.

## 11. Governança (G-05)

Introduz **RF-118..121** (analytics por tela) → registrar no PRD antes de codar. **Sem OD
nova:** Chart.js já decidido; métricas são todas ancoradas em dado real (sem score
composto — segue OD-029). Cada bloco exige G-01/G-02.

> **A confirmar pelo dono (G-02):** as MÉTRICAS de cada tela (§3/§4). Proposta acima é o
> ponto de partida; ajustar quais KPIs/gráfico antes de eu codar o Bloco 1.
