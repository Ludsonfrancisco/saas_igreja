# Relatório de Validação — PRD.md

**Data:** 2026-05-28
**Reviewer:** code-reviewer-tech-lead (agente)
**Documento:** PRD.md
**Task vinculada:** docs/SPRINTS.md linha 51 — "Validar PRD com líder principal do produto"

---

## Veredicto

**APROVADO COM RESSALVAS**

---

## Sumário executivo

O PRD versão 1.0 está maduro, completo e operacional como source of truth para o MVP. Os 12 pontos do checklist auditado retornam 8 PASS, 4 PARTIAL e 0 FAIL — nenhum bloqueador. As ressalvas são desvios de coerência cruzada e completude editorial: (a) o "dono do projeto" é citado genericamente sem nome próprio na capa; (b) numeração `RF-001..RF-101` no título cria expectativa de 101 requisitos quando existem ~32 efetivos com prefixos por categoria; (c) RF-013 fala em "papel obrigatório" (singular) mas o modelo `Invite` (PRD §15.2) já usa `roles ArrayField` plural; (d) duas decisões fechadas que já vivem em OPEN_DECISIONS.md (OD-015 GitHub Actions, OD-016 RTO/RPO) ainda não foram refletidas no PRD §29.1. Nada disso impede o início da Sprint 1, mas vale corrigir antes do versionamento final por higiene de rastreabilidade.

---

## Checklist (12 pontos)

| ID | Item | Status | Evidência | Observação |
|---|---|---|---|---|
| 1 | Capa, versão, data, dono identificados (§1) | PARTIAL | PRD.md:3-5, PRD.md:13-24 | Versão 1.0, data 2026-05-27 e status presentes; campo "dono"/"owner" nominal ausente — só referência genérica a "dono do projeto" nas regras G-01..05 |
| 2 | Governança G-01..G-05 explícita e idêntica em PRD §1.1 e CLAUDE.md | PASS | PRD.md:30-38, CLAUDE.md:22-26 | Texto semanticamente equivalente; PRD ligeiramente mais formal mas sem divergência operacional |
| 3 | Personas (Pastor, Líder, Coordenador, Tesoureiro, Secretaria, Membro, PlatformAdmin) com responsabilidades claras | PASS | PRD.md:126-172 | 7 personas listadas em §6.1..6.7; Tesoureiro marcado como "futuro/fora do MVP profundo"; Secretaria aparece como persona em §6.4 e como ator em RFs (não é role própria — é Pastor/Líder/Secretaria agregado) |
| 4 | RF-001..RF-101: numeração contínua; cada RF tem ator, ação, critério; vinculado a sprint | PARTIAL | PRD.md:323-413, PRD.md:1221-1251 | Numeração usa prefixos por categoria (RF-00x tenants, RF-01x auth, RF-02x users, RF-03x people, RF-04x communities, RF-05x ministries, RF-06x gatherings, RF-07x schedules, RF-08x files, RF-09x dashboard, RF-10x ops) — não há 101 RFs sequenciais, existem ~32 efetivos. O título "RF-001..101" é enganoso. Cada RF tem ator, critério e sprint na coluna; vínculo formal por RF→sprint em §11 e §26 (matriz de rastreabilidade). SPRINTS.md NÃO referencia RFs individuais — apenas backlog ainda aberto cita "RF-001..101 como issues" |
| 5 | RNF-001..RNF-024: segurança, performance, LGPD, observabilidade, RTO/RPO; thresholds quantificáveis | PASS | PRD.md:421-444 | 24 RNFs contínuos (RNF-001..024), todos com critério verificável e validação atribuída; RNF-023 fixa RTO 4h/RPO 24h; RNF-021 paginação >25 registros; RNF-011 <500ms em 500 registros; RNF-024 N+1 via nplusone |
| 6 | RN-001..RN-015 presentes (especialmente RN-003, RN-003a, RN-004, RN-005..007, RN-009, RN-010, RN-015) | PASS | PRD.md:452-467 | 16 RNs (RN-001..015 com RN-003a entre RN-003 e RN-004); todas as RNs solicitadas presentes — RN-003 (1 user→1 igreja, sem migração), RN-003a (multi-role união), RN-004 (último Pastor), RN-005..007 (LGPD), RN-009 (unique Attendance), RN-010 (COMMUNITY oculto), RN-015 (SupportAccess) |
| 7 | RISK-001..RISK-009 com mitigação e teste vinculado (em particular RISK-001 e RISK-009) | PASS | PRD.md:1262-1277 | 14 RISKs (RISK-001..014); RISK-001 vazamento cross-tenant com `test_tenant_isolation_matrix`; RISK-009 SupportAccess com `test_platform_admin_blocked_without_support_access`; cada um tem coluna Mitigação + Teste/Validação + Sprint |
| 8 | Linguagem de domínio pt-BR consistente entre PRD, ACCESS_MATRIX, CLAUDE.md | PASS | PRD.md:185, PRD.md:203-206, ACCESS_MATRIX.md:1-23, CLAUDE.md:108-115 | Termos Pessoa, Comunidade, Ministério, Encontro, Presença, Escala, Líder Principal configurável (`leader_title`) — coincidentes nos três documentos; interface pt-BR, código inglês (RNF-013) |
| 9 | 8 sprints (0–7) no PRD batem com docs/SPRINTS.md | PASS | PRD.md:1114-1191, SPRINTS.md:33-509 | Títulos IDÊNTICOS Sprint 0 (Planejamento e Fundação SDD), Sprint 1 (Fundação Django+PostgreSQL+django-tenants), Sprint 2 (Auth+Convites+Autoriz+Audit+SecurityLog), Sprint 3 (Pessoas+Comunidades+Ministérios), Sprint 4 (Encontros+Cultos+Presença), Sprint 5 (Escalas+Voluntários com Bloqueio de Conflito), Sprint 6 (Arquivos/PDFs+Dashboard+Permissões de Mídia), Sprint 7 (Deploy Beta+Backup+Restore+Hardening+Piloto Athos) |
| 10 | Decisões fechadas (OD-002, OD-003, OD-003a, OD-006, OD-007, OD-012) marcadas em PRD §29.1 e OPEN_DECISIONS.md; abertas idem | PARTIAL | PRD.md:1327-1335, OPEN_DECISIONS.md:308-322 | As 6 ODs do checklist estão fechadas em ambos. PORÉM: OPEN_DECISIONS.md histórico (linhas 318-319) registra OD-015 (GitHub Actions) e OD-016 (RTO 4h/RPO 24h) como fechadas em 2026-05-27, mas o PRD §29.1 NÃO lista OD-015 nem OD-016 — embora o conteúdo (RTO/RPO) viva em PRD §20.4 e RNF-023. Falta sincronia editorial |
| 11 | Multi-role (RN-003a) documentado como UNIÃO; exemplo `['treasurer', 'leader']` consistente em PRD, ACCESS_MATRIX e CLAUDE.md | PASS | PRD.md:455, PRD.md:593, PRD.md:601-605, ACCESS_MATRIX.md:25-37, CLAUDE.md:84-87 | Os três documentos repetem: união de permissões, verificação via `user.has_any_role(*roles)`, exemplo `['treasurer', 'leader']`, regra "Pastor sempre domina"; ACCESS_MATRIX.md §1.1 tabela explicita os pares |
| 12 | LGPD §RN-005..007: consent_given_at, anonymize_person, purge 30 dias via Celery Beat, FK SET_NULL, export_person_data | PASS | PRD.md:457-459, PRD.md:359-360, PRD.md:651-664, PRD.md:738-739 | RN-005 consent_given_at obrigatório com PII; RN-006 soft delete + purge semanal; RN-007 FK SET_NULL; RF-034 anonymize_person; RF-035 export_person_data JSON+CSV+AuditLog; §17.2 mapa LGPD operacional; Celery Beat purge via decisão OD-003 (PRD:767) |

**Totais:** 8 PASS · 4 PARTIAL · 0 FAIL

---

## Bloqueadores (FAIL)

_Nenhum._

---

## Ressalvas (PARTIAL)

### R-01 — Capa sem dono nominal (Checklist #1)

**Onde:** PRD.md:3-5 e PRD.md:13-24.
**Problema:** O bloco de cabeçalho identifica versão (1.0), data (2026-05-27), status, mercado-alvo, piloto comercial e stack — mas não nomeia o "dono do projeto" referenciado em G-01..G-05 e nas regras de aprovação de sprint. O PRD é claro sobre o papel (G-01..G-05 mencionam "dono do projeto") porém o papel não está vinculado a uma pessoa identificável.
**Como ajustar:** Adicionar linha na tabela §1 do tipo `| Dono do projeto | <Nome / contato> |` ou explicitar que o dono está identificado em outro documento operacional (ex.: `INFRA.md` ou Notion).

### R-02 — Numeração "RF-001..RF-101" é enganosa (Checklist #4)

**Onde:** PRD.md:313 ("convenção") e PRD.md:1389 ("Próximos passos: Transcrever requisitos do PRD em backlog inicial (RF-001..101 como issues)") e SPRINTS.md:65.
**Problema:** A convenção sugere até 101 requisitos funcionais sequenciais, mas o PRD usa **prefixos por categoria** (RF-00x, RF-01x, RF-02x, ..., RF-10x) com aproximadamente 32 RFs efetivos. Quem ler "RF-001..101" pode tentar buscar RF-005, RF-019, RF-024, RF-036..039, RF-043..049, etc. — IDs que não existem por design.
**Como ajustar:** (a) Trocar texto para "RFs organizados por categoria com prefixos RF-00x..RF-10x" ou (b) listar explicitamente no §11 quais blocos de prefixo existem ("RF-00x Tenants, RF-01x Accounts, RF-02x Users, ..."). O esquema de prefixos é boa prática, só falta documentar.

### R-03 — RF-013 fala em "papel obrigatório" singular vs. modelo `Invite.roles` plural (Checklist #4)

**Onde:** PRD.md:334 (RF-013 critério: "papel obrigatório") versus PRD.md:550 (`Invite.roles ArrayField(CharField(choices=User.Role.choices))`) versus PRD.md:733 (`Invite | public | UUID token, expires_at, roles ArrayField, unique(church, email)`) e SPRINTS.md:192 (`create_invite (aceita lista de roles)`).
**Problema:** Inconsistência interna: o critério de aceite usa singular ("papel obrigatório"), mas o model, a UI prevista (SPRINTS.md:193 "selecionar múltiplas roles") e RN-003a já estabeleceram multi-role no convite. Quem só ler a tabela §11.2 pode achar que convite atribui 1 role apenas.
**Como ajustar:** Reescrever critério do RF-013 para algo como "Criar `Invite` com token UUID, expiração 7 dias, **lista de roles obrigatória (ArrayField, ≥1)**, email único por igreja". Atualizar CA-013 (PRD.md:1000) na mesma linha (atualmente ela usa "papel LEADER" — singular).

### R-04 — OD-015 e OD-016 fechadas em OPEN_DECISIONS.md mas ausentes em PRD §29.1 (Checklist #10)

**Onde:** OPEN_DECISIONS.md:318-319 (linhas históricas registrando OD-015 GitHub Actions e OD-016 RTO 4h/RPO 24h fechadas em 2026-05-27) versus PRD.md:1327-1335 (§29.1 lista apenas OD-002, OD-003, OD-003a, OD-006, OD-007, OD-012, RN-MULTI-ROLE, RN-NO-CHURCH-MIGRATION).
**Problema:** O conteúdo de OD-016 (RTO/RPO) já vive em PRD §20.4 (linhas 864-875) e RNF-023, então a decisão técnica está coberta. OD-015 (CI/CD GitHub Actions) é mencionada em CLAUDE.md:33 ("CI/CD GitHub Actions decidido OD-015") e em SPRINTS.md:71, mas **não está listada no §29.1 do PRD**. A ausência de OD-015/OD-016 na tabela §29.1 quebra a regra do próprio PRD de que toda decisão fechada deve ser refletida no documento de origem (PRD).
**Como ajustar:** Adicionar duas linhas em PRD §29.1:

```
| OD-015 | Plataforma de CI/CD | GitHub Actions; pipeline em .github/workflows/ci.yml |
| OD-016 | RTO / RPO baseline beta | RTO 4h / RPO 24h (limitado por pg_dump diário) |
```

---

## Recomendações opcionais

Estas observações estão fora do escopo de aprovação do PRD mas merecem registro:

1. **Inconsistência cruzada TEST_STRATEGY.md vs RN-003a:** `docs/TEST_STRATEGY.md:99,124,134,144` usam `role='pastor'` / `role='leader'` (singular) nas fixtures de exemplo, contradizendo `User.roles ArrayField` definido por RN-003a. Esses exemplos viram ponto de confusão na Sprint 1 quando o `User` for criado. Sugestão: atualizar exemplos para `roles=['pastor']`, `roles=['leader']`. **Não bloqueia o PRD**, mas vale corrigir junto na próxima janela de revisão de documentação.

2. **Persona "Secretaria" sem role no modelo:** §6.4 define Secretaria como persona, e RFs (RF-030..035, RF-080) listam Secretaria como ator, mas o modelo `User.Role` em PRD §8.1:200 só lista PASTOR/LEADER/TREASURER/MEMBER. Provavelmente Secretaria é tratada como `roles=['leader']` ou como permissão delegada via Pastor — o PRD pode tornar isso explícito em ACCESS_MATRIX ou na própria definição de Persona 4.

3. **CA-013 menciona papel singular** (PRD.md:1000 "papel LEADER"): coerente com R-03 acima, mas registrado separadamente para evitar esquecimento na revisão do critério.

4. **§30.3 item 3 desatualizado:** PRD.md:1389 menciona "Próximas a endereçar: OD-004 (login Membro), OD-008 (OAuth Google) e OD-013 (template de privacidade) na Sprint 2". OD-013 está marcada como Sprint 2, mas OD-004 marca Sprint 3 em OPEN_DECISIONS.md:115. Pequena dessincronização de prazo.

5. **Considerar adicionar §1.2 ou anexo "Glossário de IDs":** com tabela única explicando prefixos RF-XXX, RNF-XXX, RN-XXX, RISK-XXX, OD-XXX, CA-XXX, P-ARQ-XX, AP-XX, G-XX, TENANT-XX, SEC-XX, TAP-XX — facilita onboarding e referência cruzada futura.

---

## Conclusão

O PRD versão 1.0 está pronto para servir como source of truth do MVP. As 4 ressalvas (R-01 a R-04) são correções editoriais menores, todas resolvíveis em uma única passada de edição (~30 min) e nenhuma delas impede a autorização da Sprint 1 (G-01). Recomendo ao dono do projeto: (a) aprovar o PRD condicionalmente, (b) abrir uma task pequena de pós-revisão para aplicar R-01..R-04 antes do versionamento final 1.0.1 ou 1.1, (c) corrigir em paralelo a inconsistência de fixtures em TEST_STRATEGY.md (recomendação opcional 1) para garantir que a Sprint 1 não comece com exemplos contraditórios. Após essas correções, o PRD pode ser marcado como "aprovado pelo líder principal do produto" — fechando definitivamente as duas tasks abertas em SPRINTS.md linhas 51-52.
