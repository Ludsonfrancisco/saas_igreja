# SPEC — Comunidades v2 (presença da célula)

> **Status:** ✅ IMPLEMENTADA (Blocos 1–3, 2026-06-11). RF-106..110 / RN-016..019 no
> PRD; ACCESS_MATRIX §3.4/§3.6 atualizadas; matrizes (permissões + isolamento) e a11y
> verdes. DM-1 (visitante = `Person` VISITOR) e DM-2 (`AttendanceSession`) aprovados
> pelo dono. Irmã da futura **SPEC — Escalas v2** (pendente de 3 decisões).

---

## 1. Contexto e problema

Hoje `apps/communities` e a presença (`apps/gatherings`) entregam um **CRUD seco**:
a lista de Comunidades mostra **todas** as células para qualquer papel de gestão, a
presença é marcada por dentro de **Encontros** (`/encontros/<id>/presenca/`) e não há
um lugar onde o **líder de célula** veja "as células que são minhas e os dias que
preciso lançar". O produto nasceu da rotina de célula: o líder precisa de um fluxo
**simples e escopado** para lançar a presença semanal da célula dele, com anotação do
que aconteceu, e o Pastor precisa enxergar a **frequência de todas as células**.

Esta spec redesenha esse fluxo (**Comunidades v2**) sem quebrar o que existe.

## 2. Papéis envolvidos (reusa ACCESS_MATRIX)

- **Líder (de comunidade):** papel `leader` vinculado como `Community.leaders`. Vê e
  opera **apenas a(s) célula(s) que lidera**.
- **Pastor / Secretário (OD-019) / autorizado pelo PR (Gestão de Acessos):** visão e
  gestão de **todas** as células.
- "Coordenador" (líder de ministério) **não** entra aqui — isto é célula, não escala.

## 3. Requisitos funcionais novos

| ID | Requisito |
|---|---|
| **RF-106** | A **lista de Comunidades** é escopada por papel: o `leader` vê só as células que lidera; Pastor/Secretário veem todas. (Hoje a *lista* não filtra — só o *detalhe*.) |
| **RF-107** | A **página da célula** (detalhe) lista **os dias a lançar presença** = os Encontros do tipo *Comunidade* (`Gathering.gathering_type=COMMUNITY`) vinculados àquela `Community`, com indicador de **lançado / pendente** por dia. |
| **RF-108** | **Lançamento de sessão de presença da célula:** ao abrir um dia, o líder vê a lista das pessoas que congregam na célula e marca **presente/falta**; pode **adicionar um visitante** (só o nome); preenche **anotações do dia** (texto livre — o que aconteceu, quem fez o quê); e clica em **Confirmar**. O confirmar persiste presença (`update_or_create`, RN-009) + a sessão (RN-016). |
| **RF-109** | **Frequência:** a página de Comunidades mostra um **card de frequência da célula** (para o líder, a dele; uma por célula liderada). Para Pastor/Secretário, um **resumo de frequência de todas as células**. (Liga no item de cards/gráficos transversal.) |
| **RF-110** | **Encontros** permanece como as **programações gerais da igreja**. Criar encontro = **Pastor/Secretário**. O **líder pode editar somente a DATA** do encontro de *Comunidade* da célula dele (nenhum outro campo). |

## 4. Regras de negócio novas

| ID | Regra |
|---|---|
| **RN-016** | A **anotação do dia** é **por sessão/reunião** (1 por Encontro de célula), **não** por pessoa. Guarda o texto, **quem confirmou** (`confirmed_by` = user_id, TENANT-04) e **quando** (`confirmed_at`). |
| **RN-017** | **Visitante** adicionado pelo líder no lançamento cria uma `Person` com `status=VISITOR` (o status já existe) vinculada à célula (`community`), marcada presente naquela sessão. Visitante **não é membro**: criá-lo é permitido ao líder; **promover a membro** segue RN-019. |
| **RN-018** | **Criar `Gathering` = Pastor/Secretário.** O líder **não cria** encontros; só **edita a `date`** dos encontros de *Comunidade* da célula que lidera (date-only; tipo/título/comunidade travados). |
| **RN-019** | **Adicionar/remover MEMBRO de uma célula = só Pastor/Secretário** (define `Person.community`). O líder **não** altera o quadro de membros — só lança presença e adiciona visitante (RN-017). |

## 5. Modelo de dados

### 5.1 Novo: `AttendanceSession` (1:1 com o Encontro de célula)

`apps/gatherings/models.py` (ou `apps/communities` — decidir na implementação; fica
junto da presença). Herda `BaseModel`.

```
class AttendanceSession(BaseModel):
    gathering   = OneToOneField('Gathering', on_delete=CASCADE, related_name='session')
    note        = TextField(blank=True)              # RN-016 — anotações do dia
    confirmed_at = DateTimeField(null=True, blank=True)
    confirmed_by = IntegerField(null=True, blank=True)  # user_id (TENANT-04)
```

- **Por que 1:1 com `Gathering` e não campo no `Gathering`:** mantém o `Gathering`
  (programação geral) limpo e abre espaço para "confirmado em/por" sem inflar o model
  de encontro. Só encontros de *Comunidade* que tiveram lançamento ganham sessão.
- **Sem auditoria por linha de presença** (mantém OD-020). A **confirmação da sessão**
  pode gerar 1 `AuditLog` (`action=update`/`create`) — leve, 1 por dia/célula.
- `Attendance` **não muda** (person/gathering/is_present; SET_NULL; unique).

### 5.2 Visitante

Sem model novo: `Person(status=VISITOR, community=<célula>)` criado no ato do
lançamento + `Attendance(is_present=True)`. (Decisão de modelagem #1 — **proposta**.)

> **Decisão de modelagem (a confirmar pelo dono):**
> - **DM-1 (visitante):** reusar `Person.Status.VISITOR` vinculado à célula. *(recomendado)*
> - **DM-2 (nota do dia):** `AttendanceSession` 1:1 com o Encontro. *(recomendado)*

## 6. Fluxos por papel

### 6.1 Líder
1. **Comunidades** → vê só a(s) célula(s) dele (RF-106) + card de frequência (RF-109).
2. Clica na célula → **dias a lançar** (RF-107): lista de encontros de Comunidade da
   célula, com badge *Pendente/Lançado*.
3. Abre um dia pendente → **tela de lançamento** (RF-108): roster (membros da célula)
   com presente/falta + "Adicionar visitante" (nome) + "Anotações do dia" + **Confirmar**.
4. Pode **editar a data** de um encontro da célula (RF-110/RN-018) — nada mais.

### 6.2 Pastor / Secretário
- Veem todas as células (RF-106) + **frequência de todas** (RF-109).
- **Criam** encontros (RN-018) e **gerenciam membros** da célula (RN-019).
- Podem lançar presença de qualquer célula (já coberto por `can_mark_attendance`).

## 7. Mudanças de acesso (ACCESS_MATRIX)

- **§3.4 Comunidades:** lista escopada (RF-106); "adicionar membro" só Pastor/Secretário (RN-019).
- **§3.6 Encontros e Presença:** criar encontro = Pastor/Secretário; líder edita só `date`
  (RN-018); lançamento de sessão + visitante pelo líder (RF-108/RN-017); nota da sessão (RN-016).
- Atualizar `test_permissions_matrix` e `test_tenant_isolation_matrix` para as rotas novas.

## 8. Telas (frontend, design Athos)
- **Comunidades (lista):** cards das células do escopo + card/resumo de frequência (RF-109).
- **Célula (detalhe):** cabeçalho da célula + lista "dias a lançar" (Pendente/Lançado).
- **Lançamento da sessão:** roster com toggle presente/falta (mobile-first, marcação em
  lote <2 min — RNF de usabilidade), bloco "Adicionar visitante", textarea "Anotações
  do dia", botão Confirmar. Estados vazios/loja em pt-BR.

## 9. Fatiamento em blocos (proposto)

- **Bloco 1 — Backend/modelo:** `AttendanceSession` + migration; service de lançamento
  de sessão (presente/falta em lote + visitante VISITOR + nota + confirm) reusando
  `update_or_create`; escopo de lista de comunidades (RF-106); restrição de criação de
  encontro e edição date-only (RN-018); trava de membro (RN-019). Testes de service +
  isolamento.
- **Bloco 2 — Frontend:** telas §8 no design system; expor lançamento dentro de
  Comunidades; cards de frequência (RF-109).
- **Bloco 3 — Matrizes/docs/fechamento:** `test_permissions_matrix` +
  `test_tenant_isolation_matrix` novas rotas; ACCESS_MATRIX §3.4/§3.6; PRD RF-106..110 /
  RN-016..019; gate de cobertura; regressão verde.

## 10. Testes mínimos (TEST_STRATEGY)
- `test_community_list_scoped_to_leader` (líder só vê a dele; pastor vê todas).
- `test_cell_pending_days_from_community_gatherings` (RF-107).
- `test_leader_launch_attendance_session` (presente/falta + confirm persiste; RN-009).
- `test_leader_adds_visitor_creates_visitor_person` (RN-017).
- `test_session_note_is_per_session_not_per_person` (RN-016).
- `test_leader_cannot_create_gathering` / `test_leader_edits_only_gathering_date` (RN-018).
- `test_leader_cannot_add_member_to_cell` (RN-019).
- Isolamento cross-tenant de todas as rotas novas (RISK-001).

---

## 11. Escalas v2 — PENDENTE (não especificada ainda)

A **SPEC — Escalas v2** (item #5 do backlog) é irmã desta, mas precisa de **3 decisões
do dono** antes de eu escrever:
1. Colaborador **já escalado em outra data/ministério** aparece em **cinza** = trava
   absoluta **ou** dá pra escalar mesmo assim via aprovação de exceção (o fluxo
   `ScheduleConflictApproval`/RN-010 que já existe)?
2. **"Não atuaremos nesse evento"** é decisão **por ministério** (cada coordenador
   marca o seu), certo?
3. A regra **"eventos do mês seguinte sinalizam pendência no dia 25"** é **fixa** ou
   **configurável por igreja**?

Respondidas essas, escrevo a SPEC — Escalas v2 no mesmo formato.
