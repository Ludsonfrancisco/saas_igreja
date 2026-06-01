# THREAT MODEL — SaaS Igreja (v1)

> **Versão:** 1.0 (rascunho de fundação)
> **Data:** 2026-06-01
> **Status:** Versão simples de Sprint 0 (~1 página). **Refinado e formalizado na Sprint 7** (`SPRINTS.md`, antes do beta público). Base: `PRD.md §17.5` e §27 (riscos).
> **Escopo:** plataforma multi-tenant Django (schema-per-tenant) em VPS único, beta controlado com piloto Athos.

## 1. Ativos protegidos

| Ativo | Por quê importa |
|---|---|
| Dados pessoais de membros (`Person`: nome, email, telefone, presença) | LGPD — frequência religiosa é dado sensível |
| Isolamento entre igrejas (tenants) | Vazamento cross-tenant é o risco crítico do produto (RISK-001) |
| Credenciais e sessões de usuários | Acesso pastoral/administrativo |
| Trilha de auditoria (`AuditLog`/`SecurityLog`) | Conformidade e investigação de incidentes |
| Arquivos enviados (`FileAsset`) | Podem conter PII (declarações, atestados) |
| Backups (`pg_dump` + mídia no R2) | Recuperação de desastre; também contêm PII |

## 2. Atacantes considerados

| # | Atacante | Capacidade |
|---|---|---|
| A1 | Externo não autenticado | Internet pública; tenta enumerar contas, força bruta, IDOR |
| A2 | Usuário autenticado de outra igreja | Conta válida em tenant B tentando ler dados do tenant A |
| A3 | Usuário autenticado com papel baixo | `leader`/`member` tentando ações de `pastor` |
| A4 | Uploader malicioso | Envia arquivo perigoso (SVG com XSS, executável disfarçado de PDF) |
| A5 | Insider de plataforma (Platform Admin) | Acesso operacional tentando ler dados pastorais sem fluxo de suporte (RISK-009) |
| A6 | Observador de canais laterais | PII vazando via Sentry, logs ou backup mal protegido |

## 3. Superfície de ataque

- Endpoints de autenticação: login, recuperação de senha, aceite de convite.
- URLs autenticadas de cada app (`people`, `communities`, `gatherings`, etc.) — alvo de IDOR e cross-tenant.
- Resolução de tenant por subdomínio (`TenantMiddleware`).
- Upload e download de arquivos.
- Endpoints públicos: landing, cadastro de igreja, `/health/`, `/ready/`.
- Integrações externas: Brevo (email), Cloudflare R2 (storage/backup), Sentry (erros).
- Console do Platform Admin e fluxo `SupportAccess`.

## 4. Ameaças × mitigações

| Ameaça (STRIDE simplificado) | Atacante | Mitigação principal | Validação |
|---|---|---|---|
| Enumeração de contas | A1 | Mensagem e tempo idênticos no reset de senha (RF-011) | `test_password_reset_no_enumeration` |
| Força bruta de login | A1 | `django-axes` (5 falhas → lockout 15 min) + SecurityLog | `test_axes_lockout` |
| Vazamento cross-tenant | A2 | `TenantRequiredMixin` em toda view; schema-per-tenant; 404 (nunca 403 com dado) | `test_tenant_isolation_matrix` |
| IDOR via manipulação de URL | A1/A2 | Queryset sempre filtrado por tenant; permissões em 3 camadas (P-ARQ-08) | `test_permissions_matrix`, `test_*_returns_404` |
| Escalonamento de privilégio | A3 | Verificação `has_any_role(...)` em view + service + queryset; sem confiar no menu | `test_permissions_matrix` |
| Upload malicioso (XSS/RCE) | A4 | Validação de MIME via `python-magic`; SVG proibido; ≤10MB; PDF/PNG/JPG (RN-012) | `test_upload_validates_mime_via_magic`, `test_upload_rejects_svg` |
| Download não autorizado de arquivo | A1/A2 | View autenticada + permissão por tenant/papel; URL assinada TTL 60s; sem link público | `test_download_requires_permission`, `test_no_permanent_public_url` |
| Abuso de Platform Admin | A5 | `SupportAccess` (janela 4h) obrigatório; `PlatformAdminWithSupportAccessMixin`; MFA obrigatório; toda ação auditada | `test_platform_admin_blocked_without_support_access` |
| Vazamento de PII em telemetria | A6 | Sentry `before_send` sanitiza email/telefone; logs sem PII desnecessária; tag `tenant_id` | `test_sentry_no_pii` |
| Sequestro de sessão / CSRF | A1 | Cookies `Secure`/`HttpOnly`/`SameSite`; HSTS, CSP, X-Frame; CSRF nativo do Django | `test_security_headers_present`, `test_session_cookies_flags` |
| Roubo de credenciais de conta crítica | A1 | MFA TOTP opt-in (Sprint 2) → obrigatório para `pastor`/`PlatformAdmin` (Sprint 7) | `test_mfa_enforced_for_pastor_role` |
| Exposição de secrets | A6 | `python-decouple` + env vars; `.env` no `.gitignore`; sem secret no compose (AP-12) | Revisão de código + `pip-audit` |
| Comprometimento de backup | A6 | R2 com criptografia em trânsito/repouso; bucket privado; restore testado (RTO 4h/RPO 24h) | Teste mensal de restore (`RESTORE.md`) |

## 5. Pressupostos e limitações (beta)

- VPS único sem failover automático (sem SLA de alta disponibilidade — decisão consciente, PRD §5.2).
- Confiança nos provedores: Cloudflare (DNS/SSL/R2), Brevo (email), Hostinger (VPS), Sentry.
- DPO/responsável LGPD ainda em aberto (OD-005) — fechar antes do beta público.
- Procedimento formal de resposta a incidentes (`INCIDENT_RESPONSE.md`) é entregável pós-MVP (OD-011).

## 6. Itens para a versão formal (Sprint 7)

- Diagrama de fluxo de dados (DFD) com fronteiras de confiança.
- Revisão STRIDE completa por componente.
- Pentest manual das URLs de download e dos fluxos de autenticação.
- Validação de retenção de logs (OD-010) e notificação de incidentes (OD-011).
- Confirmação de MFA obrigatório ativo para `pastor` e `PlatformAdmin`.
