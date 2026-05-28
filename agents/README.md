# Agents — SaaS Igreja

Índice dos agentes de IA do time de desenvolvimento. Cada agente é especialista em uma área da stack do projeto e produz código de forma alinhada ao [`PRD.md`](../PRD.md), aos documentos em [`docs/`](../docs/) e ao [`CLAUDE.md`](../CLAUDE.md).

## Governança aplicável a todos os agentes

Antes de qualquer ação, todo agente respeita as regras de governança definidas em `PRD.md §1.1`:

- **G-01** Sprint só inicia com autorização explícita do dono.
- **G-02** Task só executa após revisão prévia; proibido pular para próxima.
- **G-03** Nunca `git commit`, `git push`, `git merge` ou abrir PR.
- **G-04** Mudanças ficam no workspace para revisão.
- **G-05** Decisão técnica fora do escopo da task exige consulta.

## MCP servers utilizados

| MCP | Quem usa | Para quê |
|---|---|---|
| **context7** | Todos os agentes técnicos | Documentação atualizada de Django, HTMX, Tailwind, PostgreSQL, django-tenants, allauth, axes, Celery, etc. |
| **playwright** | `qa-engineer` | E2E em browser real, verificação visual, captura de telas |
| **notion** | Todos | Consultar `00_SaaS Igreja — Painel do Projeto` em caso de dúvida sobre escopo, decisões ou histórico |

## Agentes

| Arquivo | Papel | Quando usar |
|---|---|---|
| [`backend-engineer.md`](backend-engineer.md) | Desenvolvedor Backend (Django + django-tenants) | Implementar models, services, signals, views CBV, forms, formularios, integração allauth/axes/Celery |
| [`frontend-engineer.md`](frontend-engineer.md) | Desenvolvedor Frontend (HTMX + Alpine.js + Tailwind) | Implementar templates, partials HTMX, componentes Alpine, telas seguindo design system Athos |
| [`database-engineer.md`](database-engineer.md) | Engenheiro de Banco (PostgreSQL 15 + django-tenants) | Modelar schemas, escrever migrations, otimizar queries, gerenciar índices e schema-per-tenant |
| [`security-engineer.md`](security-engineer.md) | Engenheiro de Segurança + LGPD | Implementar auth, MFA, SupportAccess, AuditLog/SecurityLog, isolamento multi-tenant, LGPD (`anonymize_person`, `export_person_data`) |
| [`qa-engineer.md`](qa-engineer.md) | QA Engineer (pytest + Playwright) | Escrever testes unit/integration/E2E, tenant isolation, permissions matrix, verificar UI no browser |
| [`devops-engineer.md`](devops-engineer.md) | DevOps Engineer | Docker, EasyPanel, Cloudflare, R2, GitHub Actions CI/CD, healthcheck, backup/restore |
| [`code-reviewer.md`](code-reviewer.md) | Code Reviewer / Tech Lead | Revisar PR/diff contra PRD, anti-padrões AP-01..13, princípios P-ARQ-01..09, governança G-01..05 |

## Como invocar um agente

1. Identifique o tipo de task (backend, frontend, teste, etc.).
2. Carregue o conteúdo do arquivo correspondente como contexto/persona.
3. Forneça a task específica, o RF/RNF/RN do PRD que ela atende, e o sprint atual.
4. Aguarde aprovação do dono antes de executar próxima task (G-02).

## Quando combinar agentes

| Task | Agentes necessários |
|---|---|
| Nova feature CRUD (ex: Pessoas) | backend → frontend → security (audit/permissions) → qa → code-reviewer |
| Migração de schema | database → backend → qa → code-reviewer |
| Hardening de segurança | security → backend → qa → code-reviewer |
| Setup de CI/CD ou deploy | devops → security (secrets) → code-reviewer |
| Novo componente de UI | frontend → qa (visual) → code-reviewer |
| Investigação de bug de performance | database → backend → qa → code-reviewer |

## Ordem de leitura para qualquer agente novo

1. [`../CLAUDE.md`](../CLAUDE.md) — orientação curta de operação.
2. [`../PRD.md`](../PRD.md) — produto e regras invioláveis.
3. [`../docs/README.md`](../docs/README.md) — índice da documentação.
4. Arquivo do próprio agente.
5. Doc(s) específicos da task: `TECH_SPEC.md`, `ACCESS_MATRIX.md`, `TEST_STRATEGY.md`, `SPRINTS.md`, `OPEN_DECISIONS.md`.
