# Documentação — SaaS Igreja

Índice da documentação do projeto. A fonte de verdade de produto é o [`PRD.md`](../PRD.md) na raiz.

Esta pasta contém os documentos derivados que aprofundam áreas específicas do PRD.

## Como ler

1. Comece pelo [`PRD.md`](../PRD.md) — contexto, escopo, requisitos, riscos.
2. Vá para o documento desta pasta correspondente à sua área (arquitetura, permissões, testes, sprints, decisões abertas).
3. Em caso de conflito entre documentos, prevalece a fonte mais específica e mais recente. Conflitos não resolvíveis vão para [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md).

## Documentos

| Arquivo | Para quê serve | Quando consultar |
|---|---|---|
| [`TECH_SPEC.md`](TECH_SPEC.md) | Stack, modelos, estrutura de apps, princípios arquiteturais (P-ARQ-01..08, TENANT-01..07, STYLE-01..05, SEC-01..07, OPS-01..04) e anti-padrões (AP-01..13) | Antes de codar qualquer feature; durante revisão de PR |
| [`ACCESS_MATRIX.md`](ACCESS_MATRIX.md) | Matriz detalhada de permissões por módulo × ação × papel | Ao criar view, service ou queryset sensível; ao adicionar novo papel |
| [`TEST_STRATEGY.md`](TEST_STRATEGY.md) | Estratégia de testes, fixtures, factories, gates de cobertura e Definition of Done | Ao escrever testes; ao fechar sprint |
| [`SPRINTS.md`](SPRINTS.md) | Detalhamento operacional das sprints do MVP (Sprint 0 → 7, com **6.5 Design/UI Athos**, **6.6 Athos v2** e **6.7 Financeiro** entre 6 e 7) | No planejamento e na execução de sprint |
| [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md) | Decisões em aberto com owner, prazo, impacto e status | Antes de tomar decisão que afete áreas em aberto; revisão semanal |

## Regras de governança (inviolável)

Aplicáveis a qualquer agente, dev externo ou colaborador. Em caso de dúvida, **pergunte antes de agir**.

- **G-01.** Nenhuma sprint começa sem autorização explícita do dono do projeto.
- **G-02.** Nenhuma task é executada sem revisão prévia. Proibido pular de uma task para a próxima sem aprovação.
- **G-03.** Nenhum `git commit`, `git push`, `git merge` ou abertura de PR é feito pelo agente. **Apenas o dono versiona.**
- **G-04.** Mudanças em arquivos ficam no workspace para revisão; nunca são consideradas "entregues" antes da aprovação.
- **G-05.** Qualquer decisão técnica fora do escopo da task atual exige consulta antes de implementação.

## Regras invioláveis (resumo)

Estas regras aparecem em vários documentos. Em caso de dúvida, valem.

1. **Toda view autenticada usa `TenantRequiredMixin`.** Vazamento cross-tenant é risco crítico (RISK-001).
2. **Permissões são backend.** Menu/template nunca é segurança.
3. **`User` é model público.** Nenhuma model dentro do tenant schema referencia `User` por FK (TENANT-04).
4. **Verificação de papel sempre via `user.has_any_role(*roles)`.** `User.roles` é lista. Permissões são união (RN-003a).
5. **Um usuário pertence a uma única igreja.** Migração entre igrejas não é suportada — excluir e recriar (RN-003).
6. **Platform Admin não acessa tenant sem `SupportAccess` ativo.** Expira em 4h, audita toda ação (RN-015).
7. **MFA obrigatório para `pastor` e `PlatformAdmin`** (a partir da Sprint 7; opt-in disponível desde Sprint 2).
8. **`AuditLog` e `SecurityLog` em ações sensíveis.** Sem auditoria, ação não é completa.
9. **PostgreSQL sempre.** SQLite é proibido (AP-13).
10. **LGPD desde o cadastro.** `consent_given_at` obrigatório quando há PII (RN-005).
11. **Storage de mídia em Cloudflare R2** desde Sprint 6 (sem volume local em prod).
12. **Design system inviolável.** Marca (landing) = **Terracota & Âmbar fixa**; app (área logada) = **base neutra temável por igreja** (`Church.accent_color`/`hot_color`/`logo`). O design system (base.html + `tailwind.config` + componentes) é **consolidado na Sprint 6.5**; referência visual em `referencias/` (direção da marca + `referencias/templates/igreja_saas_novo.html` como padrão de qualidade do app). Nenhuma cor/fonte/componente fora desses tokens.
13. **Prevenção de N+1.** `select_related`/`prefetch_related` obrigatórios em listagens (P-ARQ-09); `nplusone` quebra teste em CI.
14. **Paginação obrigatória** em listas com >25 registros (RNF-021). Carregar lista completa em template é proibido.
15. **Healthcheck:** `/health/` (liveness) e `/ready/` (Postgres+Redis) sempre ativos (RNF-022).
16. **RTO 4h / RPO 24h** baseline do beta (RNF-023).

## O que NÃO está nesta pasta (ainda)

Os documentos abaixo serão criados na sprint indicada. Não existem ainda — não invente conteúdo.

| Documento | Sprint | Conteúdo |
|---|---|---|
| `THREAT_MODEL.md` v1 | 1 | Versão curta (~1 página): atacantes, superfície, mitigações |
| `INFRA.md` | 1 | Topologia de produção (VPS Hostinger KVM 2, EasyPanel, Cloudflare, R2) |
| `PRIVACY_POLICY.md` | 2 | Política de privacidade modelo por igreja |
| `RESTORE.md` | 7 | Runbook de restauração de backup (RTO 4h / RPO 24h) |
| `THREAT_MODEL.md` v2 | 7 | Revisão formal antes do beta público |
| `INCIDENT_RESPONSE.md` | 7 | Procedimento de notificação LGPD e incidentes |

## Mudanças na documentação

- Toda mudança relevante incrementa a versão do documento afetado.
- Mudanças no escopo, stack ou regras invioláveis exigem atualização do PRD primeiro, depois dos documentos derivados.
- Decisões abertas que se fecham devem ser movidas de `OPEN_DECISIONS.md` para o documento onde a decisão se aplica.
