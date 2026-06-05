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
| Status | ✅ Fechada (2026-06-01) |
| Impacto | Médio (escopo) |
| Owner | Produto |
| Decisão | **Membro existe apenas como `Person`, sem login no MVP (opção b)** |

**Contexto:** PRD prevê persona "Membro / Pessoa" com acesso limitado (próprio perfil, comunidade, ministérios, presença). Custo: mais views, mais permissões, mais convites.

**Opções:** (a) login para Membro no MVP; (b) Membro existe apenas como `Person` sem login; (c) decidir caso a caso pela igreja (flag por tenant).

**Decisão:** **(b)** — o MVP cobre login apenas para Pastor, Líder e Coordenador. "Membro / Pessoa" existe somente como `Person` (sem conta de acesso). Login de Membro entra na Fase 2 se houver demanda.

**Justificativa:**
- Mantém a app `accounts` enxuta no MVP (menos views, menos permissões, menos fluxos de convite).
- A persona Membro não tem ação operacional crítica no MVP — só visualizaria o próprio perfil.
- `member` permanece em `User.Role.choices` para não exigir migração de schema na Fase 2, mas nenhuma view de autoatendimento de Membro é construída no MVP.

**Implicações para o escopo:**
- Convites (Sprint 2) são emitidos apenas para `pastor`, `leader`, `treasurer` (este último com escopo mínimo). Não há fluxo de convite para `member`.
- Nenhuma view "minha conta de Membro" / "minhas escalas (Membro)" entra no MVP.
- Reabrir como nova decisão (OD-XXX) se a demanda da Fase 2 exigir.

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
- **Reforço do gatilho (pós-piloto):** Sprint 8 (Financeiro Avançado) e sobretudo Sprint 9 (**Evolution API** = +1 serviço Node + sessão por tenant) devem **exigir upgrade de VPS** — reavaliar dimensionamento antes da Sprint 9 (OD-024/OD-025).

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
| Status | ✅ Fechada (2026-06-04) |
| Impacto | Médio (UX vs segurança) |
| Owner | Produto + Segurança |
| Decisão | **(b) Confirmação dupla — o Pastor digita o nome exato da pessoa para confirmar** |

**Contexto:** anonimização é irreversível (soft delete imediato + purge físico em 30 dias). Confirmação simples pode causar perda acidental.

**Opções:** (a) confirmação simples no modal; (b) confirmação dupla (modal + digitar nome da pessoa); (c) confirmação por email do Pastor.

**Decisão (dono, 2026-06-04):** opção **(b)**. Implementada em `PersonAnonymizeView` (Sprint 3 / Frente 2 / Bloco 3): GET mostra o aviso de irreversibilidade + campo de confirmação; POST só anonimiza se o nome digitado bate exatamente com `person.name`, senão cancela. Validado por `test_anonymize_view_requires_exact_name`.

---

### OD-017 — Política de exclusão de tenant (Church)

| Campo | Valor |
|---|---|
| Status | ✅ Fechada (2026-06-01) |
| Impacto | Alto (LGPD + integridade de auditoria) |
| Owner | Segurança + Produto |
| Decisão | **Igreja não é hard-deletável no MVP — apenas suspensa (opção a)** |

**Contexto:** `User.church` está com `on_delete=CASCADE` (`TECH_SPEC §5.2`). Excluir uma `Church` apagaria os `User` do schema public, deixando `AuditLog.user_id`/`SecurityLog.user_id` órfãos no tenant. O PRD prevê apenas **suspender** igreja (RF-003), não há RF de exclusão definitiva.

**Opções:** (a) igreja não é hard-deletável no MVP — apenas suspensa (RF-003); (b) hard delete com fluxo de anonimização/retenção prévio dos logs; (c) `on_delete=PROTECT` em `User.church` exigindo limpeza manual.

**Decisão:** **(a)** — no MVP a igreja só é **suspensa** (RF-003), nunca excluída fisicamente. Os dados e a trilha de auditoria são preservados. Hard delete entra como fluxo auditado/anonimizado pós-MVP, se houver demanda real.

**Implicações para o código:**
- Não construir view/serviço de exclusão definitiva de `Church` no MVP.
- O `on_delete=CASCADE` em `User.church` permanece no model (sem migração), mas **nenhum caminho de produto dispara a exclusão da Church** — a suspensão é via flag de status, não delete.
- Reabrir como nova OD se a Fase 2 exigir exclusão definitiva (definir então retenção/anonimização prévia de logs).

**Origem:** levantada na validação Tech Lead do TECH_SPEC (achado B-1, 2026-06-01).

---

### OD-018 — Camada canônica de enforcement LGPD (`consent_given_at`)

| Campo | Valor |
|---|---|
| Status | ✅ Fechada (2026-06-01) |
| Impacto | Crítico (LGPD) |
| Owner | Tech Lead |
| Decisão | **Validação na camada de service (espelhada no form) — opção a** |

**Contexto:** RNF-007 diz que `consent_given_at` é validado "no `Person.save` ou form". Se a validação ficar **só no `ModelForm`**, a importação CSV (RF-033, que pode rodar via Celery e não passa por form) burlaria a regra LGPD (RN-005).

**Opções:** (a) validar na **camada de service** (`create_person`/`import_csv`) e espelhar no form para UX; (b) validar no `Person.save()` (model-level); (c) validar apenas no form (rejeitada — não cobre CSV).

**Decisão:** **(a)** — a barreira efetiva é a **camada de service**: `people/services.py.create_person` e `import_csv` rejeitam Pessoa com `email` ou `phone` sem `consent_given_at` (RN-005/RNF-007). O `ModelForm` espelha a regra para UX, mas não é a única defesa. Garante cobertura do caminho de importação CSV.

**Implicações para o código:**
- Regra de consentimento implementada em `people/services.py` (já registrada em `TECH_SPEC §OPS-05`).
- Teste obrigatório no fluxo de form **e** no fluxo CSV (`test_person_create_requires_consent_when_email_or_phone` + equivalente CSV).
- Form espelha a validação apenas para feedback ao usuário; não substitui a checagem no service.

**Origem:** levantada na validação Tech Lead do TECH_SPEC (achado A-4, 2026-06-01).

---

### OD-019 — Modelo de papéis e Gestão de Acessos

| Campo | Valor |
|---|---|
| Status | ✅ Fechada (2026-06-04) |
| Impacto | Alto (autorização, segurança) |
| Owner | Produto + Segurança |
| Decisão | Papel **`secretary`** (admin sem financeiro); **`leader` unificado** (comunidade e ministério, diferença = vínculo); **M2M** `Community.leaders`/`Ministry.coordinators` (vários por grupo); tela de **Gestão de Acessos** concede funções + escopo; **conceder acesso = Pastor + Secretário** (Tesoureiro de fora) |

**Contexto:** o dono pediu (2026-06-04) papéis administrativos (secretário) e a possibilidade de vários líderes por célula / coordenadores por ministério, com uma tela onde um admin concede funções + escopo de grupo a um membro.

**Decisões:**
- **Papéis:** adiciona `secretary` ao `User.Role`. `leader` continua único (comunidade vs ministério = vínculo, não papel separado). `treasurer` permanece (financeiro pós-MVP).
- **Cardinalidade:** `Community.leader`/`Ministry.coordinator` (FK) → `Community.leaders`/`Ministry.coordinators` (**M2M** de `Person`). Vínculo ao login segue `Person.user_id` (IntegerField, TENANT-04).
- **Gestão de Acessos:** Pastor ou Secretário concede; ver fluxo em `ACCESS_MATRIX §3.2.1`.

**Travas de segurança obrigatórias (viram requisito — `RISK-015`):**
1. Secretário **não** concede/atribui o papel `pastor` nem desativa um Pastor (só Pastor cria/derruba Pastor).
2. **Ninguém** altera os próprios papéis (sem auto-escalonamento).
3. Concessão escopada ao tenant (`church`) e **auditada** (`AuditLog` + `SecurityLog` `role_change`).
4. RN-004 (último Pastor) permanece.
5. **MFA do Secretário** passa a ser exigido na Sprint 7 (junto com Pastor/PlatformAdmin).

**Impacto na implementação:** afeta `ScopedToCommunityMixin`/`ScopedToMinistryMixin` (lookup `leaders__user_id`/`coordinators__user_id`), models de Community/Ministry (M2M), e replaneja a Frente 3 da Sprint 3 (Comunidades M2M → Ministérios M2M → Gestão de Acessos → CSV/fecho).

---

### OD-020 — `on_delete` de `Attendance.person` (conflito de docs)

| Campo | Valor |
|---|---|
| Status | ✅ Fechada (2026-06-05) |
| Impacto | Médio (LGPD, integridade de dados) |
| Owner | Produto + Segurança |
| Decisão | **`on_delete=SET_NULL`** (`null=True`) em `Attendance.person`, alinhando com **RN-007**. Corrige a `TECH_SPEC §5.6`, que trazia `CASCADE` por engano |

**Contexto:** ao implementar a Frente 2 da Sprint 4 (Presença), `TECH_SPEC §5.6` especificava `Attendance.person = ForeignKey(on_delete=CASCADE)`, conflitando com `RN-007`/`CLAUDE.md` ("FKs para Person usam `on_delete=SET_NULL` — preserva auditoria/**presença**").

**Decisão:** prevalece RN-007. O **purge físico** (Celery Beat, 30 dias pós-anonimização) que apaga a `Person` mantém os registros de `Attendance` com `person=NULL` — preserva a **contagem histórica** de presença dos encontros sem revelar *quem* (esquece a identidade, mantém o número). A anonimização (soft delete) não dispara nada disso; a linha da Pessoa permanece. `unique_together (person, gathering)` segue válido (NULLs são distintos no Postgres). Sem auditoria por linha em `Attendance` (operação de alta frequência; marcação em lote geraria ruído).

---

### OD-021 — Mecanismo de download de arquivo (Sprint 6)

| Campo | Valor |
|---|---|
| Status | ✅ Fechada (2026-06-05) |
| Impacto | Médio (segurança de mídia, UX) |
| Owner | Tech Lead + Segurança |
| Decisão | **Streaming pela view autenticada** (a view checa tenant+papel e devolve os bytes), **não** redirect para URL assinada do R2 |

**Contexto:** a `SPRINTS` Sprint 6 oferecia duas opções para download — (a) gerar URL temporária assinada do R2 (TTL 60s) e redirecionar, ou (b) fazer streaming do arquivo pela própria view. A escolha afeta a bateria de testes (`test_signed_url_expires_in_60s` vs testes de permissão/streaming) e o comportamento entre ambientes.

**Decisão:** **(b) streaming pela view autenticada.** A view de download aplica `TenantRequiredMixin` + checagem de papel, resolve o `FileAsset` no escopo do tenant e faz streaming dos bytes a partir do `STORAGES['default']` (FS em dev, R2 em prod). O cliente nunca recebe uma URL direta do objeto.

**Justificativa:**
- **Mesma rota em dev e prod**: FileSystemStorage (dev) não emite URL assinada; streaming server-side funciona idêntico nos dois backends, sem `moto`/mock de S3 nos testes.
- **Zero URL pública permanente** (RNF-018 / RISK-005 / `test_no_permanent_public_url`): o controle de acesso fica 100% na view, a cada request — não há janela de URL assinada vazável/compartilhável.
- **Auditoria confiável**: todo download passa pela view → `AuditLog`/`SecurityLog` (Bloco 3) sem depender de o cliente realmente baixar via redirect.

**Implicações:**
- O teste `test_signed_url_expires_in_60s` da `SPRINTS` é **substituído** por testes de streaming/permissão (`test_download_requires_permission`, `test_download_unauthorized_returns_404`, `test_no_permanent_public_url`).
- `STORAGES['default']` do R2 mantém `querystring_auth=True` como rede de segurança (mesmo que `.url()` seja chamado, nunca gera link público) — mas a view não expõe `.url()`.
- Streaming síncrono é aceitável para arquivos ≤10MB (limite de upload do Bloco 2). Revisar se o limite crescer muito.

---

### OD-022 — Acesso do voluntário escalado (magic-link, não login)

| Campo | Valor |
|---|---|
| Status | ✅ Fechada (2026-06-05) |
| Impacto | Médio (escopo + auth + UX) |
| Owner | Produto + Segurança |
| Decisão | **Voluntário escalado** (Pessoa com `Schedule`) acessa "minhas escalas / próximos encontros" **read-only** via **magic-link sem conta** (token assinado, sem senha, sem MFA). **Distinto do Membro geral** (OD-004, que segue sem acesso) |

**Contexto:** ao planejar a UI (Sprint 6.5), o dono esclareceu que **quem é escalado como voluntário deve poder ver o próprio compromisso** — e que isso é um tipo específico de pessoa, **não** o Membro geral. A spec vigente negava ambos: PRD §papéis traz *"Voluntário: Pessoa com `Schedule`, sem login dedicado"* e OD-004 tira o login do Membro.

**Decisão:** criar um acesso de **baixíssima fricção, exclusivo do voluntário escalado**: um **magic-link** (token assinado, TTL configurável) entregue ao ser escalado (email/WhatsApp), abrindo uma visão **read-only mobile** das próprias escalas/próximos encontros. **Não é login** (sem conta, sem senha, sem MFA).

**Justificativa:**
- Quem assume um compromisso (foi escalado) merece visibilidade dele; o **membro passivo** não precisa de acesso — daí a distinção.
- Magic-link **não infla** a app `accounts` (sem `User`/convite/permissões novas), **não reabre OD-004** (Membro geral segue sem acesso) e **não entra no enforce de MFA** da Sprint 7.
- Mantém o PRD coerente: *"sem login dedicado"* continua verdadeiro — magic-link não é login.

**Implicações:**
- **Backend (feature pequena, não só UI):** gerar token assinado escopado à `Person` (TTL); view tokenizada **read-only** que só mostra os dados da própria pessoa; disparo do link na notificação de escala. Entra como sub-tarefa de backend na frente "Voluntário" da Sprint 6.5.
- **Segurança:** token com TTL + escopo individual + somente leitura; nunca expor PII de terceiros; avaliar `SecurityLog` no acesso (leitura sensível).
- **Membro geral (OD-004):** inalterado — sem acesso.

---

### OD-023 — Nome do produto

| Campo | Valor |
|---|---|
| Status | ✅ Decidida (2026-06-05) — **registro de domínio + INPI pendentes de confirmação pelo dono** |
| Impacto | Alto (marca, GTM, landing, logo) |
| Owner | Produto + Dono |
| Decisão | **Oikonos** (marca primária) + **CasaIgreja** (reserva + domínio descritivo/SEO). Substitui o placeholder "Comunhão" |

**Contexto:** o app rodava com placeholder "Comunhão". Avaliados 5 candidatos do dono (Oikonos, Diakonis, Ministrae, Templaris, Celestra) + alternativas, com `.com.br` livre como filtro decisivo (verificado no RDAP do registro.br).

**Decisão:** **Oikonos** — do grego *oîkos* (casa/lar) + *oikonómos* (mordomo da casa) → "administrar a casa da fé": gestão + acolhimento num só conceito, transdenominacional, brandável, `.com.br` livre. **CasaIgreja** como reserva e domínio descritivo (tradução transparente de *oîkos*; `.com.br` livre).

**Justificativa resumida:** toda palavra cristã óbvia (ágape, comunhão, koinonia…) já está registrada no `.com.br` → disponibilidade vive em nomes cunhados. Oikonos é o único cujo significado descreve o produto (administrar a "casa"/comunidade). Descartados: Templaris (conotação templária vs marca acolhedora), Ministrae (pronúncia ambígua), Celestra (domínio tomado).

**Pendências do dono (não automatizáveis):** confirmar disponibilidade e **registrar** `oikonos.com.br` + `casaigreja.com.br` (+ defensivas); **checar marca no INPI** (domínio livre ≠ marca livre).

**Detalhe, história da marca e opções de slogan:** `docs/superpowers/specs/2026-06-05-nome-produto-design.md`.

---

### OD-024 — Módulo Financeiro: **básico no MVP (Sprint 6.7)** + avançado (Sprint 8)

| Campo | Valor |
|---|---|
| Status | ✅ Decidida (2026-06-05) — **revisada no mesmo dia**: financeiro **básico entra no MVP** (Sprint 6.7, pré-piloto); avançado fica na Sprint 8 |
| Impacto | Alto (DNA do produto, escopo, diferencial, infra) |
| Owner | Produto + Dono |
| Decisão | `apps/finance` dividido: **(a) Básico — MVP/Sprint 6.7:** lançamentos (entrada/saída + categorias), dízimos/ofertas (FK opcional a `Person`, **SET_NULL**/LGPD), saldo/totais, **página Financeiro + Dashboard**, export CSV, **papel `treasurer` ativado**. **(b) Avançado — Sprint 8 (pós-piloto):** recibos PDF, conciliação, relatório contábil para assembleia, fechamento, **doação online** (giving via gateway) |

**Contexto:** o dono esclareceu que **o produto nasceu de uma necessidade financeira** — financeiro é **gênese, não add-on**. A 1ª versão desta OD jogava todo o financeiro pós-piloto; **revisada**: o **básico é MVP** (o piloto Athos precisa de tesouraria). A pesquisa de mercado já apontava financeiro como **DOR #1**.

**Justificativa:** financeiro básico no MVP valida o DNA do produto e dá tesouraria ao piloto; o avançado (recibo fiscal, conciliação, giving online) fica pós-piloto para não estourar o prazo. O básico é **recorte cirúrgico**: lançar + categorizar + saldo + dashboard + CSV.

**Implicações:** novo app `finance` no tenant (**Sprint 6.7**); o papel `treasurer` **deixa de ser stub** e ganha telas **no MVP** (Pastor + Tesoureiro, ACCESS_MATRIX); dado financeiro entra na trilha LGPD/AuditLog; **doação online (avançado) exige decisão de gateway** (Stripe proibido → Pix/Mercado Pago/Asaas — futura OD). Marca: financeiro no MVP dá **lastro** a "Mordomia / Honramos o que é de Deus".

---

### OD-025 — Comunicação WhatsApp via Evolution API (pós-piloto, Sprint 9)

| Campo | Valor |
|---|---|
| Status | ✅ Decidida (2026-06-05) — roadmap **pós-piloto (Sprint 9)** |
| Impacto | Alto (canal #1 da igreja BR; risco ToS/LGPD/infra) |
| Owner | Produto + Segurança + Ops |
| Decisão | Integração WhatsApp via **Evolution API** (gateway self-hosted) para mensagens **transacionais/opt-in** (ex.: lembrete de escala, confirmação). A **WhatsApp Business Cloud API oficial permanece FORA** (stack proibida mantida). **Sem disparo em massa/marketing** |

**Contexto:** WhatsApp é o **canal #1** da igreja brasileira (DOR #5). A Business Cloud API oficial está proibida na stack (custo/complexidade); a **Evolution API** (self-hosted, normalmente via Baileys/WhatsApp Web) é a alternativa escolhida.

**Riscos (documentados — decisão de olhos abertos):**
- **ToS / ban:** automação não-oficial viola os termos da Meta; **disparo em massa** é o maior gatilho de bloqueio do número da igreja.
- **LGPD:** dado de frequência religiosa é **sensível** (art. 5º); enviar por WhatsApp exige **consentimento + opt-out**; igreja = controladora, plataforma = operadora.
- **Infra:** **uma sessão/número por tenant** (pareamento QR, reconexão); +1 serviço (Node + banco) no VPS → reforça o **upgrade de VPS** (OD-006).
- **Reliability:** quebra quando o WhatsApp muda; precisa de monitoramento da sessão.

**Mitigações:** uso **transacional/opt-in de baixo volume** (não marketing em massa); consentimento explícito; rate-limit; fila Celery; e caminho de migração para a **Cloud API oficial** depois (o Evolution também a suporta como backend).

---

## Histórico — decisões fechadas

| ID | Decisão | Data | Resultado |
|---|---|---|---|
| OD-002 | MFA obrigatório | 2026-05-27 | Split: opt-in Sprint 2; enforcement obrigatório Sprint 7 |
| OD-003 | Celery + Redis no MVP | 2026-05-27 | Celery + Redis incluído desde Sprint 1 |
| OD-004 | Membro/Pessoa tem login no MVP | 2026-06-01 | Não — Membro existe apenas como `Person`, sem login. Login de Membro fica para a Fase 2 |
| OD-017 | Política de exclusão de tenant (Church) | 2026-06-01 | Igreja não é hard-deletável no MVP — apenas suspensa (RF-003). Exclusão definitiva fica para pós-MVP |
| OD-018 | Camada canônica de enforcement LGPD (`consent_given_at`) | 2026-06-01 | Validação na camada de service (`create_person`/`import_csv`), espelhada no form. Cobre o caminho CSV |
| OD-019 | Modelo de papéis e Gestão de Acessos | 2026-06-04 | Papel `secretary` (admin sem financeiro); `leader` unificado (comunidade/ministério = vínculo); M2M `Community.leaders`/`Ministry.coordinators`; Gestão de Acessos concede funções+escopo (Pastor+Secretário); travas RISK-015 |
| OD-020 | `on_delete` de `Attendance.person` | 2026-06-05 | `SET_NULL` (alinha RN-007: presença preservada no purge da Pessoa); corrige `TECH_SPEC §5.6` que trazia `CASCADE` |
| OD-021 | Mecanismo de download de arquivo (Sprint 6) | 2026-06-05 | Streaming pela view autenticada (não URL assinada R2); substitui `test_signed_url_expires_in_60s` por testes de permissão/streaming |
| OD-022 | Acesso do voluntário escalado | 2026-06-05 | Magic-link read-only sem conta (não login, não MFA), exclusivo de quem tem `Schedule`; Membro geral (OD-004) segue sem acesso |
| OD-023 | Nome do produto | 2026-06-05 | **Oikonos** (marca) + CasaIgreja (reserva/descritivo); substitui placeholder "Comunhão"; registro de domínio + INPI pendentes do dono |
| OD-024 | Módulo Financeiro (básico MVP + avançado) | 2026-06-05 | **Básico no MVP — Sprint 6.7** (lançamentos/dízimos/saldo/**dashboard**/CSV + Tesoureiro ativo); **avançado — Sprint 8** (recibos PDF/conciliação/relatório assembleia/doação online). Produto nasceu de necessidade financeira |
| OD-025 | Comunicação WhatsApp | 2026-06-05 | Via **Evolution API** self-hosted (transacional/opt-in); Business Cloud API oficial fora; pós-piloto **Sprint 9**; riscos ToS/ban/LGPD documentados |
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
