# SPEC — Escalas v2 (escala coordenador-cêntrica)

> **Status:** ✅ IMPLEMENTADA (Blocos 1–3, 2026-06-11). RF-111..117 / RN-020..023 no PRD;
> OD-031 em OPEN_DECISIONS; ACCESS_MATRIX §3.7 atualizada; matrizes (permissões +
> isolamento) **175 passed** e a11y do modal (axe WCAG AA) verde. As **3 decisões** foram
> fechadas (2026-06-11): (a) membro já escalado = **cinza + escalável via aprovação de
> exceção**; (b) opt-out **por ministério, marcado pelo coordenador**; (c) gatilho de
> pendência **configurável por igreja, default dia 25** (→ OD-031). Aguarda só revisão
> visual/backend + versionamento do dono (G-03).

---

## 1. Contexto e problema

Hoje `apps/schedules` (Sprint 5) é um **CRUD seco**: List/Detail/Create/Update/Delete de
`Schedule` + `ScheduleExceptionCreateView` (aprovação de conflito de data, RN-010/011) +
`VolunteerScheduleView` (magic-link, OD-022). O dono descreveu como **"só um CRUD, não
intuitivo"**. O fluxo real é **coordenador-cêntrico**:

- O coordenador pensa por **evento** ("quem escalo pro culto de domingo?"), não por
  registro de escala isolado.
- Ele quer **abrir o evento**, ver **seus voluntários** (os membros dos ministérios que
  coordena) e **marcá-los** ali, num só lugar.
- Precisa **enxergar quem já está escalado em outro ministério na mesma data** (pra não
  sobrecarregar), mas com a opção de escalar mesmo assim.
- Quando o ministério dele **não vai atuar** num evento, ele quer **dizer isso** e sumir
  a pendência — sem ter que "não fazer nada" e ficar com alerta eterno.
- Quer ver os **eventos pendentes de escalar** como uma lista de afazeres, e que os
  eventos do **mês seguinte** comecem a cobrar a tempo (a partir do dia 25, configurável).

Esta spec redesenha o fluxo (**Escalas v2**) **reusando** `Schedule`,
`ScheduleConflictApproval`, `detect_conflict`/`approve_exception` e `ScopedToMinistryMixin`
— sem quebrar o magic-link do voluntário.

## 2. Papéis envolvidos (reusa ACCESS_MATRIX)

- **Coordenador (de ministério):** papel `leader` vinculado em `Ministry.coordinators`
  (M2M, OD-019). Opera **apenas os ministérios que coordena** (escopo já existe via
  `ScopedToMinistryMixin` → `coordinators__user_id`). Seus voluntários = `ministry.members`
  (`Person.ministries`) dos ministérios dele.
- **Pastor / Secretário (OD-019):** visão e gestão de **todos** os ministérios e escalas
  (Pastor sempre domina, RN-003a). Aprovam exceções de conflito (RN-010/011).
- **Voluntário:** consulta a própria escala via magic-link (OD-022) — **inalterado**.

## 3. Requisitos funcionais novos

| ID | Requisito |
|---|---|
| **RF-111** | **Tela de Escalas por evento:** lista **todos os cultos/eventos** (`Gathering`) da janela ativa (ver RF-116), cada um com indicador de **pendência de escala por ministério** do coordenador logado (Pastor/Sec veem todos os ministérios). Substitui a `ScheduleListView` (lista de registros) como entrada principal. |
| **RF-112** | **Pop-up de escalação:** clicar num evento abre um **modal** (HTMX) onde o coordenador vê **os voluntários dos ministérios que coordena** e marca **quem serve naquele evento**. Confirmar cria um `Schedule` por (pessoa, ministério, evento) — reusa `create_schedule`. |
| **RF-113** | **Sinalização "já escalado":** no modal, um voluntário **já escalado em outro ministério na mesma data** aparece **em cinza** com aviso *"já escalado nessa data"*. O coordenador **pode escalá-lo mesmo assim** → dispara o fluxo de **exceção** (`approve_exception` → `ScheduleConflictApproval`, RN-010/011: Pastor ou coordenador competente aprova com justificativa). |
| **RF-114** | **Opt-out por ministério/evento:** no evento, o coordenador pode marcar **"não atuaremos nesse evento"** para um ministério que coordena → **some a pendência** daquele ministério naquele evento. Reversível. (Novo model `MinistryEventOptOut`.) |
| **RF-115** | **Pendências do coordenador:** painel que lista os eventos da janela ativa que **ainda não têm escala nem opt-out** para os ministérios do coordenador — a "fila de afazeres" dele. Pastor/Sec veem a visão consolidada. |
| **RF-116** | **Janela de pendência configurável:** eventos do **mês corrente** sempre contam como pendência; eventos do **mês seguinte** passam a contar **a partir do dia `schedule_pending_open_day` da igreja** (default **25**). Antes desse dia, o próximo mês não gera pendência/alerta. |
| **RF-117** | **Cards/gráficos na tela de Escalas:** indicadores no topo (ex.: eventos pendentes, % de eventos com escala fechada, voluntários mais/menos escalados) no estilo do design exemplo. *(Liga no item transversal #6 — cards/gráficos por página; pode ser fatiado junto.)* |

## 4. Regras de negócio novas

| ID | Regra |
|---|---|
| **RN-020** | **Escala é coordenador-cêntrica:** o coordenador só escala **voluntários dos ministérios que coordena** (`ministries__coordinators__user_id` = `user.id`) e só nesses ministérios. Reusa `ScopedToMinistryMixin` (P-ARQ-08, 3 camadas). Pastor/Secretário não têm esse recorte. |
| **RN-021** | **Conflito de data:** voluntário já escalado em **outro ministério na mesma data** é sinalizado (cinza) mas **não bloqueado** — escalar exige **exceção aprovada** (`detect_conflict` + `approve_exception` → `ScheduleConflictApproval` + SecurityLog `schedule_exception_approved`). Mantém RN-010/011. |
| **RN-022** | **Opt-out por (ministério, evento):** registrado em `MinistryEventOptOut` (único por par). Marcado pelo **coordenador daquele ministério** (`marked_by_id` = user_id, TENANT-04). Pastor/Sec podem **remover** opt-out (dominância). Enquanto existir, o par (ministério, evento) **não é pendência** e o ministério não aparece escalável naquele evento (some do modal). |
| **RN-023** | **Gatilho de pendência configurável:** `Church.schedule_pending_open_day` (PositiveSmallInteger, **default 25**, faixa 1–28). Um evento de data no **mês `m+1`** só entra na janela ativa quando `hoje.day >= schedule_pending_open_day`. Eventos do **mês corrente** sempre estão na janela. (→ **OD-031**, decisão fechada: configurável.) |

## 5. Modelo de dados

### 5.1 Novo: `MinistryEventOptOut` (opt-out por ministério/evento) — TENANT

`apps/schedules/models.py`. Herda `BaseModel` + `AuditLogMixin` (1 AuditLog por marcação,
leve). **Unique** `(ministry, gathering)`.

```
class MinistryEventOptOut(BaseModel, AuditLogMixin):
    ministry   = ForeignKey('ministries.Ministry', on_delete=CASCADE, related_name='event_optouts')
    gathering  = ForeignKey('gatherings.Gathering', on_delete=CASCADE, related_name='ministry_optouts')
    marked_by_id = IntegerField()                 # user_id do coordenador (TENANT-04)
    reason     = CharField(max_length=120, blank=True, default='')  # opcional

    class Meta:
        unique_together = (('ministry', 'gathering'),)
```

- **Por que model próprio (e não flag no Schedule):** opt-out é a **ausência** de escala
  com intenção explícita — não há `Schedule` para pendurar a flag. Um registro por par
  resolve "esse ministério decidiu não atuar nesse evento".
- `on_delete=CASCADE` em ambos: se o evento ou o ministério somem, o opt-out perde sentido.

### 5.2 Config por igreja: `Church.schedule_pending_open_day` — PÚBLICO

`apps/tenants/models.py` (model `Church`, schema **public**). Campo novo →
**migração shared** (`migrate_schemas --shared`); afeta todos os tenants existentes com o
default.

```
schedule_pending_open_day = PositiveSmallIntegerField(
    default=25,
    validators=[MinValueValidator(1), MaxValueValidator(28)],
    help_text='Dia em que abrem as pendências de escala do mês seguinte.',
)
```

- Faixa 1–28 evita meses curtos (fevereiro). Editável na futura tela de configurações da
  igreja (fora desta spec; default cobre o MVP).

### 5.3 Reuso (nada muda)
- `Schedule` (person SET_NULL / OD-020), `ScheduleConflictApproval`, `detect_conflict`,
  `create_schedule(allow_conflict=...)`, `approve_exception`, `is_competent_approver`,
  `ScopedToMinistryMixin`, `VolunteerScheduleView` (magic-link).

## 6. Fluxos por papel

### 6.1 Coordenador
1. **Escalas** → lista de eventos da janela ativa (RF-111) + **pendências** dos
   ministérios dele em destaque (RF-115) + cards (RF-117).
2. Clica num evento → **modal** (RF-112): para cada ministério que coordena, o roster de
   voluntários com **marcar/desmarcar**; já-escalados-na-data em **cinza** com
   *"escalar mesmo assim"* (RF-113 → exceção, RN-021); botão **"Não atuaremos nesse
   evento"** por ministério (RF-114 → opt-out, RN-022); **Confirmar**.
3. A pendência some quando **todo** ministério dele naquele evento tem escala **ou**
   opt-out.

### 6.2 Pastor / Secretário
- Veem **todos** os ministérios/eventos e a visão consolidada de pendências.
- **Aprovam** exceções de conflito (RN-021) e podem **remover** opt-out (RN-022).

### 6.3 Voluntário
- **Inalterado:** consulta a própria escala por magic-link (OD-022).

## 7. Lógica de "pendência" (selector)

Um par **(ministério `M`, evento `E`)** é **pendência** quando, para o coordenador de `M`:
- `E.date` está na **janela ativa** (mês corrente; ou mês `m+1` se `hoje.day >=
  Church.schedule_pending_open_day` — RF-116/RN-023); **e**
- **não** existe `Schedule(ministry=M, gathering=E)`; **e**
- **não** existe `MinistryEventOptOut(ministry=M, gathering=E)`.

Selector em `apps/schedules/services.py` (ou `selectors.py`), com
`select_related/prefetch_related` (P-ARQ-09; `nplusone` raise nos testes).

## 8. Mudanças de acesso (ACCESS_MATRIX §3.7)

- **Escalas por evento (RF-111/112):** entrada = lista de eventos; escalar = coordenador
  no escopo dos seus ministérios (RN-020) / Pastor-Sec em todos.
- **Exceção (RF-113/RN-021):** aprovar = Pastor **ou** coordenador competente
  (`is_competent_approver`) — já existe.
- **Opt-out (RF-114/RN-022):** marcar = coordenador do ministério; remover = coordenador
  ou Pastor/Sec.
- Atualizar `test_permissions_matrix` (papel × ação) e `test_tenant_isolation_matrix`
  (rotas novas: modal de escalação, opt-out, pendências).

## 9. Telas (frontend, design Athos)

- **Escalas (lista de eventos):** cards/gráficos no topo (RF-117) + lista cronológica de
  eventos, cada um com **badge de pendência** (ex.: "2 ministérios pendentes") e ação
  *Escalar*. Filtro por mês reusa o padrão do calendário de Encontros.
- **Modal de escalação (HTMX + Alpine):** por ministério coordenado → roster (foto/nome)
  com toggle; já-escalado-na-data em **cinza** + *"escalar mesmo assim"* (abre confirm de
  exceção com justificativa); botão **"Não atuaremos nesse evento"**; **Confirmar**.
  Mobile-first, marcação em lote, estados vazio/loading em pt-BR; WCAG AA.
- **Pendências do coordenador:** painel/lista "eventos a escalar".

## 10. Fatiamento em blocos (proposto)

- **Bloco 1 — Backend/modelo:** `MinistryEventOptOut` + migration (tenant);
  `Church.schedule_pending_open_day` + migration **shared**; selector de pendências
  (janela configurável); services de escalação em lote (reusa `create_schedule`),
  opt-out (marcar/remover), e ligação com `approve_exception`; escopo coordenador
  (RN-020). Testes de service + isolamento.
- **Bloco 2 — Frontend:** tela de Escalas por evento (RF-111), modal de escalação
  (RF-112/113/114), painel de pendências (RF-115), cards (RF-117) no design Athos.
- **Bloco 3 — Matrizes/docs/fechamento:** `test_permissions_matrix` +
  `test_tenant_isolation_matrix` novas rotas; ACCESS_MATRIX §3.7; PRD RF-111..117 /
  RN-020..023; OPEN_DECISIONS OD-031; gate de cobertura; regressão + e2e (a11y do modal).

## 11. Testes mínimos (TEST_STRATEGY)

- `test_schedule_events_list_shows_pending_by_ministry` (RF-111/115).
- `test_coordinator_schedules_only_own_ministry_volunteers` (RN-020).
- `test_already_scheduled_same_date_is_greyed_not_blocked` (RF-113).
- `test_schedule_despite_conflict_requires_exception_approval` (RN-021, reusa fluxo).
- `test_ministry_event_optout_removes_pending` / `test_optout_unique_per_pair` (RF-114/RN-022).
- `test_optout_removable_by_pastor` (RN-022).
- `test_next_month_pending_only_after_open_day` (RF-116/RN-023 — testa antes/depois do dia configurado).
- `test_open_day_is_configurable_per_church` (RN-023/OD-031).
- Isolamento cross-tenant de todas as rotas novas (RISK-001).

## 12. Governança (G-05)

Introduz requisitos **novos** → antes de implementar:
1. Registrar **RF-111..117**, **RN-020..023** no PRD.
2. Registrar **OD-031** (gatilho de pendência configurável, default 25 — **fechada**) em
   OPEN_DECISIONS.
3. Aprovação do dono desta spec (G-02) e autorização de cada bloco (G-01).

> **Decisões fechadas (2026-06-11):** (a) cinza + exceção · (b) opt-out por ministério
> (coordenador marca) · (c) gatilho configurável por igreja (default 25). Nenhuma decisão
> de modelagem pendente — os 2 models novos (`MinistryEventOptOut`,
> `Church.schedule_pending_open_day`) decorrem direto das decisões.
