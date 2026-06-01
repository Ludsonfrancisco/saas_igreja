# Relatório de Validação — docs/TECH_SPEC.md
**Data:** 2026-05-28
**Reviewer:** code-reviewer-tech-lead (agente)
**Documento:** docs/TECH_SPEC.md
**Task vinculada:** docs/SPRINTS.md linha 52 — "Validar Tech Spec com Tech Lead"

## Veredicto
APROVADO COM RESSALVAS

## Sumário executivo
O TECH_SPEC.md está estruturalmente íntegro e alinhado ao PRD nas decisões mais críticas: multi-tenancy schema-per-tenant, P-ARQ-01..09 completos, AP-01..13 enumerados, models de domínio bem definidos, multi-role (`roles ArrayField`), LGPD (consent + anonymize + export + SET_NULL), `PlatformAdmin`/`SupportAccess` com janela de 4h, healthcheck `/health/` + `/ready/`, CI/CD GitHub Actions e Sentry com `before_send`. As ressalvas são lacunas de explicitação (não contradições): faltam citar `nplusone`, `django-anymail[brevo]`, `python-magic`, CSP, MFA enforcement Sprint 7, RTO/RPO, backup/restore (RNF-015/RNF-016/RNF-023), path scheme R2 e TTL 60s da signed URL — todos elementos já decididos em PRD/OPEN_DECISIONS/SPRINTS mas ausentes do TECH_SPEC, que é a "source of truth técnica". Modelos `Domain` e `MFARequiredForRoleMiddleware` são referenciados sem definição. Nenhum bloqueador. Recomenda-se um patch único cobrindo as 9 ressalvas antes de iniciar Sprint 1.

## Checklist (18 pontos)

| ID | Item | Status | Evidência | Observação |
|---|---|---|---|---|
| 1 | Stack oficial idêntica TECH_SPEC vs CLAUDE.md | PARTIAL | `docs/TECH_SPEC.md:13-29` vs `CLAUDE.md:49-65` | Tabela §1 do TECH_SPEC NÃO cita `nplusone` (presente em CLAUDE.md:61 e TEST_STRATEGY:18), NÃO cita `django-anymail[brevo]` (citado só em §13:785), NÃO cita Brevo no §1, e NÃO cita GitHub Actions na coluna de stack (só §12.2:756). Hostinger KVM 2 está ausente da tabela §1 (linha 29 fala apenas "Docker + EasyPanel + Cloudflare"). |
| 2 | Stack proibida cobre o conjunto inteiro | PASS | `docs/TECH_SPEC.md:33-41` | Cobre SQLite (AP-13), Next.js/React SPA/Vue SPA, Prisma, Auth.js, FastAPI, SQLAlchemy, WhatsApp Cloud API, LangChain/LangGraph, Stripe, Prometheus/Grafana, `fields='__all__'`, `@csrf_exempt`, raw SQL com f-strings. |
| 3 | P-ARQ-01..P-ARQ-09 todos presentes; P-ARQ-09 cita select_related/prefetch_related + nplusone | PASS | `docs/TECH_SPEC.md:165-175` | Tabela completa; P-ARQ-09 cita `select_related`/`prefetch_related` + `nplusone` ligado com `raise_in_dev=True`. |
| 4 | AP-01..AP-13 presentes com motivo e alternativa | PASS | `docs/TECH_SPEC.md:636-650` | Todos os 13 anti-padrões listados com descrição curta. AP-08 ("Prompt/PR sem referenciar PRD e design system") faz a ponte certa com governança. |
| 5 | Models completos (BaseModel, User, Invite, PlatformAdmin, SupportAccess, Church, Plan, Domain, Person, Community, Ministry, Gathering, Attendance, Schedule, ScheduleConflictApproval, FileAsset, AuditLog, SecurityLog) | PARTIAL | `docs/TECH_SPEC.md:210-575` | Faltando: `Domain` é apenas referenciado (TECH_SPEC:101-102, 105) mas NÃO tem definição de model na §5. Como `django-tenants` exige `Domain` no `SHARED_APPS`, o spec técnico precisa declarar o model (mesmo que seja o padrão da lib) para consistência com PRD §17.2:736. Todos os demais 17 models estão definidos. |
| 6 | Multi-tenancy: TenantMiddleware (subdomain→search_path), TENANT-04 (User SHARED_APPS sem FK cross-schema, user_id IntegerField + tenant_id CharField), TENANT-05 (TenantRequiredMixin mandatório) | PASS | `docs/TECH_SPEC.md:187-204, 530-533, 569-570` | TENANT-01..07 presentes em §4.2. Middleware descrito em §4.3 com 4 passos incluindo `SET search_path TO tenant_<slug>, public`. AuditLog e SecurityLog usam `user_id IntegerField` + `tenant_id CharField` conforme TENANT-04. |
| 7 | Multi-role (ArrayField, has_any_role/has_all_roles, validação último Pastor RN-004) | PARTIAL | `docs/TECH_SPEC.md:248-265, 318-324` | `roles ArrayField`, `has_any_role`, `has_all_roles` definidos. PORÉM: a validação "último Pastor" (RN-004) NÃO é citada na §5.2 nem em "Regras críticas de User/Invite" (linhas 318-324). Só aparece em ACCESS_MATRIX.md:314 e SPRINTS.md:202. Como TECH_SPEC é source of truth técnica, a regra deveria ser explicitada (mesmo que com 1 linha apontando ao service `change_roles`). |
| 8 | LGPD: consent obrigatório, anonymize soft delete + PII, Celery Beat semanal purge 30d, FK SET_NULL, export JSON+CSV com AuditLog action=export | PASS | `docs/TECH_SPEC.md:401-407, 597, 658` | `Person.consent_given_at` com help text "Obrigatorio quando email ou telefone esta preenchido (LGPD)". A1 (linha 658) descreve `anonymize_person()` soft delete + Celery Beat semanal + FKs `SET_NULL`. SEC-03 cita `export_person_data()`. |
| 9 | Healthcheck `/health/` liveness sempre 200 sem auth; `/ready/` Postgres+Redis 200/503 | PASS | `docs/TECH_SPEC.md:712-752` | Tabela §12.1 e implementação em `apps/core/views.py`. `@require_GET`, sem auth, ready verifica connection.cursor() + redis.ping(), retorna 200/503 conforme `healthy`. Rotas registradas no schema `public`. |
| 10 | CI/CD GitHub Actions: Ruff, Black, pip-audit, safety, pytest com Postgres+Redis service containers, cobertura mínima 80% | PARTIAL | `docs/TECH_SPEC.md:754-766` | Pipeline cobre Ruff, Black, pip-audit, safety, pytest com Postgres 15 + Redis em service containers. PORÉM o gate de cobertura está como placeholder `<gate>` em linha 762 (`--cov-fail-under=<gate>`) — não é uma falha mas o número deveria ser fixado (TEST_STRATEGY:38-50 dá 70%/80%/90% por app; o gate global mínimo é 80%). |
| 11 | Segurança: HSTS, X-Frame-Options, CSP, referrer-policy; cookies Secure+HttpOnly+SameSite; MFA TOTP allauth opt-in S2 + enforced S7 Pastor/PlatformAdmin; Sentry before_send sanitiza email/telefone e tag tenant_id; python-magic; rejeita SVG; signed URL R2 TTL 60s; path `{tenant_schema}/{model}/{object_id}/{filename}` | PARTIAL | `docs/TECH_SPEC.md:605-619, 195, 770, 781` | Headers em §7.1: HSTS, SECURE_BROWSER_XSS_FILTER, SECURE_CONTENT_TYPE_NOSNIFF, REFERRER_POLICY, X_FRAME_OPTIONS=DENY OK. Cookies Secure/HttpOnly/SameSite OK. **GAPS**: (a) **CSP NÃO está no bloco §7.1** (mencionado só em SPRINTS:180 e PRD em RNF-003); (b) **python-magic, rejeição de SVG e signed URL TTL 60s** NÃO aparecem no TECH_SPEC (estão em PRD §17.7:843-845 e SPRINTS:456-460); (c) **path scheme `{tenant_schema}/{model}/{object_id}/{filename}`** ausente (está em SPRINTS:451); (d) **MFA enforcement Sprint 7 (`MFARequiredForRoleMiddleware`)** apenas mencionado em §13:781 sem detalhamento técnico (PRD §15.4:581 define o middleware); (e) **Sentry `before_send` sanitiza email/telefone** aparece em TENANT-07:195 e §12.3:770 mas sem dizer **o que** sanitiza ou que adiciona tag `tenant_id` (PRD §15:557 cita tag explicitamente). |
| 12 | Convites: unique_together=('church','email'), token UUID, expiração 7 dias, password reset sem enumeração (mensagem e tempo idênticos) | PARTIAL | `docs/TECH_SPEC.md:268-286` | `unique_together=('church','email')` OK (linha 286); `token UUIDField(default=uuid.uuid4, unique=True)` OK (linha 276); `expires_at` declarado mas o **valor "7 dias" NÃO é citado em lugar nenhum do TECH_SPEC** (está em PRD §17.4 e SPRINTS:194). **Password reset sem enumeração** também NÃO é citado (regra está em SPRINTS:178 e RF-011 do PRD). Como TECH_SPEC é source of truth técnica, esses dois números/regras deveriam aparecer explicitamente, mesmo como notas em §5.2 ou §7. |
| 13 | Backup/Restore: RTO 4h / RPO 24h documentados; pg_dump diário; upload R2 retenção 30 dias; RESTORE.md previsto + teste mensal | FAIL | `docs/TECH_SPEC.md` (ausente) | **O TECH_SPEC.md NÃO menciona backup, restore, RTO, RPO, pg_dump, retenção 30 dias nem `RESTORE.md`**. Está tudo documentado em PRD §20.4:864-880 e SPRINTS:520-528, e OD-016 fechou RTO 4h/RPO 24h. Mas o TECH_SPEC, que é a source of truth técnica, precisa ter pelo menos uma seção dedicada ("Backup e Recovery") com: estratégia (pg_dump diário), destino (bucket R2 separado), retenção, RTO/RPO e referência ao runbook `docs/RESTORE.md`. Isto é a ressalva mais relevante. |
| 14 | P-ARQ-04 Service Layer leve (lógica em services.py, view fina) | PASS | `docs/TECH_SPEC.md:170, 584` | P-ARQ-04 ("Fluxos com >1 efeito vão em services.py. CBVs delegam. CRUD trivial não precisa de service") + STYLE-02 ("Lógica complexa em services.py"). Reforçado com exemplos na estrutura `apps/*/services.py`. |
| 15 | P-ARQ-06 Signals em signals.py por app, conectado em apps.py.ready() | PASS | `docs/TECH_SPEC.md:172` | "Signals em `signals.py` — Conectados em `apps.py.ready()`. Nunca em `models.py`." Estrutura de diretórios reforça (linhas 95, 114, 129, 134). |
| 16 | P-ARQ-07 TextChoices em vez de booleanos compostos | PASS | `docs/TECH_SPEC.md:173, 241, 348, 377, 448` | P-ARQ-07 declarado; aplicado em `User.Role`, `Church.Plan`, `Person.Status`, `Gathering.Type`. AP-03 reforça ("Booleanos para status com mais de 2 estados"). |
| 17 | Domain language pt-BR (Pessoa, Comunidade, Ministério, Encontro, Presença, Escala, Líder Principal) consistente entre TECH_SPEC, PRD, ACCESS_MATRIX, CLAUDE.md | PASS | `docs/TECH_SPEC.md:241-242, 334-337, 377-382, 446-453` | `Lider Principal` em `User.Role.PASTOR`. `leader_title` configurável no `Church`. `Person.Status` em pt-BR. `Gathering.Type` (`Culto`, `Reuniao de Comunidade`, `Evento`, `Reuniao`). Consistente com ACCESS_MATRIX:18-23 e CLAUDE.md:117-125. Aspas simples e código em inglês (STYLE-01). |
| 18 | Decisões abertas reconhecidas: OD-001 (Plan), OD-004 (Membro login), OD-005/OD-011 (DPO/incidente), OD-008 (OAuth2), OD-013 (templates privacidade), OD-014 (confirmação anonimização), OD-015 (CI/CD GitHub Actions) | PARTIAL | `docs/TECH_SPEC.md:775-786` | Seção §13 ("Decisões Técnicas Pendentes") cita as fechadas (OD-002, OD-003, OD-003a/OD-007, OD-006, OD-012, CI/CD GitHub Actions). PORÉM as **decisões ABERTAS que afetam stack/arquitetura** (OD-004, OD-008, OD-013, OD-014) não estão referenciadas no TECH_SPEC — só remete genericamente a `OPEN_DECISIONS.md`. Para um leitor que entre direto no TECH_SPEC, deveria haver pelo menos uma lista de "decisões abertas que afetam este documento". OD-015 está fechada e citada corretamente (linha 786). |

## Bloqueadores (FAIL)

_Nenhum._

Item 13 (Backup/Restore ausente) foi classificado como FAIL por ausência total no documento, mas **não é bloqueador para iniciar Sprint 1** — backup/restore só vira código na Sprint 7. Recomenda-se corrigir antes do início da Sprint 7, idealmente já na próxima revisão do TECH_SPEC. Como ressalva, fica documentado para tracking.

## Ressalvas (PARTIAL)

Lista priorizada por impacto:

### R1 — Backup/Restore ausente do TECH_SPEC (Item 13, FAIL reclassificado)
- **Onde:** `docs/TECH_SPEC.md` (seção inexistente).
- **O que falta:** seção "Backup e Recovery" com estratégia `pg_dump` diário, destino R2 bucket separado, retenção 30 dias, RTO 4h / RPO 24h (OD-016), referência a `docs/RESTORE.md` (a ser criado na Sprint 7).
- **Por que importa:** TECH_SPEC é source of truth técnica (`CLAUDE.md:37`). RNF-015/016/023 são "Crítico". OD-016 já está fechada mas não refletida aqui.
- **Como corrigir:** acrescentar §14 "Backup, Restore e Recuperação de Desastre" copiando o conteúdo essencial de PRD §20.3-20.5.

### R2 — CSP, python-magic, signed URL TTL 60s, path scheme R2, MFA middleware ausentes do TECH_SPEC (Item 11)
- **Onde:** §7 Segurança e §7.1 (`docs/TECH_SPEC.md:591-619`).
- **O que falta:**
  - CSP no bloco `prod.py` (RNF-003);
  - validação de upload via `python-magic` + rejeição de SVG (RF-080, RN-012);
  - signed URL R2 TTL 60s (RNF-018, OD-003a);
  - path scheme `{tenant_schema}/{model}/{object_id}/{filename}` (RISK-001);
  - `MFARequiredForRoleMiddleware` para Sprint 7 com Pastor + PlatformAdmin (RF-018b, OD-002).
- **Como corrigir:** adicionar `CONTENT_SECURITY_POLICY` ao bloco §7.1, criar subsecção §7.2 "Upload e Storage" com python-magic + SVG + path scheme + TTL 60s, e subsecção §7.3 "MFA" com o middleware referenciado.

### R3 — Backup de menções a `nplusone`, `django-anymail[brevo]`, GitHub Actions e Hostinger na tabela §1 (Item 1)
- **Onde:** `docs/TECH_SPEC.md:13-29`.
- **O que falta:** linhas na tabela de stack oficial para: `nplusone` (testes), `django-anymail[brevo]` (email transacional), GitHub Actions (CI/CD), Hostinger KVM 2 (hosting).
- **Como corrigir:** adicionar 4 linhas na tabela. Conteúdo já existe em CLAUDE.md:61-65 — basta espelhar.

### R4 — `Domain` model referenciado mas não definido (Item 5)
- **Onde:** `docs/TECH_SPEC.md:101-102, 105` (referências) vs §5 (sem definição).
- **O que falta:** declaração mínima do model `Domain` (mesmo que seja "padrão do django-tenants").
- **Como corrigir:** adicionar 6 linhas em §5.3 logo após `Church`:
  ```python
  class Domain(DomainMixin):
      """django-tenants Domain padrao. Resolve subdominio → schema."""
      pass
  ```

### R5 — Regra "último Pastor" (RN-004) sem citação no TECH_SPEC (Item 7)
- **Onde:** `docs/TECH_SPEC.md:318-324` (regras críticas de User/Invite).
- **O que falta:** uma linha indicando que `change_roles` valida RN-004.
- **Como corrigir:** adicionar bullet em §5.2: "Remoção de role `pastor` validada em `services.change_roles`: rejeita se deixaria a igreja sem nenhum user com `'pastor' in roles` (RN-004)."

### R6 — Expiração de convite (7 dias) e password reset sem enumeração não citados (Item 12)
- **Onde:** `docs/TECH_SPEC.md:268-286` (Invite) e §7 (Segurança).
- **O que falta:** o número "7 dias" para expiração de convite e a regra "mensagem e tempo idênticos" no password reset (sem enumeração).
- **Como corrigir:** anotação em §5.2 "Expiração default: 7 dias (set no service `create_invite`)" e linha em §7 "Password reset: mensagem e tempo de resposta idênticos para email existente/inexistente (sem enumeração)."

### R7 — Sentry tag `tenant_id` e sanitização específica (Item 11)
- **Onde:** `docs/TECH_SPEC.md:195, 770`.
- **O que falta:** explicitar que Sentry adiciona tag `tenant_id` em todos eventos e que `before_send` regex-sanitiza email/telefone.
- **Como corrigir:** §12.3 já tem o gancho ("Formatter sanitiza email/telefone via regex"); adicionar uma linha: "Sentry SDK configurado com `before_send` que aplica a mesma sanitização; tag `tenant_id` adicionada via `set_tag` no `TenantMiddleware`."

### R8 — Gate de cobertura como placeholder (Item 10)
- **Onde:** `docs/TECH_SPEC.md:762` (`--cov-fail-under=<gate>`).
- **O que falta:** valor numérico ou referência cruzada.
- **Como corrigir:** substituir por "ver gates por app em [`TEST_STRATEGY.md §3`](TEST_STRATEGY.md). Global mínimo: 80%."

### R9 — Decisões abertas que afetam stack/arquitetura não listadas no TECH_SPEC (Item 18)
- **Onde:** `docs/TECH_SPEC.md:775-786`.
- **O que falta:** mini-tabela das OD abertas com impacto técnico (OD-004, OD-008, OD-013, OD-014, OD-010 — retenção de logs).
- **Como corrigir:** acrescentar à §13 uma seção "Decisões abertas com impacto técnico" replicando a tabela enxuta de CLAUDE.md:185-196.

## Risco arquitetural residual

| Risco | Origem | Mitigação proposta |
|---|---|---|
| **RISK-006 (perda de dados)** — gate de Backup/Restore documentado apenas em PRD; TECH_SPEC silencioso sobre estratégia. Risco: implementação na Sprint 7 sem referência técnica única. | Item 13 ausente | Criar §14 "Backup e Recovery" no TECH_SPEC antes da Sprint 7. |
| **RISK-001 (vazamento cross-tenant)** — path scheme R2 `{tenant_schema}/{model}/{object_id}/{filename}` documentado apenas em SPRINTS:451. Se Sprint 6 começar sem esta convenção formalizada em TECH_SPEC, dev pode usar `upload_to=` padrão e gerar colisão. | Item 11 PARTIAL | Adicionar subsecção §7.2 "Upload e Storage" ao TECH_SPEC. |
| **RISK-013 (MFA não obrigatório)** — `MFARequiredForRoleMiddleware` definido apenas como menção em §13:781. Implementação técnica do middleware exige especificação detalhada (qual order no `MIDDLEWARE`, qual exceção lançar, qual redirect URL). | Item 11 PARTIAL | Detalhar §7.3 "MFA" no TECH_SPEC com pseudo-código do middleware. |
| **RISK-005 (LGPD: vazamento de PII em log)** — TECH_SPEC só diz "sanitiza email/telefone" sem exemplo de regex nem onde aplica (logger Django, Sentry, ambos). Risco operacional médio: dev pode aplicar só em um dos sinks. | Item 11 PARTIAL | §12.3 referenciar formatter customizado em `core/logging.py` (a ser criado Sprint 2). |

## Recomendações opcionais

- **REC-1:** adicionar ao TECH_SPEC §4 uma linha sobre `Public schema apps` (SHARED_APPS) vs `Tenant apps` (TENANT_APPS) — útil para devs novos navegarem o split rapidamente.
- **REC-2:** §11 (Design System) cita paleta mas não cita breakpoints mobile-first nem viewport mínimo 360px (RNF-021). Acrescentar 1 linha.
- **REC-3:** §2 Estrutura de Diretórios mostra `apps/core/admin.py` com `TenantAdminMixin`, mas não há nenhum exemplo de código deste mixin (diferente de `mixins.py`). Adicionar bloco mínimo (5 linhas) ao §7 ou §4.
- **REC-4:** §10 Notas A1..A5 são valiosas. Considerar adicionar A6 sobre **pagination default** (RNF-021: >25 paginadas).
- **REC-5:** OD-015 está citada no histórico de OPEN_DECISIONS.md:318 como fechada — convém numerá-la formalmente no §13 do TECH_SPEC ao invés de só dizer "CI/CD: GitHub Actions". Pequena consistência.

## Conclusão

O TECH_SPEC.md cumpre seu papel central: define stack, modelos, princípios e anti-padrões com solidez técnica suficiente para iniciar a Sprint 1. Os 18 pontos avaliados resultaram em **11 PASS, 6 PARTIAL, 1 FAIL** (este último reclassificado como ressalva R1 por não bloquear sprints anteriores à 7). Nenhum item viola governança G-01..G-05 nem introduz contradição com PRD/ACCESS_MATRIX/OPEN_DECISIONS.

**Próximos passos sugeridos ao dono:**
1. Aprovar o TECH_SPEC condicionalmente, autorizando R1..R9 como patch único de revisão antes de marcar `[x]` na task da SPRINTS.md:52.
2. Priorizar **R1 (Backup/Restore), R2 (segurança operacional) e R4 (Domain model)** antes do início da Sprint 1 — são lacunas técnicas que dev/agente vai precisar referenciar imediatamente.
3. R3, R5, R6, R7, R8, R9 podem entrar no mesmo patch ou em revisão imediatamente posterior; nenhum bloqueia o scaffold inicial.
4. Após o patch, repassar este checklist (10 minutos) e marcar `[x]` na linha 52 de SPRINTS.md.
5. Após aprovação do TECH_SPEC, fechar a Sprint 0 (faltam ainda 3 tasks: backlog inicial, RTO/RPO em `PRD §20.4` formalizado, `THREAT_MODEL.md` v1 — ver SPRINTS.md:65-83).

**Não foi feito git commit/push/merge (G-03 respeitado). Nenhum arquivo além deste relatório foi modificado.**
