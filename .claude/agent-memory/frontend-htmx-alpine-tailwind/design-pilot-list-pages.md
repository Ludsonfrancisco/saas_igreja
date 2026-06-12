---
name: design-pilot-list-pages
description: Padrão para recriar telas de listagem no design "Oikonos/Athos v3" (Comunidades + Pessoas feitos; replicar p/ Ministérios/Presença)
metadata:
  type: project
---

O dono exportou um bundle do Claude Design (`/tmp/design_bundle/oikonos/`) e quer recriar o LAYOUT DE CONTEÚDO das telas de lista no app. Piloto = Comunidades; depois Pessoas/Ministérios/Presença.

**Regra-chave:** recriar SÓ o `{% block content %}` (`{% extends 'app_base.html' %}`). NÃO tocar shell/sidebar/topbar/drawer (já existem). NÃO copiar o CSS cru do protótipo.

**Why:** o design system vivo do projeto JÁ casa com o bundle — `static/src/input.css` define `.card`/`.card-md`/`.stat-pill`/`.stat-icon`/`.stat-num`/`.stat-label`/`.eyebrow`/`.btn-terra`/`.btn-soft`/`.panel-card`/`.panel-dark`/`.list-row`/`.kpi-num`/`.soon-badge` + tokens Oikonos v2 (accent/hot/ink/muted/bg-soft/hairline/success/danger) + fontes Inter/Poppins + `.tnum`. Tints via `color-mix(in srgb, var(--accent) N%, transparent)`.

**How to apply (estrutura da tela de lista):**
1. Cabeçalho: eyebrow (`text-xs uppercase tracking-[0.16em] text-accent`) + `h1 font-display` + subtítulo `text-muted` + ações (busca + `.btn-terra` CTA).
2. KPIs: `{% include 'components/_stat_cards.html' with cards=stats.cards %}` (stat-pills).
3. Gráfico: `{% include 'components/_chart.html' with chart_id=... chart_type='bar' chart_title=... chart_payload=stats.chart %}`. **Manter chart_id e títulos exatos** — há testes de contrato (`assert 'cell-freq-chart' in html`, `assert 'Frequência por célula' in html`, `assert 'Lançamento pendente' in html` p/ Comunidades).
4. Grade de cards: `grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5`, cada card `.card .card-md p-5`, dados REAIS (sem % fabricado). Card-CTA tracejado no fim.
5. Empty state: `components/empty_state.html`.

**Busca:** sem filtro de backend → fiz filtro client-side Alpine (`x-data="{ q: '' }"` + `x-show` por nome/líder com `|escapejs|lower`). A lista já vem ESCOPADA por papel do servidor (RF-106). Filtro de "Região" do design foi OMITIDO (não há campo no model — evitar UI morta).

**Avatar/iniciais:** `{{ name|make_list|first|upper }}` (mesmo padrão de `templates/components/avatar.html` e `app_base.html`).

**Build CSS:** `node_modules/.bin/tailwindcss -i static/src/input.css -o static/css/app.css --minify` (Tailwind v4.3, CSS-first).

**Verificação:** `uv run pytest apps/communities -q` (28 verdes) + `uv run pytest apps/e2e/test_e2e_a11y.py -k community -q` (2 verdes, gate axe). E2E a11y compartilha banco `test_saas_igreja` → rodar SOZINHO.

**PESSOAS feito (`apps/people/templates/people/person_list.html`):** difere de Comunidades em pontos importantes:
- **Busca/filtros = SERVER-SIDE** (decisão do dono p/ Pessoas, ≠ client-side de Comunidades). Mantido o `<form method="get">` com `q`/`status`/`community`/`ministry`; o backend (`PersonListView.get_queryset`) filtra. Contexto: `filters`(=request.GET), `status_choices`, `communities`, `ministries`. Cada `<select>` tem `<label class="sr-only">` (gate axe exige label).
- **Layout = tabela (desktop md:block) + cards (mobile md:hidden)**, não grade de cards. Colunas: Pessoa(avatar+nome), Contato(email/phone, podem ser NULL→"Sem contato"), Situação(badge), Comunidade+ministérios(tags reais), "Membro desde"(`joined_at`, RF-125), Ações(ver/editar com `aria-label`).
- **Includes de analytics fixos:** `_stat_cards.html with cards=stats.cards` (contém card "Aniversariantes do mês") + `_chart.html` com `chart_id='people-status-chart'` e `chart_title='Pessoas por situação'`. Testes de contrato: `assert 'people-status-chart' in html`, `'Pessoas por situação'`, `'Aniversariantes do mês'`.
- **N+1:** rendi `person.ministries.all` (M2M) → tive de adicionar `.prefetch_related('ministries')` à queryset da view (testes rodam com `NPLUSONE_RAISE=True` em `core.settings.dev`). `community` já era `select_related`. Sem prefetch, a suite QUEBRA. Lição: ao renderizar FK/M2M novo numa lista, conferir o queryset da view.
- **Omitido (sem dado real):** idade, estado civil, "Envolvimento"/engajamento, selos de integração, checkboxes de seleção em massa, contadores fictícios. Status reais: visitor/congregant/member/leader/inactive. Badge: member/leader=success, inactive=muted, resto=accent.
- **"Tempo de casa":** `{{ joined_at|date:'Y' }}` + `há {{ joined_at|timesince }}` (built-ins; não há filtro custom de idade/anos).
- Verificação: `uv run pytest apps/people -q` (58 verdes) + `uv run pytest apps/e2e/test_e2e_a11y.py -k person_list -q` (1 verde, gate axe). Rodar a11y SOZINHO.

Ver [[shell-athos-v2]] e [[tailwind-v4-build]].
