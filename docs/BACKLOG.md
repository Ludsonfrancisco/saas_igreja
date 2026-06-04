# BACKLOG — SaaS Igreja

> **Versão:** 1.0
> **Data:** 2026-06-01
> **Método:** Spec Driven Development (SDD).
> **Origem:** transcrição dos requisitos funcionais do [`PRD.md`](../PRD.md) §11, §26 (rastreabilidade) e §27 (riscos).

Backlog inicial do MVP. Cada requisito funcional (`RF-XXX`) do PRD vira uma **issue** com sprint sugerida e papel responsável. Este documento é derivado: a fonte de verdade dos requisitos continua sendo o `PRD.md`. Em caso de conflito, prevalece o PRD.

## Como ler este backlog

- **ID** — identificador do RF no PRD (`PRD.md §11`).
- **Issue** — título acionável.
- **Ator (papel que executa)** — papel de usuário que dispara a ação (RBAC), conforme `ACCESS_MATRIX.md`. `Sistema` = ação automática sem ator humano.
- **App responsável** — bounded context (P-ARQ-01) onde a issue é implementada.
- **Prio** — `P0` obrigatório · `P1` desejável · `P2` opcional.
- **Sprint** — sprint sugerida no PRD/`SPRINTS.md`.
- **Teste** — teste sugerido (gate de conclusão).
- **Risco** — risco relacionado (`PRD §27`).

> **Convenção de status (para tracking futuro):** `[ ]` backlog · `[~]` em andamento · `[x]` concluída. Nenhuma issue inicia sem autorização do dono (G-01/G-02).

---

## Visão consolidada por sprint

| Sprint | Tema | Issues (RF) | P0 | P1 |
|---|---|---|---|---|
| 1 | Fundação Django + tenants | RF-001 | 1 | — |
| 2 | Auth, convites, autorização, auditoria | RF-002, RF-010..017, RF-018a, RF-020..023 | 13 | 2 |
| 3 | Pessoas, Comunidades, Ministérios (LGPD) | RF-030..035, RF-040..042, RF-050..051 | 13 | 1 |
| 4 | Encontros, Cultos, Presença | RF-060..062 | 3 | — |
| 5 | Escalas e voluntários | RF-070..072 | 2 | 1 |
| 6 | Arquivos/PDFs e Dashboard | RF-080..082, RF-090..091 | 4 | 2 |
| 7 | Deploy, backup, restore, hardening | RF-003, RF-018b, RF-100..101 | 3 | 1 |

> **Nota OD-004 (fechada 2026-06-01):** Membro/Pessoa **não tem login no MVP** — existe apenas como `Person`. Portanto **não há issues de autoatendimento de Membro** neste backlog. Convites (RF-013) são emitidos apenas para `pastor`, `leader` e `treasurer`. Login de Membro fica para a Fase 2.

---

## Sprint 1 — Fundação Django + PostgreSQL + django-tenants

| ID | Issue | Ator (papel que executa) | App | Prio | Teste | Risco |
|---|---|---|---|---|---|---|
| RF-001 | Provisionar nova igreja: criar `Church` gera schema, `Domain`, primeiro `User` com role `pastor` e envia convite por email | Platform Admin | tenants | P0 | `test_provision_creates_schema_and_admin` | RISK-001 |

**Critério de aceite (RF-001 / CA-001):** Dado Platform Admin autenticado, quando cria igreja com slug, então o schema `tenant_<slug>` é criado e o Pastor recebe convite por email.

---

## Sprint 2 — Autenticação, Convites, Autorização, Auditoria, SecurityLog

| ID | Issue | Ator (papel que executa) | App | Prio | Teste | Risco |
|---|---|---|---|---|---|---|
| RF-002 | Configurar igreja: editar nome, slug, logo, `leader_title`, `has_communities`, `accent_color`, `privacy_policy_url` | Pastor | tenants | P0 | `test_church_config_persists` | — |
| RF-010 | Login por email (sem username); senha exigida; sessão segura | Qualquer usuário com login | accounts | P0 | `test_login_email_only` | RISK-002 |
| RF-011 | Recuperar senha sem enumeração: resposta e tempo idênticos; token único; expira em 24h | Qualquer usuário com login | accounts | P0 | `test_password_reset_no_enumeration` | RISK-002 |
| RF-012 | Bloqueio por força bruta: 5 tentativas/15min → lockout 15min (`django-axes`); registrado em SecurityLog | Sistema | accounts | P0 | `test_axes_lockout` | RISK-002 |
| RF-013 | Convidar usuário: `Invite` com token UUID, expiração 7 dias, **roles** obrigatórias, email único por igreja | Pastor | accounts | P0 | `test_invite_unique_per_church` | — |
| RF-014 | Aceitar convite: valida token/expiração; cria `User` vinculado à igreja; marca `accepted_at` | Convidado | accounts | P0 | `test_accept_invite_creates_user` | — |
| RF-015 | Reenviar convite: reset de expiração e novo email | Pastor | accounts | P1 | `test_resend_invite` | — |
| RF-016 | Logout: encerra sessão e invalida cookies | Qualquer usuário com login | accounts | P0 | `test_logout` | — |
| RF-017 | Sessão segura: cookies `Secure`, `HttpOnly`, `SameSite=Lax` em produção | Sistema | accounts | P0 | `test_session_cookies_flags` | RISK-002 |
| RF-018a | MFA opt-in (TOTP): setup via `django-allauth` com QR code e 8 backup codes de uso único | Qualquer usuário com login | accounts | P0 | `test_mfa_totp_opt_in_setup_and_login` | RISK-013 |
| RF-020 | Listar usuários da igreja: email, roles, status, último login | Pastor | accounts | P0 | `test_list_users_scoped_by_church` | RISK-001 |
| RF-021 | Alterar roles / Gestão de Acessos: concede funções (multi-role) + escopo de grupo; `AuditLog`+`SecurityLog`; **travas OD-019:** Secretário não concede `pastor` nem desativa Pastor, sem auto-escalonamento, RN-004 | Pastor, Secretário | accounts | P0 | `test_role_change_audited`, `test_secretary_cannot_grant_pastor` | RISK-004/015 |
| RF-022 | Desativar acesso: `is_active=False`; bloqueia login; preserva histórico | Pastor | accounts | P0 | `test_deactivate_blocks_login` | RISK-002 |
| RF-023 | Reativar acesso: reverso de RF-022; gera `AuditLog` | Pastor | accounts | P1 | `test_reactivate_user` | — |

**Issues de plataforma desta sprint (sem RF dedicado, mas exigidas pelo PRD §15/§17 e RISK-009):**

- **Platform Admin + SupportAccess (RN-015 / RISK-009):** `PlatformAdminWithSupportAccessMixin`, `grant_support_access` (janela 4h + SecurityLog), `revoke_support_access`, bloqueio sem acesso ativo. Ator: Platform Admin. App: accounts/core. Teste: `test_platform_admin_blocked_without_support_access`. Prio: P0.
- **AuditLog e SecurityLog (RN-014, RNF-009/010):** models no schema do tenant, sem FK cross-schema. App: core. Teste: `test_auditlog_no_cross_schema_fk`. Prio: P0.
- **Headers e cookies de segurança (RNF-002/003):** App: core/settings. Teste: `test_security_headers_present`. Prio: P0.

---

## Sprint 3 — Pessoas, Comunidades, Ministérios (LGPD)

| ID | Issue | Ator (papel que executa) | App | Prio | Teste | Risco |
|---|---|---|---|---|---|---|
| RF-030 | Cadastrar pessoa: nome obrigatório; `consent_given_at` obrigatório quando email/telefone; respeita `plan.max_persons` | Pastor, Líder, Secretaria | people | P0 | `test_person_create_requires_consent` | RISK-005/011 |
| RF-031 | Editar pessoa: mudança em campos sensíveis gera `AuditLog` | Pastor, Líder responsável, Secretaria | people | P0 | `test_person_update_audited` | RISK-004 |
| RF-032 | Listar pessoas: filtros por status/comunidade/ministério; busca por nome; escopo por papel | Pastor, Líder (escopo), Secretaria | people | P0 | `test_person_list_scoped` | RISK-001 |
| RF-033 | Importar pessoas via CSV: assíncrono (Celery); idempotente por `import_id` | Pastor | people | P1 | `test_csv_import_idempotent` | — |
| RF-034 | Anonimizar pessoa: substitui PII; soft delete imediato; purge físico semanal (Celery Beat) | Pastor | people | P0 | `test_anonymize_lgpd` | RISK-005/011 |
| RF-035 | Exportar dados de pessoa: JSON + CSV; gera `AuditLog` com `action=export` | Pastor | people | P0 | `test_export_person_data` | RISK-005 |
| RF-040 | Criar comunidade: só se `has_communities=True`; respeita `plan.max_communities` | Pastor, Secretário | communities | P0 | `test_community_respects_plan_limit` | — |
| RF-041 | Editar comunidade: nome, **líderes (M2M, 1+, OD-019)**, dia/hora; gera `AuditLog` | Pastor, Secretário, Líder | communities | P0 | `test_community_update_audited` | RISK-004 |
| RF-042 | Vincular pessoa a comunidade: `Person.community` FK `on_delete=SET_NULL` (RN-007) | Pastor, Secretário, Líder | communities | P0 | `test_person_community_set_null` | — |
| RF-050 | Criar ministério: nome obrigatório; **coordenadores (M2M, 0+, OD-019)** opcionais | Pastor, Secretário | ministries | P0 | `test_ministry_create` | — |
| RF-051 | Vincular pessoas a ministério: M2M `Person.ministries` | Pastor, Secretário, Coordenador | ministries | P0 | `test_ministry_m2m` | — |

---

## Sprint 4 — Encontros, Cultos, Presença

| ID | Issue | Ator (papel que executa) | App | Prio | Teste | Risco |
|---|---|---|---|---|---|---|
| RF-060 | Criar encontro/culto: tipo (WORSHIP/COMMUNITY/EVENT/MEETING); data; `community` opcional; tipo COMMUNITY oculto se `has_communities=False` (RN-010) | Pastor, Líder, Coordenador | gatherings | P0 | `test_gathering_create` | — |
| RF-061 | Marcar presença em lote: lista pessoas elegíveis; checkbox por pessoa; `update_or_create` (sem duplicação, RN-009) | Líder, Coordenador | gatherings | P0 | `test_attendance_bulk_no_duplicate` | — |
| RF-062 | Editar presença: atualiza `is_present`; gera `AuditLog` | Líder, Coordenador | gatherings | P0 | `test_attendance_update_audited` | RISK-004 |

---

## Sprint 5 — Escalas e Voluntários com Bloqueio de Conflito

| ID | Issue | Ator (papel que executa) | App | Prio | Teste | Risco |
|---|---|---|---|---|---|---|
| RF-070 | Criar escala: vincular pessoa a `Gathering` como voluntário; valida pertencimento ao ministério | Coordenador | schedules | P0 | `test_schedule_create_validates_ministry` | — |
| RF-071 | Detectar conflito: mesma pessoa em dois `Gathering` na mesma data/hora bloqueia salvamento (RN-011) | Sistema | schedules | P0 | `test_schedule_conflict_blocked` | — |
| RF-072 | Aprovar exceção de conflito: cria `ScheduleConflictApproval` com justificativa; libera salvamento; gera `AuditLog` | Coordenador competente | schedules | P1 | `test_schedule_exception_approval` | RISK-004 |

---

## Sprint 6 — Arquivos/PDFs, Dashboard Mínimo, Permissões de Mídia

| ID | Issue | Ator (papel que executa) | App | Prio | Teste | Risco |
|---|---|---|---|---|---|---|
| RF-080 | Upload de arquivo: valida MIME via `python-magic`; ≤10MB; PDF/PNG/JPG; rejeita SVG; metadados em `FileAsset` (RN-012) | Pastor, Secretaria, Coordenador | files | P0 | `test_upload_validates_mime_and_size` | RISK-005 |
| RF-081 | Download protegido: URL assinada (TTL 60s) ou view com checagem por tenant/papel; nunca link público permanente (RN-013, RNF-018) | Usuário autenticado autorizado | files | P0 | `test_download_requires_permission` | RISK-005 |
| RF-082 | Excluir arquivo: remove arquivo + metadados; gera `AuditLog` | Pastor, Secretaria | files | P1 | `test_delete_file_audited` | — |
| RF-090 | Dashboard do Pastor: pessoas por status, presença último mês, comunidades/ministérios ativos; escopo do tenant | Pastor | dashboard | P0 | `test_dashboard_scoped_no_leak` | RISK-001 |
| RF-091 | Dashboard do Líder/Coordenador: versão simplificada limitada à comunidade/ministério | Líder, Coordenador | dashboard | P1 | `test_dashboard_leader_scope` | RISK-001 |

---

## Sprint 7 — Deploy Beta, Backup, Restore, Hardening, Piloto Athos

| ID | Issue | Ator (papel que executa) | App | Prio | Teste | Risco |
|---|---|---|---|---|---|---|
| RF-003 | Suspender igreja: marca tenant como suspenso, bloqueia acesso operacional, mantém dados | Platform Admin | tenants | P1 | `test_suspended_church_blocks_login` | — |
| RF-018b | MFA obrigatório: `MFARequiredForRoleMiddleware` exige TOTP em login para `'pastor' in roles` e `PlatformAdmin` (OD-002) | Sistema | accounts | P0 | `test_mfa_enforced_for_pastor_role` | RISK-013 |
| RF-100 | Backup diário: cron `pg_dump`; offsite S3-compatible (R2); retenção 30 dias | Sistema | ops | P0 | `test_backup_cron_documented` | RISK-006 |
| RF-101 | Restore de teste documentado: runbook restaura backup em ambiente isolado; teste mensal registrado | Ops | ops | P0 | Runbook `RESTORE.md` validado | RISK-006 |

---

## Requisitos não funcionais transversais (não viram issue de feature, mas são gate)

Estes RNF atravessam várias sprints e são validados nos gates de segurança/conclusão (ver `PRD §12`, `TEST_STRATEGY.md`):

| RNF | Descrição | Sprints | Teste |
|---|---|---|---|
| RNF-001 | `TenantRequiredMixin` em toda view autenticada | 1–7 | `test_all_authenticated_views_have_tenant_mixin` |
| RNF-006 | Zero vazamento cross-tenant | 1–7 | `test_tenant_isolation_matrix` |
| RNF-002/003 | Cookies seguros + headers (HSTS/X-Frame/CSP) | 2, 7 | `test_cookie_flags_in_prod`, `test_security_headers_present` |
| RNF-007/008 | LGPD: consent obrigatório, anonimização, exportação | 3 | `test_consent_required`, `test_anonymize_and_export` |
| RNF-009/010 | Auditoria + SecurityLog em ações sensíveis | 2–5 | `test_*_audited`, `test_security_events_logged` |
| RNF-017 | Sentry com tag `tenant_id` + `before_send` sanitiza PII | 7 | `test_sentry_tags_tenant`, `test_sentry_no_pii` |
| RNF-022 | `/health/` e `/ready/` (Postgres + Redis) | 1 | `test_health_endpoint_returns_200`, `test_ready_endpoint_checks_postgres_and_redis` |
| RNF-023 | RTO 4h / RPO 24h | 7 | Runbook + log de teste de restore |
| RNF-024 | Prevenção de N+1 (`nplusone` raise em testes) | 1–7 | `test_no_n_plus_one_in_listings` |

---

## Resumo quantitativo

- **Total de issues de RF:** 41 (RF-001..RF-101, incluindo RF-018a/018b).
- **P0:** 33 · **P1:** 8 · **P2:** 0.
- **Fora do MVP por OD-004:** autoatendimento/login de Membro (Fase 2).
- **Rastreabilidade completa:** ver `PRD §26 — Matriz de Rastreabilidade` (RF → CA → teste → sprint → risco).

> Este backlog deve ser revisado ao fim de cada sprint. Mudança de escopo entra primeiro como decisão em [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md), depois vira issue aqui.
