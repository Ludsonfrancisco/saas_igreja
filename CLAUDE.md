# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Estado atual do repositório

**Pré-implementação — Sprint 0 (SDD).** Não existe código ainda. O repositório contém apenas especificação:

- `PRD.md` — source of truth de produto (capa, regras, requisitos RF/RNF/RN, riscos, sprints)
- `docs/` — documentos derivados (`TECH_SPEC`, `ACCESS_MATRIX`, `TEST_STRATEGY`, `SPRINTS`, `OPEN_DECISIONS`, `README`)

Antes de qualquer ação (criar arquivo, sugerir implementação, rodar comando), leia `PRD.md` §1.1 (governança) e `docs/README.md`. **Não invente código que ainda não foi autorizado.**

---

## Governança inviolável (G-01..G-05)

Estas regras estão em `PRD.md §1.1` e `docs/README.md`. Quebrar qualquer uma é bug crítico de processo:

- **G-01** — Sprint só inicia com autorização explícita do dono do projeto.
- **G-02** — Task só é executada após revisão prévia. Proibido pular para a próxima sem aprovação.
- **G-03** — **Nunca rodar `git commit`, `git push`, `git merge` ou abrir PR.** Apenas o dono versiona.
- **G-04** — Mudanças em arquivos ficam no workspace para revisão; nada é "entregue" antes da aprovação.
- **G-05** — Decisão técnica fora do escopo da task atual exige consulta antes de implementação.

Em caso de dúvida sobre escopo: **pergunte ao dono em vez de assumir.**

---

## Hierarquia de fonte de verdade

| Documento | Para quê serve |
|---|---|
| `PRD.md` | Produto: requisitos (RF-001..101, RNF-001..024, RN-001..015), riscos, sprints, decisões |
| `docs/TECH_SPEC.md` | Stack, models completos, princípios P-ARQ-01..09, anti-padrões AP-01..13, healthcheck, CI/CD |
| `docs/ACCESS_MATRIX.md` | Matriz papel × módulo × ação; mixins; multi-role; SupportAccess |
| `docs/TEST_STRATEGY.md` | Fixtures, gates de cobertura, testes obrigatórios por categoria |
| `docs/SPRINTS.md` | 8 sprints (0–7) com tasks `[ ]/[x]`, testes mínimos, critérios de conclusão |
| `docs/OPEN_DECISIONS.md` | Decisões fechadas (histórico) e abertas (tracking) |

Conflito entre documentos: prevalece o mais específico e recente. Conflito não resolvível → registrar em `OPEN_DECISIONS.md` e aplicar regra mais conservadora em segurança.

---

## Stack oficial (decidido)

| Camada | Tecnologia |
|---|---|
| Backend | Django 5.2 |
| Frontend | HTMX + Alpine.js + TailwindCSS |
| Banco | PostgreSQL 15+ (obrigatório por causa de schema-per-tenant) |
| Multi-tenancy | `django-tenants` |
| Auth | `django-allauth` (email login) + `django-axes` (lockout) |
| MFA | `django-allauth` TOTP — opt-in Sprint 2, obrigatório `pastor`/`PlatformAdmin` Sprint 7 |
| Async | Celery + Redis (decidido OD-003: desde Sprint 1) |
| Storage | Cloudflare R2 via `django-storages` (decidido OD-003a/OD-007: desde Sprint 6) |
| Email | Brevo free tier via `django-anymail[brevo]` (decidido OD-012) |
| Hosting | Hostinger KVM 2 (8GB, 2 vCPU) + EasyPanel Free + Cloudflare Free (decidido OD-006) |
| Testes | pytest + pytest-django + pytest-cov + nplusone |
| Lint/format | Ruff + Black |
| Package manager | uv |
| CI/CD | GitHub Actions (decidido OD-015) |
| Monitoramento | Sentry (tag `tenant_id`, `before_send` sanitiza PII) |

### Stack proibida

SQLite (AP-13), Next.js/React SPA/Vue SPA, Prisma, Auth.js, FastAPI, SQLAlchemy, WhatsApp Business Cloud API, LangChain/LangGraph, Stripe, Prometheus/Grafana, `fields = '__all__'` em ModelForm, `@csrf_exempt`, raw SQL com f-strings.

---

## Arquitetura — conceitos críticos

### Multi-tenancy (schema-per-tenant)

- Cada igreja = 1 schema PostgreSQL via `django-tenants`.
- `TenantMiddleware` resolve subdomínio (`igreja.saasigreja.com`) → `SET search_path TO tenant_<slug>, public`.
- **Toda view autenticada usa `TenantRequiredMixin`** (TENANT-05, AP-09). Vazamento cross-tenant é RISK-001 (crítico).
- **`User` é model público** (TENANT-04). Models dentro do tenant nunca referenciam `User` por FK; usam `user_id IntegerField` + `tenant_id CharField`.
- Bateria `test_tenant_isolation_matrix` percorre todas as views autenticadas com dois tenants e valida ausência de vazamento.

### Multi-role (RN-003a)

- `User.roles` é `ArrayField(CharField(choices=Role.choices))`, **não** campo único.
- Permissões = **união** das permissões de cada role. Exemplo: `['treasurer', 'leader']` tem acessos somados.
- Verificação **sempre** via `user.has_any_role('pastor', 'leader')`, **nunca** `user.role == 'pastor'`.
- Pastor sempre domina; adicionar outras roles a um Pastor é redundante.

### Migração entre igrejas (RN-003)

- **Não é suportada.** Um `User` pertence a uma única `Church` via FK simples.
- Para mudar de igreja: excluir conta + recriar via novo convite. Nada de M2M `Membership`.

### Platform Admin e SupportAccess (RN-015, RISK-009)

- `PlatformAdmin` é model separado de `User`. MFA obrigatório.
- Platform Admin **não acessa tenant** sem `SupportAccess` ativo (4h expiry).
- `PlatformAdminWithSupportAccessMixin` bloqueia e registra `SecurityLog` em tentativa sem acesso.
- Toda ação durante `SupportAccess` é auditada (`AuditLog` + `SecurityLog`).

### LGPD (RN-005, RN-006, RN-007)

- `Person.consent_given_at` obrigatório quando email ou telefone informado.
- `anonymize_person()` faz soft delete imediato + substitui PII. Celery Beat semanal faz purge físico após 30 dias.
- FKs para Person usam `on_delete=SET_NULL` (preserva auditoria/presença).
- `export_person_data()` retorna JSON + CSV. Toda exportação gera `AuditLog` com `action=export`.

### Princípios arquiteturais (P-ARQ-01..09)

P-ARQ-01 App-per-Bounded-Context · P-ARQ-02 `BaseModel(created_at, updated_at)` · P-ARQ-03 Login por email desde a 1ª migração · P-ARQ-04 Service Layer leve · P-ARQ-05 `TenantRequiredMixin` mandatório · P-ARQ-06 Signals em `signals.py` · P-ARQ-07 `TextChoices` (nunca booleanos compostos) · P-ARQ-08 Permissões em 3 camadas (view/service/queryset) · **P-ARQ-09 Prevenção de N+1** (`select_related`/`prefetch_related`; `nplusone` raise em testes).

---

## Linguagem de domínio (pt-BR)

| Termo | Model | Notas |
|---|---|---|
| Pessoa | `Person` | LGPD-aware (`consent_given_at`) |
| Comunidade | `Community` | Célula/grupo. Visível só se `Church.has_communities=True` |
| Ministério | `Ministry` | Departamento/equipe |
| Encontro | `Gathering` | Tipos: WORSHIP, COMMUNITY, EVENT, MEETING |
| Presença | `Attendance` | Unique `(person, gathering)` via `update_or_create` |
| Escala | `Schedule` | Bloqueia conflito; exceções via `ScheduleConflictApproval` |
| Líder Principal | `Church.leader_title` | Configurável: Pastor, Padre, Reverendo, etc. |

**Interface 100% pt-BR. Código 100% em inglês.** Aspas simples em Python.

---

## Sprint progression (não pular foundation)

Ordem obrigatória das 8 sprints:

```
Sprint 0 (docs) → 1 (Django+tenants+health) → 2 (auth+convites+autoriz+audit+SupportAccess+MFA opt-in)
→ 3 (Pessoas+Comunidades+Ministérios+LGPD) → 4 (Encontros+Presença) → 5 (Escalas+conflito)
→ 6 (Files R2+Dashboard) → 7 (Deploy+Backup+Restore+MFA enforce+Pen test+Athos)
```

**Gate de segurança:** nenhuma sprint operacional (3+) fecha sem `test_tenant_isolation_matrix` e `test_permissions_matrix` aplicáveis passando. Detalhes em `docs/TEST_STRATEGY.md §9`.

Sprint atual e progresso de tasks: ver checkboxes em `docs/SPRINTS.md`.

---

## Comandos

**Nenhum comando funcional ainda — repositório está em Sprint 0.** Não tente rodar `python`, `pytest`, `docker-compose`, `manage.py` etc. — não há projeto Django ainda.

A partir da Sprint 1 (após autorização explícita do dono), os comandos esperados serão (conforme `docs/TECH_SPEC.md`):

```bash
# Setup inicial
uv sync                                       # instala deps
docker compose up -d                          # Postgres 15 + Redis em service containers
python manage.py migrate_schemas --shared     # migrações no schema public

# Provisionar tenant em dev
python manage.py create_church athos          # cria tenant + Pastor inicial

# Lint e format
ruff check .
black --check .
black .                                       # aplica formatação

# Testes
pytest                                        # toda a suite
pytest apps/people/tests/test_services.py     # arquivo único
pytest -k anonymize                           # filtro por nome
pytest --cov=apps --cov-report=term-missing   # com cobertura

# Segurança
pip-audit
safety check

# Servidor de dev
python manage.py runserver
```

Healthcheck (Sprint 1): `GET /health/` (liveness, sem auth, sempre 200) e `GET /ready/` (readiness, verifica Postgres + Redis, retorna 200/503).

---

## Decisões abertas (consultar antes de assumir)

Listadas em `docs/OPEN_DECISIONS.md §29.2` (ou PRD §29.2). Resumo das que afetam código:

- **OD-001** Precificação (afeta `Plan` mas não bloqueia MVP)
- **OD-004** Login para Membro/Pessoa (afeta escopo de `accounts`)
- **OD-005, OD-011** DPO e notificação de incidentes (afeta `PRIVACY_POLICY.md`)
- **OD-008** OAuth2 Google opt-in (afeta `allauth` config)
- **OD-013** Templates de privacidade por igreja (afeta onboarding)
- **OD-014** Confirmação dupla na anonimização (afeta UX)

Se uma task tocar área de OD aberta, **pergunte ao dono antes de decidir.**

---

## Quando começar a codar

Só após o dono autorizar uma task específica de uma sprint específica (G-01, G-02). Antes disso, qualquer interação no repositório é leitura, análise ou refinamento de spec.

Toda task implementada deve referenciar pelo menos um RF/RNF/RN do PRD. Se não houver requisito vinculado, **não implementar.**
