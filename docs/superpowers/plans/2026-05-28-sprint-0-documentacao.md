# Sprint 0 — Documentação: Validação Final Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Concluir as 2 tasks pendentes da seção "Documentação" da Sprint 0 — validar `PRD.md` com o líder principal do produto e validar `docs/TECH_SPEC.md` com o Tech Lead — produzindo relatórios de auditoria estruturados que o dono do projeto possa aprovar.

**Architecture:** Cada validação consiste em (1) auditoria automatizada via agente `code-reviewer-tech-lead`, (2) geração de relatório de findings em `docs/superpowers/reviews/`, (3) handoff ao dono para signoff explícito, (4) registro da decisão e marcação `[x]` em `docs/SPRINTS.md`. Sem signoff do dono → task permanece `[ ]` (G-02).

**Tech Stack:** Markdown + agente `code-reviewer-tech-lead` (Sonnet) executando contra `PRD.md`, `docs/TECH_SPEC.md` e os documentos auxiliares (`ACCESS_MATRIX.md`, `TEST_STRATEGY.md`, `SPRINTS.md`, `OPEN_DECISIONS.md`, `README.md`).

---

## Pré-requisitos e governança

- **G-01:** Sprint 0 já autorizada (em andamento). Esta execução foi explicitamente solicitada pelo dono via comando `/writing-plans`.
- **G-02:** Toda task aqui produz artefato de revisão; marcar `[x]` exige signoff do dono. Se o relatório apontar bloqueadores, **não marcar** e devolver para correção.
- **G-03:** Nenhum `git commit`/`git push`/`git merge` durante este plano. Mudanças ficam no workspace.
- **G-04:** Relatórios ficam em `docs/superpowers/reviews/` para revisão do dono.
- **G-05:** Se algum agente sugerir mudança fora do escopo da task (ex.: criar nova seção no PRD), consultar dono antes de aplicar.

## Estrutura de arquivos

- Criar: `docs/superpowers/reviews/2026-05-28-prd-validation.md` — Relatório da auditoria do PRD.
- Criar: `docs/superpowers/reviews/2026-05-28-tech-spec-validation.md` — Relatório da auditoria do TECH_SPEC.
- Modificar: `docs/SPRINTS.md` — marcar `[x]` apenas após signoff do dono (linhas 51 e 52 da seção Documentação da Sprint 0).

Cada relatório é fonte única de verdade da validação correspondente. Não duplicar conteúdo em outro lugar.

---

## Task 1: Validar PRD com líder principal do produto

**Files:**
- Read: `/home/ludsoncorrea/Documentos/projects/saas_igreja/PRD.md`
- Read (referência cruzada): `/home/ludsoncorrea/Documentos/projects/saas_igreja/docs/SPRINTS.md`, `/home/ludsoncorrea/Documentos/projects/saas_igreja/docs/OPEN_DECISIONS.md`, `/home/ludsoncorrea/Documentos/projects/saas_igreja/docs/ACCESS_MATRIX.md`
- Create: `/home/ludsoncorrea/Documentos/projects/saas_igreja/docs/superpowers/reviews/2026-05-28-prd-validation.md`
- Modify (após signoff): `/home/ludsoncorrea/Documentos/projects/saas_igreja/docs/SPRINTS.md` linha 51

### Escopo da auditoria (checklist do reviewer)

A auditoria do PRD valida critérios **de produto** (não técnicos). O reviewer deve verificar:

1. **Capa e governança (§1, §1.1):** versão, data, dono identificados; G-01..G-05 explícitos.
2. **Personas e papéis (§2..§5):** Pastor, Líder, Coordenador, Tesoureiro, Secretaria, Membro, PlatformAdmin definidos com responsabilidades claras; multi-role (RN-003a) documentado.
3. **Requisitos funcionais (RF-001..RF-101):** numeração contínua; cada RF tem ator, ação, critério de aceite; nenhum RF órfão (sem sprint vinculada).
4. **Requisitos não-funcionais (RNF-001..RNF-024):** segurança, performance, LGPD, observabilidade, RTO/RPO citados; thresholds quantificáveis (ex.: "<2s", "≥99%", "≤10MB").
5. **Regras de negócio (RN-001..RN-015):** RN-003 (1 user → 1 igreja), RN-003a (multi-role união), RN-004 (último Pastor), RN-005..RN-007 (LGPD), RN-009 (unique Attendance), RN-010 (COMMUNITY oculto), RN-015 (SupportAccess) todas presentes.
6. **Riscos (RISK-001..RISK-009):** tenant leak (RISK-001) e SupportAccess (RISK-009) com mitigação e teste vinculado.
7. **Linguagem de domínio (pt-BR):** Pessoa, Comunidade, Ministério, Encontro, Presença, Escala alinhados a `CLAUDE.md` e `TECH_SPEC.md`.
8. **Sprints (§28 ou equivalente):** 8 sprints (0–7) batem com `docs/SPRINTS.md`.
9. **Decisões fechadas vs. abertas:** OD-002, OD-003, OD-003a, OD-006, OD-007, OD-012 marcadas como fechadas; OD-001, OD-004, OD-005, OD-008, OD-011, OD-013, OD-014, OD-015 marcadas como abertas em `OPEN_DECISIONS.md`.
10. **Consistência de domínio entre documentos:** termos e papéis idênticos em `PRD.md`, `ACCESS_MATRIX.md`, `TECH_SPEC.md`, `CLAUDE.md`.

### Steps

- [ ] **Step 1: Acionar o agente `code-reviewer-tech-lead` para auditar o PRD**

Despachar via Agent tool com este prompt (self-contained — o agente não vê este plano):

```text
Você está auditando o `PRD.md` do projeto SaaS Igreja como parte da validação final da
Sprint 0 (task "Validar PRD com líder principal do produto" — linha 51 de
docs/SPRINTS.md). Repositório em /home/ludsoncorrea/Documentos/projects/saas_igreja.

ESCOPO: Validação de PRODUTO, não de código. Não há código ainda (pré-implementação).

LEIA estes arquivos antes de auditar:
- /home/ludsoncorrea/Documentos/projects/saas_igreja/PRD.md
- /home/ludsoncorrea/Documentos/projects/saas_igreja/CLAUDE.md (referência cruzada de governança e domínio)
- /home/ludsoncorrea/Documentos/projects/saas_igreja/docs/SPRINTS.md
- /home/ludsoncorrea/Documentos/projects/saas_igreja/docs/OPEN_DECISIONS.md
- /home/ludsoncorrea/Documentos/projects/saas_igreja/docs/ACCESS_MATRIX.md
- /home/ludsoncorrea/Documentos/projects/saas_igreja/docs/TEST_STRATEGY.md

CHECKLIST DE AUDITORIA (responder cada ponto com PASS/FAIL/PARTIAL + evidência via
referência `arquivo:linha`):

1. Capa, versão, data, dono identificados (§1).
2. Governança G-01..G-05 explícita e idêntica em PRD §1.1 e CLAUDE.md.
3. Personas (Pastor, Líder, Coordenador, Tesoureiro, Secretaria, Membro,
   PlatformAdmin) com responsabilidades claras.
4. RF-001..RF-101: numeração contínua; cada RF tem ator, ação, critério de aceite;
   cada RF vinculado a uma sprint em docs/SPRINTS.md.
5. RNF-001..RNF-024: cobrem segurança, performance, LGPD, observabilidade, RTO/RPO;
   thresholds quantificáveis.
6. RN-001..RN-015: presentes; em especial RN-003 (1 user → 1 igreja),
   RN-003a (multi-role união), RN-004 (último Pastor), RN-005..RN-007 (LGPD),
   RN-009 (unique Attendance), RN-010 (COMMUNITY oculto), RN-015 (SupportAccess).
7. RISK-001..RISK-009: com mitigação e teste vinculado (especialmente RISK-001
   tenant leak e RISK-009 SupportAccess).
8. Linguagem de domínio pt-BR consistente entre PRD, ACCESS_MATRIX, CLAUDE.md.
9. 8 sprints (0–7) no PRD batem com docs/SPRINTS.md.
10. Decisões fechadas (OD-002, OD-003, OD-003a, OD-006, OD-007, OD-012) marcadas
    como fechadas no PRD §29 e em OPEN_DECISIONS.md. Decisões abertas idem.
11. Multi-role (RN-003a) documentado claramente como UNIÃO de permissões e exemplo
    `['treasurer', 'leader']` consistente entre PRD, ACCESS_MATRIX e CLAUDE.md.
12. LGPD: §RN-005..RN-007 detalham consent_given_at obrigatório, anonymize_person,
    purge 30 dias via Celery Beat, FK SET_NULL, export_person_data.

ENTREGA: Relatório markdown salvo em
/home/ludsoncorrea/Documentos/projects/saas_igreja/docs/superpowers/reviews/2026-05-28-prd-validation.md

ESTRUTURA OBRIGATÓRIA do relatório:

```
# Relatório de Validação — PRD.md
**Data:** 2026-05-28
**Reviewer:** code-reviewer-tech-lead (agente)
**Documento:** PRD.md
**Task vinculada:** docs/SPRINTS.md linha 51 — "Validar PRD com líder principal do produto"

## Veredicto
APROVADO | APROVADO COM RESSALVAS | REPROVADO

## Sumário executivo
3-5 linhas resumindo o estado do PRD.

## Checklist (12 pontos)
Tabela com: ID | Item | Status (PASS/FAIL/PARTIAL) | Evidência (arquivo:linha) | Observação

## Bloqueadores (FAIL)
Lista de itens que impedem aprovação. Vazio se nenhum.

## Ressalvas (PARTIAL)
Lista de pontos a ajustar mas não bloqueantes.

## Recomendações opcionais
Sugestões fora do escopo de aprovação.

## Conclusão
1 parágrafo orientando o dono sobre próximos passos.
```

NÃO modifique PRD.md nem SPRINTS.md. Apenas crie o relatório.
NÃO faça git commit/push/merge (G-03).
Reporte de volta o caminho do arquivo criado + veredicto.
```

Expected: Agente cria `docs/superpowers/reviews/2026-05-28-prd-validation.md` e devolve veredicto.

- [ ] **Step 2: Verificar que o relatório foi criado**

Run: `ls -la /home/ludsoncorrea/Documentos/projects/saas_igreja/docs/superpowers/reviews/2026-05-28-prd-validation.md`
Expected: Arquivo existe, tamanho > 0.

- [ ] **Step 3: Ler o relatório e extrair o veredicto**

Read: `/home/ludsoncorrea/Documentos/projects/saas_igreja/docs/superpowers/reviews/2026-05-28-prd-validation.md`

Expected: Identificar veredicto (APROVADO / APROVADO COM RESSALVAS / REPROVADO), lista de bloqueadores, lista de ressalvas.

- [ ] **Step 4: Handoff ao dono via AskUserQuestion**

Apresentar ao dono:
- Caminho do relatório
- Veredicto
- Resumo de bloqueadores (se houver)
- Resumo de ressalvas (se houver)

Pergunta ao dono (via AskUserQuestion):

```
Pergunta: "Aprovar a validação do PRD com base no relatório?"
Header: "PRD signoff"
Opções:
- "Aprovar e marcar [x]" → dono aceita o PRD como source of truth e autoriza marcar
  a task como concluída.
- "Aprovar com ressalvas (marcar [x], ajustar depois)" → marca [x] e registra
  ressalvas para tratar fora desta task.
- "Reprovar — corrigir antes" → não marca [x]; aguarda correção e nova auditoria.
```

Sem resposta do dono → **NÃO** marcar `[x]` (G-02). Parar a task aqui.

- [ ] **Step 5: Marcar [x] em docs/SPRINTS.md (somente se aprovado)**

Se dono aprovou (opções 1 ou 2), aplicar via Edit em `/home/ludsoncorrea/Documentos/projects/saas_igreja/docs/SPRINTS.md`:

```text
old_string: - [ ] (P0) Validar PRD com líder principal do produto
new_string: - [x] (P0) Validar PRD com líder principal do produto
```

Se reprovou → pular este step.

- [ ] **Step 6: Confirmar marcação**

Read: `/home/ludsoncorrea/Documentos/projects/saas_igreja/docs/SPRINTS.md` linha 51

Expected: `- [x] (P0) Validar PRD com líder principal do produto`

- [ ] **Step 7: NÃO commitar (G-03)**

Não rodar `git add` / `git commit` / `git push`. Apenas reportar ao dono que o workspace está pronto para revisão.

---

## Task 2: Validar Tech Spec com Tech Lead

**Files:**
- Read: `/home/ludsoncorrea/Documentos/projects/saas_igreja/docs/TECH_SPEC.md`
- Read (referência cruzada): `/home/ludsoncorrea/Documentos/projects/saas_igreja/PRD.md`, `/home/ludsoncorrea/Documentos/projects/saas_igreja/CLAUDE.md`, `/home/ludsoncorrea/Documentos/projects/saas_igreja/docs/ACCESS_MATRIX.md`, `/home/ludsoncorrea/Documentos/projects/saas_igreja/docs/TEST_STRATEGY.md`, `/home/ludsoncorrea/Documentos/projects/saas_igreja/docs/OPEN_DECISIONS.md`
- Create: `/home/ludsoncorrea/Documentos/projects/saas_igreja/docs/superpowers/reviews/2026-05-28-tech-spec-validation.md`
- Modify (após signoff): `/home/ludsoncorrea/Documentos/projects/saas_igreja/docs/SPRINTS.md` linha 52

### Escopo da auditoria (checklist do reviewer)

A auditoria do TECH_SPEC valida critérios **técnicos**:

1. **Stack oficial** bate com `CLAUDE.md` (Django 5.2, HTMX, Alpine, Tailwind, Postgres 15+, django-tenants, allauth, axes, Celery+Redis, R2, Brevo, Hostinger KVM 2, EasyPanel, Cloudflare, pytest, Ruff+Black, uv, GitHub Actions, Sentry).
2. **Stack proibida** lista SQLite (AP-13), Next/React SPA, Prisma, Auth.js, FastAPI, SQLAlchemy, WhatsApp Cloud, LangChain, Stripe, Prometheus, `fields='__all__'`, `@csrf_exempt`, raw SQL com f-string.
3. **Princípios P-ARQ-01..P-ARQ-09** todos presentes com descrição clara; P-ARQ-09 (N+1) cita `select_related`/`prefetch_related`/`nplusone`.
4. **Anti-padrões AP-01..AP-13** todos presentes com motivo e alternativa.
5. **Models completos** para User, Invite, PlatformAdmin, SupportAccess, Church, Plan, Domain, Person, Community, Ministry, Gathering, Attendance, Schedule, ScheduleConflictApproval, FileAsset, AuditLog, SecurityLog, BaseModel.
6. **Multi-tenancy:** `TenantMiddleware` (subdomínio → `SET search_path`), TENANT-04 (`User` em SHARED_APPS, sem FK cross-schema), TENANT-05 (`TenantRequiredMixin` mandatório).
7. **Multi-role:** `roles ArrayField`, `has_any_role`/`has_all_roles`, validação último Pastor (RN-004).
8. **LGPD:** `consent_given_at`, `anonymize_person`, `export_person_data`, `purge_anonymized_persons` Celery Beat, FK `SET_NULL`.
9. **Healthcheck:** `/health/` (liveness 200) e `/ready/` (readiness 200/503 Postgres+Redis).
10. **CI/CD:** GitHub Actions com Ruff, Black, pip-audit, safety, pytest, service containers Postgres+Redis, cobertura ≥80%.
11. **Segurança:** headers (HSTS, X-Frame, CSP), cookies (Secure, HttpOnly, SameSite), MFA TOTP (opt-in S2, enforced S7), Sentry `before_send` sanitiza PII + tag `tenant_id`, `python-magic` MIME, rejeita SVG, signed URL R2 TTL 60s, path `{schema}/{model}/{id}/{filename}`.
12. **Convites:** unique `(church, email)`, token UUID, expiração 7 dias, sem enumeração no reset.
13. **Backup/Restore:** RTO 4h / RPO 24h documentados; cron `pg_dump` diário; R2 retenção 30d; runbook `RESTORE.md` previsto.
14. **Service Layer:** P-ARQ-04 explica camada service leve, lógica de domínio fora das views.
15. **Signals:** P-ARQ-06 obriga `signals.py` por app.
16. **TextChoices:** P-ARQ-07 (não booleanos compostos).
17. **Domain language pt-BR** consistente.
18. **Decisões abertas** (OD-001, OD-004, OD-005, OD-008, OD-011, OD-013, OD-014, OD-015) reconhecidas onde tocam stack/arquitetura.

### Steps

- [ ] **Step 1: Acionar o agente `code-reviewer-tech-lead` para auditar o TECH_SPEC**

Despachar via Agent tool com este prompt (self-contained):

```text
Você está auditando o `docs/TECH_SPEC.md` do projeto SaaS Igreja como parte da
validação final da Sprint 0 (task "Validar Tech Spec com Tech Lead" — linha 52 de
docs/SPRINTS.md). Repositório em /home/ludsoncorrea/Documentos/projects/saas_igreja.

ESCOPO: Validação TÉCNICA do TECH_SPEC.md. Não há código ainda (pré-implementação),
então a auditoria foca em consistência da especificação contra PRD, ACCESS_MATRIX,
TEST_STRATEGY, OPEN_DECISIONS e CLAUDE.md.

LEIA estes arquivos antes de auditar:
- /home/ludsoncorrea/Documentos/projects/saas_igreja/docs/TECH_SPEC.md (alvo)
- /home/ludsoncorrea/Documentos/projects/saas_igreja/PRD.md
- /home/ludsoncorrea/Documentos/projects/saas_igreja/CLAUDE.md
- /home/ludsoncorrea/Documentos/projects/saas_igreja/docs/ACCESS_MATRIX.md
- /home/ludsoncorrea/Documentos/projects/saas_igreja/docs/TEST_STRATEGY.md
- /home/ludsoncorrea/Documentos/projects/saas_igreja/docs/OPEN_DECISIONS.md
- /home/ludsoncorrea/Documentos/projects/saas_igreja/docs/SPRINTS.md

CHECKLIST DE AUDITORIA (18 pontos — responder cada com PASS/FAIL/PARTIAL +
evidência `arquivo:linha`):

1. Stack oficial idêntica em TECH_SPEC e CLAUDE.md: Django 5.2, HTMX, Alpine.js,
   TailwindCSS, Postgres 15+, django-tenants, django-allauth, django-axes, Celery,
   Redis, Cloudflare R2 via django-storages, Brevo via django-anymail, Hostinger
   KVM 2, EasyPanel Free, Cloudflare Free, pytest+pytest-django+pytest-cov+nplusone,
   Ruff+Black, uv, GitHub Actions, Sentry.
2. Stack proibida cobre: SQLite (AP-13), Next.js/React SPA/Vue SPA, Prisma,
   Auth.js, FastAPI, SQLAlchemy, WhatsApp Business Cloud API, LangChain/LangGraph,
   Stripe, Prometheus/Grafana, `fields='__all__'`, `@csrf_exempt`, raw SQL com
   f-strings.
3. P-ARQ-01..P-ARQ-09 todos presentes e descritos. P-ARQ-09 cita
   `select_related`/`prefetch_related` + `nplusone` raise em testes.
4. AP-01..AP-13 todos presentes com motivo e alternativa correta.
5. Models completos: BaseModel, User, Invite, PlatformAdmin, SupportAccess,
   Church, Plan, Domain, Person, Community, Ministry, Gathering, Attendance,
   Schedule, ScheduleConflictApproval, FileAsset, AuditLog, SecurityLog.
6. Multi-tenancy: TenantMiddleware (subdomain → SET search_path), TENANT-04
   (User em SHARED_APPS, sem FK cross-schema, models de tenant usam
   `user_id IntegerField` + `tenant_id CharField`), TENANT-05
   (TenantRequiredMixin mandatório em toda view autenticada).
7. Multi-role: `roles ArrayField(CharField(choices=Role.choices))`,
   `has_any_role`/`has_all_roles`, validação RN-004 último Pastor.
8. LGPD: `consent_given_at` obrigatório quando email/telefone,
   `anonymize_person()` soft delete + PII substituída, Celery Beat semanal
   `purge_anonymized_persons` após 30 dias, FK Person `SET_NULL`,
   `export_person_data()` JSON+CSV com AuditLog action=export.
9. Healthcheck: `/health/` liveness sempre 200 sem auth; `/ready/` readiness
   verifica Postgres+Redis retornando 200/503.
10. CI/CD GitHub Actions: Ruff, Black, pip-audit, safety, pytest com Postgres+Redis
    service containers, cobertura mínima 80%.
11. Segurança: HSTS, X-Frame-Options, CSP, referrer-policy; cookies Secure+
    HttpOnly+SameSite; MFA TOTP allauth (opt-in Sprint 2, enforced Sprint 7 para
    Pastor e PlatformAdmin); Sentry `before_send` sanitiza email/telefone e tag
    `tenant_id`; python-magic valida MIME; rejeita SVG; signed URL R2 TTL 60s;
    path `{tenant_schema}/{model}/{object_id}/{filename}`.
12. Convites: `unique_together=('church', 'email')`, token UUID, expiração 7 dias,
    password reset sem enumeração (mensagem e tempo idênticos).
13. Backup/Restore: RTO 4h / RPO 24h documentados; cron pg_dump diário; upload R2
    com retenção 30 dias; `RESTORE.md` previsto + teste mensal.
14. P-ARQ-04 Service Layer leve: lógica de domínio em `services.py`, view fina.
15. P-ARQ-06 Signals em `signals.py` por app.
16. P-ARQ-07 TextChoices em vez de booleanos compostos.
17. Domain language pt-BR (Pessoa, Comunidade, Ministério, Encontro, Presença,
    Escala, Líder Principal) consistente entre TECH_SPEC, PRD, ACCESS_MATRIX,
    CLAUDE.md.
18. Decisões abertas reconhecidas onde tocam stack/arquitetura: OD-001 (Plan),
    OD-004 (login Membro), OD-005/OD-011 (DPO/incidente), OD-008 (OAuth2),
    OD-013 (templates de privacidade), OD-014 (confirmação anonimização),
    OD-015 (CI/CD — já fechada como GitHub Actions, verificar consistência).

ENTREGA: Relatório markdown salvo em
/home/ludsoncorrea/Documentos/projects/saas_igreja/docs/superpowers/reviews/2026-05-28-tech-spec-validation.md

ESTRUTURA OBRIGATÓRIA do relatório:

```
# Relatório de Validação — docs/TECH_SPEC.md
**Data:** 2026-05-28
**Reviewer:** code-reviewer-tech-lead (agente)
**Documento:** docs/TECH_SPEC.md
**Task vinculada:** docs/SPRINTS.md linha 52 — "Validar Tech Spec com Tech Lead"

## Veredicto
APROVADO | APROVADO COM RESSALVAS | REPROVADO

## Sumário executivo
3-5 linhas resumindo o estado técnico do TECH_SPEC.

## Checklist (18 pontos)
Tabela com: ID | Item | Status (PASS/FAIL/PARTIAL) | Evidência (arquivo:linha) | Observação

## Bloqueadores (FAIL)
Lista de itens que impedem aprovação. Vazio se nenhum.

## Ressalvas (PARTIAL)
Lista de pontos a ajustar mas não bloqueantes.

## Risco arquitetural residual
Áreas onde o TECH_SPEC pode gerar problema na Sprint 1+ (cite RISK-IDs do PRD).

## Recomendações opcionais
Sugestões fora do escopo de aprovação.

## Conclusão
1 parágrafo orientando o dono sobre próximos passos.
```

NÃO modifique TECH_SPEC.md nem SPRINTS.md. Apenas crie o relatório.
NÃO faça git commit/push/merge (G-03).
Reporte de volta o caminho do arquivo criado + veredicto.
```

Expected: Agente cria `docs/superpowers/reviews/2026-05-28-tech-spec-validation.md` e devolve veredicto.

- [ ] **Step 2: Verificar que o relatório foi criado**

Run: `ls -la /home/ludsoncorrea/Documentos/projects/saas_igreja/docs/superpowers/reviews/2026-05-28-tech-spec-validation.md`
Expected: Arquivo existe, tamanho > 0.

- [ ] **Step 3: Ler o relatório e extrair o veredicto**

Read: `/home/ludsoncorrea/Documentos/projects/saas_igreja/docs/superpowers/reviews/2026-05-28-tech-spec-validation.md`

Expected: Identificar veredicto (APROVADO / APROVADO COM RESSALVAS / REPROVADO), bloqueadores, ressalvas, risco arquitetural residual.

- [ ] **Step 4: Handoff ao dono via AskUserQuestion**

Apresentar ao dono:
- Caminho do relatório
- Veredicto
- Resumo de bloqueadores
- Resumo de ressalvas
- Risco arquitetural residual

Pergunta ao dono (via AskUserQuestion):

```
Pergunta: "Aprovar a validação do TECH_SPEC com base no relatório?"
Header: "TechSpec signoff"
Opções:
- "Aprovar e marcar [x]" → dono aceita o TECH_SPEC como source of truth técnica e
  autoriza marcar a task como concluída.
- "Aprovar com ressalvas (marcar [x], ajustar depois)" → marca [x] e registra
  ressalvas para tratar fora desta task.
- "Reprovar — corrigir antes" → não marca [x]; aguarda correção e nova auditoria.
```

Sem resposta do dono → **NÃO** marcar `[x]` (G-02). Parar a task aqui.

- [ ] **Step 5: Marcar [x] em docs/SPRINTS.md (somente se aprovado)**

Se dono aprovou (opções 1 ou 2), aplicar via Edit em `/home/ludsoncorrea/Documentos/projects/saas_igreja/docs/SPRINTS.md`:

```text
old_string: - [ ] (P0) Validar Tech Spec com Tech Lead
new_string: - [x] (P0) Validar Tech Spec com Tech Lead
```

Se reprovou → pular este step.

- [ ] **Step 6: Confirmar marcação**

Read: `/home/ludsoncorrea/Documentos/projects/saas_igreja/docs/SPRINTS.md` linha 52

Expected: `- [x] (P0) Validar Tech Spec com Tech Lead`

- [ ] **Step 7: NÃO commitar (G-03)**

Não rodar `git add` / `git commit` / `git push`. Apenas reportar ao dono que o workspace está pronto para revisão.

---

## Task 3: Encerramento e relatório consolidado

**Files:**
- Read: `/home/ludsoncorrea/Documentos/projects/saas_igreja/docs/SPRINTS.md`

### Steps

- [ ] **Step 1: Verificar estado final da seção Documentação na Sprint 0**

Read: `docs/SPRINTS.md` linhas 42–52.

Expected: As 7 tasks que já estavam `[x]` permanecem `[x]`. As 2 tasks alvo deste plano estão `[x]` se aprovadas pelo dono nas tasks 1 e 2; caso contrário permanecem `[ ]`.

- [ ] **Step 2: Resumir ao dono o resultado**

Reportar em uma mensagem curta:
- Caminho dos 2 relatórios gerados em `docs/superpowers/reviews/`
- Veredictos finais (APROVADO / APROVADO COM RESSALVAS / REPROVADO)
- Quais checkboxes foram marcadas em `docs/SPRINTS.md`
- O que falta para fechar a Sprint 0 (outras seções: Decisões críticas, Backlog, Fundação operacional, Critério de conclusão)

- [ ] **Step 3: Não commitar (G-03) e não iniciar próxima task sem nova autorização (G-02)**

Workspace fica como está. Aguardar instrução do dono.

---

## Notas finais

- Plano respeita G-01..G-05. Nenhum commit, nenhum push, nenhum merge.
- Cada relatório fica versionável quando o dono decidir versionar.
- Se algum dos relatórios identificar **REPROVADO**, as tasks correspondentes em `docs/SPRINTS.md` **não** são marcadas — corrige-se o documento e roda-se nova auditoria fora deste plano.
- Tasks da Sprint 0 fora da seção Documentação (Decisões críticas P1, Backlog, Fundação operacional) **não** estão neste plano. Serão tratadas em planos separados conforme autorização do dono (G-01).
