# OPEN DECISIONS — SaaS Igreja

> **Versão:** 1.0
> **Data:** 2026-05-27
> **Status:** Tracking ativo. Toda decisão aberta tem owner e prazo. Revisão semanal.

Toda decisão aberta com impacto técnico ou de produto vive aqui até ser fechada. Quando fechada, registrar a decisão no documento onde se aplica (`PRD.md`, `TECH_SPEC.md`, `ACCESS_MATRIX.md`) e mover para o histórico no final desta página.

## Legenda de status

- 🟢 **Aberta** — decisão pendente
- 🟡 **Em discussão** — alternativas sendo avaliadas
- 🔴 **Bloqueante** — bloqueia sprint(s) seguinte(s)
- ✅ **Fechada** — mover para histórico

## Legenda de impacto

- **Crítico** — bloqueia segurança, LGPD ou MVP
- **Alto** — afeta escopo ou prazo significativo
- **Médio** — afeta UX ou operação
- **Baixo** — preferência sem impacto material

---

## Decisões abertas

### OD-001 — Precificação final

| Campo | Valor |
|---|---|
| Status | 🟡 Em discussão |
| Impacto | Alto (comercial) |
| Owner | Produto + Finanças |
| Prazo | Antes do lançamento comercial |
| Bloqueia | Cobrança automatizada e GTM |

**Contexto:** valores históricos (R\$49, R\$99, R\$199) são hipótese, não decisão. Sem estudo formal de custos, suporte, armazenamento, backup, volume de uso, concorrência e disposição de pagamento, não fechar.

**Opções:** (a) manter beta gratuito até estudo; (b) cobrar manualmente piloto Athos durante validação; (c) lançar com pricing tentativo e ajustar.

**Recomendação atual:** (a) + (b). Não publicar preço final até estudo.

---

### OD-002 — MFA obrigatório para Pastor e Platform Admin

| Campo | Valor |
|---|---|
| Status | ✅ Fechada (2026-05-27) |
| Impacto | Alto (segurança) |
| Owner | Segurança + Produto |
| Decisão | **Split: opt-in Sprint 2; enforcement obrigatório Sprint 7** |

**Contexto:** `django-allauth` suporta MFA TOTP. Adicionar MFA só na Sprint 7 = refazer fluxo de auth perto do beta = risco.

**Decisão:**
- **Sprint 2:** habilitar MFA TOTP **opt-in** via `django-allauth` (setup, QR code, backup codes). Infra pronta, testada cedo.
- **Sprint 7:** middleware torna MFA **obrigatório** para `pastor` em `User.roles` e para `PlatformAdmin`. Login sem MFA redireciona para setup.

**Justificativa:** integração testada cedo, hardening tardio, sem refazer auth na 7.

---

### OD-003 — Celery + Redis no MVP ou importação síncrona

| Campo | Valor |
|---|---|
| Status | ✅ Fechada (2026-05-27) |
| Impacto | Alto (escopo + infra) |
| Owner | Tech Lead |
| Decisão | **Celery + Redis no MVP** |

**Contexto:** importação CSV ≥500 linhas em request síncrona = timeout. Purge LGPD semanal exige scheduler. Emails de convite/recuperação em background reduzem latência percebida.

**Decisão:** **Celery + Redis no MVP** desde Sprint 1.

**Justificativa:**
- Athos tem ~350 membros; outras igrejas podem ter mais.
- Purge físico de Person anonimizada (Sprint 3, P0) precisa de scheduler.
- Custo de infra trivial em VPS 8GB (Redis ~50MB RAM).
- Cron + management commands viraria gambiarra para múltiplos usos legítimos.

---

### OD-003a — Storage de mídia

| Campo | Valor |
|---|---|
| Status | ✅ Fechada (2026-05-27) |
| Impacto | Alto (custo de migração futura) |
| Owner | Ops + Tech Lead |
| Decisão | **Cloudflare R2 (S3-compatible) desde Sprint 6** |

**Contexto:** plano original previa volume `/media` no beta migrando para S3 em produção. Migração futura exige backfill de arquivos, troca de storage backend e revalidação de URLs assinadas.

**Decisão:** **R2 desde o MVP**. Sem volume local em prod.

**Justificativa:**
- R2 tem free tier de 10GB + zero egress (vs S3 que cobra egress).
- Alinhado com Cloudflare já em uso (DNS, SSL).
- Evita refatoração futura.
- `django-storages` configurado uma vez resolve dev (com mock local) e prod (R2).

**Implicações:** fecha OD-007 com a mesma decisão.

---

### OD-004 — Membro/Pessoa tem login no MVP

| Campo | Valor |
|---|---|
| Status | 🟢 Aberta |
| Impacto | Médio (escopo) |
| Owner | Produto |
| Prazo | Sprint 3 |
| Bloqueia | Escopo da app `accounts` |

**Contexto:** PRD prevê persona "Membro / Pessoa" com acesso limitado (próprio perfil, comunidade, ministérios, presença). Custo: mais views, mais permissões, mais convites.

**Opções:** (a) login para Membro no MVP; (b) Membro existe apenas como `Person` sem login; (c) decidir caso a caso pela igreja (flag por tenant).

**Recomendação atual:** (b). MVP cobre Pastor, Líder, Coordenador. Login de Membro entra na Fase 2 se houver demanda.

---

### OD-005 — DPO / responsável LGPD

| Campo | Valor |
|---|---|
| Status | 🟢 Aberta |
| Impacto | Crítico (regulatório) |
| Owner | Jurídico |
| Prazo | Antes do beta público |
| Bloqueia | Beta público (LGPD exige responsável) |

**Contexto:** LGPD exige responsável pelo tratamento de dados. Plataforma é operadora; cada igreja é controladora. Plataforma precisa designar pessoa de contato.

**Opções:** (a) líder do projeto assume; (b) contratar serviço externo de DPO; (c) DPO compartilhado entre projetos.

**Recomendação atual:** (a) para o beta; reavaliar antes do lançamento comercial.

---

### OD-006 — VPS definitivo

| Campo | Valor |
|---|---|
| Status | ✅ Fechada (2026-05-27) |
| Impacto | Alto (custo + previsibilidade) |
| Owner | Ops |
| Decisão | **Hostinger KVM 2 (8GB RAM, 2 vCPU, 100GB NVMe)** |

**Decisão:** Hostinger KVM 2 desde Sprint 1.

**Justificativa:**
- 8GB RAM acomoda Django + Celery + Redis + Postgres confortavelmente.
- Custo ~R\$ 60/mês (renovação) cabe no bootstrap.
- Athos + 9 igrejas pequenas em piloto cabem sem aperto.
- Backup offsite no R2 mitiga risco de provedor.
- Gatilho de migração para DigitalOcean ou banco gerenciado: >10 igrejas com uso pesado ou CPU/RAM acima de 70% sustentado.

---

### OD-007 — Storage offsite

| Campo | Valor |
|---|---|
| Status | ✅ Fechada (2026-05-27) |
| Impacto | Médio (custo + backup) |
| Owner | Ops |
| Decisão | **Cloudflare R2 (S3-compatible)** |

**Decisão:** R2 atende storage de mídia (OD-003a) e backup offsite. Mesma conta, mesmas credenciais.

**Justificativa:** free tier 10GB + zero egress + integração nativa com Cloudflare DNS/SSL. Backup de banco e backup de mídia em buckets separados na mesma conta.

---

### OD-008 — OAuth2 Google no MVP

| Campo | Valor |
|---|---|
| Status | 🟢 Aberta |
| Impacto | Médio (UX + escopo) |
| Owner | Produto |
| Prazo | Sprint 2 |
| Bloqueia | — (default: não) |

**Contexto:** `django-allauth` suporta Google OAuth nativamente. Reduz fricção de cadastro mas adiciona configuração por igreja.

**Opções:** (a) não no MVP; (b) opcional configurável por tenant; (c) padrão para todos.

**Recomendação atual:** (a). Email login resolve. OAuth fica pós-MVP.

---

### OD-009 — Billing manual

| Campo | Valor |
|---|---|
| Status | 🟢 Aberta |
| Impacto | Médio (operacional) |
| Owner | Produto |
| Prazo | Antes do segundo cliente pago |
| Bloqueia | — |

**Contexto:** MVP usa cobrança manual. Precisa de processo definido.

**Opções:** (a) planilha Google + envio manual por PIX; (b) Notion como CRM + boleto manual; (c) ferramenta dedicada (Asaas, Gerencianet).

**Recomendação atual:** (a) para piloto Athos; (b) quando passar de 3 clientes pagantes.

---

### OD-010 — Retenção de logs (`AuditLog`, `SecurityLog`)

| Campo | Valor |
|---|---|
| Status | 🟢 Aberta |
| Impacto | Médio (storage + LGPD) |
| Owner | Segurança + LGPD |
| Prazo | Sprint 7 |
| Bloqueia | Crescimento descontrolado de tabela |

**Contexto:** logs crescem indefinidamente. LGPD pode exigir prazo máximo de retenção para `AuditLog` com PII; `SecurityLog` geralmente pode ser retido mais tempo.

**Opções:** (a) reter indefinidamente (risco de crescimento); (b) particionar por mês e arquivar offsite após 12 meses; (c) purge após 24 meses.

**Recomendação atual:** (c) com revisão anual.

---

### OD-011 — Notificação de incidentes LGPD

| Campo | Valor |
|---|---|
| Status | 🟢 Aberta |
| Impacto | Crítico (regulatório) |
| Owner | Segurança + Jurídico |
| Prazo | Antes do beta público |
| Bloqueia | Beta público |

**Contexto:** LGPD exige procedimento de notificação à ANPD e aos titulares em caso de incidente.

**Opções:** (a) procedimento manual documentado em `INCIDENT_RESPONSE.md`; (b) integração com ferramenta de gestão de incidentes; (c) modelo simplificado com checklist.

**Recomendação atual:** (a) com checklist em `INCIDENT_RESPONSE.md` (Sprint 7).

---

### OD-012 — Email transacional

| Campo | Valor |
|---|---|
| Status | ✅ Fechada (2026-05-27) |
| Impacto | Alto (auth depende) |
| Owner | Ops |
| Decisão | **Brevo (ex-Sendinblue) free tier — 300 emails/dia** |

**Decisão:** Brevo desde Sprint 2.

**Justificativa:**
- 3× mais generoso que SendGrid free (300/dia vs 100/dia).
- Suporte nativo a DKIM/SPF para deliverability.
- API simples e SDK Python maduro.
- Convites + recuperação de senha cabem em 300/dia até várias dezenas de igrejas.
- Migrar para plano pago só quando volume real justificar (~R\$ 25/mês para 20k emails/mês).
- Backend Django: `django-anymail[brevo]`.

---

### OD-013 — Política de privacidade por igreja

| Campo | Valor |
|---|---|
| Status | 🟢 Aberta |
| Impacto | Médio (UX + LGPD) |
| Owner | Produto + Jurídico |
| Prazo | Sprint 2 |
| Bloqueia | Onboarding de igreja |

**Contexto:** cada igreja precisa de política de privacidade. Pode ser modelo gerado ou upload obrigatório.

**Opções:** (a) modelo template gerado a partir de campos da igreja; (b) exigir upload de URL externa; (c) ambos (template default + opção de URL externa).

**Recomendação atual:** (c). Default cobre 80% dos casos; URL externa atende igrejas com política própria.

---

### OD-014 — Confirmação dupla antes de anonimização

| Campo | Valor |
|---|---|
| Status | 🟢 Aberta |
| Impacto | Médio (UX vs segurança) |
| Owner | Produto + Segurança |
| Prazo | Sprint 3 |
| Bloqueia | — |

**Contexto:** anonimização é irreversível (soft delete imediato + purge físico em 30 dias). Confirmação simples pode causar perda acidental.

**Opções:** (a) confirmação simples no modal; (b) confirmação dupla (modal + digitar nome da pessoa); (c) confirmação por email do Pastor.

**Recomendação atual:** (b). Digitar nome da pessoa antes de confirmar.

---

## Histórico — decisões fechadas

| ID | Decisão | Data | Resultado |
|---|---|---|---|
| OD-002 | MFA obrigatório | 2026-05-27 | Split: opt-in Sprint 2; enforcement obrigatório Sprint 7 |
| OD-003 | Celery + Redis no MVP | 2026-05-27 | Celery + Redis incluído desde Sprint 1 |
| OD-003a | Storage de mídia | 2026-05-27 | Cloudflare R2 (S3-compatible) desde Sprint 6 |
| OD-006 | VPS definitivo | 2026-05-27 | Hostinger KVM 2 (8GB, 2 vCPU, 100GB NVMe) |
| OD-007 | Storage offsite | 2026-05-27 | Cloudflare R2 (mesma conta de OD-003a) |
| OD-012 | Email transacional | 2026-05-27 | Brevo (ex-Sendinblue) free tier 300/dia, via `django-anymail` |
| OD-015 | Plataforma de CI/CD | 2026-05-27 | GitHub Actions; pipeline mínimo em `.github/workflows/ci.yml` |
| OD-016 | RTO / RPO baseline beta | 2026-05-27 | RTO 4h / RPO 24h (limitado pelo `pg_dump` diário) |
| RN-MULTI-ROLE | Multi-role por usuário | 2026-05-27 | `User.roles ArrayField`, permissões viram união |
| RN-NO-CHURCH-MIGRATION | Migração entre igrejas | 2026-05-27 | Não suportada. Para mudar de igreja: excluir conta + recriar |
| RN-N-PLUS-ONE | Prevenção de N+1 | 2026-05-27 | P-ARQ-09: `select_related`/`prefetch_related` obrigatórios; `nplusone` raise em testes |

---

## Como adicionar nova decisão

1. Atribuir próximo ID `OD-XXX`.
2. Preencher tabela de campos (Status, Impacto, Owner, Prazo, Bloqueia).
3. Adicionar **Contexto**, **Opções** e **Recomendação atual**.
4. Vincular ao documento de origem (`PRD.md`, `TECH_SPEC.md`, etc.) atualizando referência cruzada.

## Como fechar uma decisão

1. Atualizar status para ✅ **Fechada**.
2. Mover para Histórico com data e opção escolhida.
3. Atualizar documento onde a decisão se aplica.
4. Atualizar PRD se decisão impactar escopo, segurança ou roadmap.
