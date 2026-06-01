# Validação do TECH_SPEC — Tech Lead

> **Versão:** 1.0
> **Data:** 2026-06-01
> **Task:** Sprint 0 / Documentação — "Validar Tech Spec com Tech Lead" (`SPRINTS.md`)
> **Escopo:** validação documental (pré-implementação, SDD). Cross-check de `TECH_SPEC.md` contra `PRD.md` (source of truth), `ACCESS_MATRIX.md`, `TEST_STRATEGY.md`, `OPEN_DECISIONS.md`, `SPRINTS.md`.

## Status de aplicação das correções (2026-06-01)

Autorizado pelo dono (opção "a"). Achados endereçados nesta data:

| Achado | Nível | Status | Onde |
|---|---|---|---|
| C-1 — fixtures `role=` → `roles=[...]` (+ import `timezone`) | P0 | ✅ Aplicado | `TEST_STRATEGY.md §5` |
| A-1 — placement de schema de `AuditLog`/`SecurityLog` (TENANT_APPS) | P1 | ✅ Aplicado | `TECH_SPEC.md §5.9.1` |
| A-2 — tabela de stack completa (magic, decouple, anymail, nplusone, debug-toolbar, CI) | P1 | ✅ Aplicado | `TECH_SPEC.md §1` |
| A-3 — `MFARequiredForRoleMiddleware` registrado | P1 | ✅ Aplicado | `TECH_SPEC.md §2, SEC-08` |
| A-4 — enforcement LGPD na camada de service (cobre CSV) | P1 | ✅ Aplicado | `TECH_SPEC.md §OPS-05` + OD-018 |
| M-1 — OD-015/OD-016 nas decisões fechadas | P2 | ✅ Aplicado | `TECH_SPEC.md §13` |
| M-2 — ODs abertas com impacto técnico listadas | P2 | ✅ Aplicado | `TECH_SPEC.md §13` |
| M-3/B-2 — nota de performance/paginação + a11y | P2 | ✅ Aplicado | `TECH_SPEC.md §10 (A6/A7)` |
| M-4 — exceção de `BaseModel` para infra/tenant | P2 | ✅ Aplicado | `TECH_SPEC.md §3 (P-ARQ-02)` |
| B-1 — política de exclusão de Church | Baixo | ✅ Fechada como OD-017 (opção a: só suspender) | `OPEN_DECISIONS.md`, `PRD §29.1`, `TECH_SPEC §13` |
| A-4 (decisão formal) — camada canônica LGPD | P1 | ✅ Fechada como OD-018 (opção a: service + form) | `OPEN_DECISIONS.md`, `PRD §29.1`, `TECH_SPEC §13/§OPS-05` |
| B-3 — nota `is_active` BooleanField vs @property | Baixo | ℹ️ Apenas observação (sem mudança) | — |

> **Atualização 2026-06-01:** OD-017 e OD-018 foram **fechadas pelo dono** (ambas opção a). Todos os achados do relatório estão endereçados.

---

## Veredito geral

**APROVADO COM RESSALVAS.**

O TECH_SPEC é coerente, fiel ao PRD na maioria dos pontos críticos (multi-tenancy, princípios P-ARQ, anti-padrões AP, modelos, segurança) e suficiente para sustentar a Sprint 1. As ressalvas são inconsistências documentais e lacunas de especificação — nenhuma bloqueia o início da Sprint 1, mas várias **devem ser corrigidas antes da Sprint 2/3** sob risco de o dev decidir por inferência (violando G-05). Há **1 achado P0 real** (fixtures de teste contradizem o modelo de dados) que invalidaria a suite assim que escrita.

## Pontos fortes

- **Multi-tenancy fiel e completo.** TENANT-01..07 (`TECH_SPEC §4.2`) reproduzem `PRD §14.3`. `User` público com `user_id IntegerField`/`tenant_id CharField` em `AuditLog`/`SecurityLog` respeita TENANT-04 e RN-014. Sem FK cross-schema.
- **P-ARQ-01..09 idênticos ao PRD §19.3**, com aplicação prática (P-ARQ-09 com `nplusone raise_in_dev=True`).
- **AP-01..13 completos e sem contradição interna** (`TECH_SPEC §9`).
- **Modelos batem com `PRD §18.1`**: `Person` LGPD-aware, FKs `SET_NULL` para Person (RN-007), `Attendance unique(person, gathering)` (RN-009), `Schedule`/`ScheduleConflictApproval` com `approved_by_id IntegerField`, `Invite.roles ArrayField` + `unique_together`.
- **Decisões fechadas incorporadas:** OD-002, OD-003, OD-003a/007, OD-006, OD-012.
- **Healthcheck (RNF-022) concreto** (`/health/` e `/ready/` com Postgres + Redis, 200/503).
- **CI/CD (OD-015) coerente** com `TEST_STRATEGY §8`.

## Divergências e lacunas

### Crítico (P0)

- **C-1 — Fixtures de teste contradizem o modelo `roles` (RN-003a).** `TEST_STRATEGY.md` usa `role='pastor'` (singular, string) em `create_user(...)`. O modelo define `roles = ArrayField(...)` — não existe campo `role`. A suite não rodaria. **Correção:** atualizar fixtures para `roles=['pastor']` etc.

### Alto (P1)

- **A-1 — Placement de schema de `AuditLog`/`SecurityLog` não declarado.** Vivem "no schema do tenant" mas estão em `apps/core/models.py` junto de `BaseModel`/mixins (tipicamente SHARED). Risco de migrarem para `public` e quebrar RN-014/TENANT-04. **Correção:** declarar explicitamente TENANT_APPS para esses models ou separá-los.
- **A-2 — Tabela de stack (`TECH_SPEC §1`) incompleta.** Faltam: `python-magic`, `python-decouple`, `django-anymail[brevo]`, `django-storages`, `redis`, `nplusone`, `django-debug-toolbar`. É contrato direto do `pyproject.toml` da Sprint 1.
- **A-3 — `MFARequiredForRoleMiddleware` ausente do TECH_SPEC §2** (exigido por RF-018b, Sprint 7).
- **A-4 — Local de validação de `consent_given_at` ambíguo (RNF-007/RN-005).** Se ficar só no form, a importação CSV (RF-033 via Celery) burla a regra LGPD. **Correção:** validar na camada de service (espelhar no form).

### Médio (P2)

- **M-1 — `TECH_SPEC §13` omite OD-015 e OD-016** (ambas fechadas e usadas no próprio TECH_SPEC).
- **M-2 — ODs abertas com impacto em código não sinalizadas no §13:** OD-004 (agora fechada), OD-010 (retenção de logs), OD-014 (dupla confirmação).
- **M-3 — Sem suporte arquitetural explícito para RNF-011 (<500ms), RNF-012/RNF-020 (WCAG AA, Lighthouse ≥90).**
- **M-4 — `Plan`/`Church` não herdam `BaseModel`**, violando o texto literal de P-ARQ-02. Registrar exceção para models de infra/tenant.

### Baixo

- **B-1 — Política de exclusão de Church não especificada** (`User.church` é CASCADE; RF-003 só prevê suspender). Pode deixar `user_id` órfão no `AuditLog`.
- **B-2 — RNF-021 (paginação >25) não referenciado no TECH_SPEC**, só no PRD/TEST_STRATEGY.
- **B-3 — `PlatformAdmin.is_active` BooleanField vs `SupportAccess.is_active` @property** — coerente, apenas nota de implementação.

## Recomendações priorizadas

**P0 (antes de escrever testes / Sprint 2):**
1. Corrigir fixtures do `TEST_STRATEGY` para `roles=[...]` (C-1).
2. Declarar placement de schema de `AuditLog`/`SecurityLog` (A-1).
3. Completar a tabela de stack §1 (A-2).

**P1 (antes da Sprint 2/3):**
4. Especificar camada de validação de `consent_given_at` (service + form) cobrindo CSV (A-4).
5. Registrar `MFARequiredForRoleMiddleware` no §2 (A-3).
6. Atualizar §13: incluir OD-015/OD-016 fechadas e ODs abertas com impacto técnico (M-1, M-2).

**P2 (housekeeping):**
7. Definir política de exclusão de Church vs CASCADE (B-1).
8. Nota de performance/índices + a11y (M-3, B-2).
9. Registrar exceção de `BaseModel` para models de infra/tenant (M-4).

## Decisões sugeridas para `OPEN_DECISIONS.md`

- **Nova OD — Política de exclusão de tenant (Church)** (B-1). Impacto LGPD + integridade de `AuditLog`. Owner: Segurança + Produto.
- **Nova OD — Camada canônica de enforcement LGPD (`consent_given_at`)** (A-4). Owner: Tech Lead.
- **OD-010 (aberta)** deve ser vinculada explicitamente aos models `AuditLog`/`SecurityLog` no TECH_SPEC §5.9.
- Confirmar **OD-015/OD-016** refletidas no TECH_SPEC §13.

## Conclusão

TECH_SPEC aprovado como base da Sprint 1, **condicionado às correções P0** (C-1 e A-1 tocam segurança/tenancy e a suite de testes). As ressalvas P1/P2 são de coerência documental e devem ser endereçadas antes das sprints que as exercitam. Como várias correções tocam `TEST_STRATEGY.md` e `OPEN_DECISIONS.md` além do TECH_SPEC, **a decisão de quais ajustes entram agora é escalada ao dono** (G-04/G-05). Nenhum arquivo de spec foi alterado por esta validação.
