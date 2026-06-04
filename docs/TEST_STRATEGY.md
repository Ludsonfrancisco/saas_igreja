# TEST STRATEGY — SaaS Igreja

> **Versão:** 1.0
> **Data:** 2026-05-27
> **Status:** Source of truth de testes. Sprint não fecha sem cumprir Definition of Done desta página.

---

## 1. Stack de Testes

| Ferramenta | Papel |
|---|---|
| `pytest` | Test runner |
| `pytest-django` | Integração com Django, fixtures, `@pytest.mark.django_db` |
| `pytest-cov` | Cobertura de código |
| `factory_boy` (opcional) | Fábricas de dados (alternativa a fixtures manuais) |
| `pip-audit` + `safety check` | Auditoria de dependências no CI |
| `nplusone` | Detecta consultas N+1 em testes (P-ARQ-09); raise em dev e CI |
| `django-debug-toolbar` | Apenas dev: análise de queries em fluxos novos |

---

## 2. Camadas de Teste

| Camada | O que testa | Velocidade | Cobertura esperada |
|---|---|---|---|
| Unit | Services puros, validators, helpers | Rápida | Alta |
| Integration | Views + ORM + signals + middleware (com banco) | Média | Alta |
| Tenant isolation | Toda view autenticada com dois tenants | Média | 100% das views autenticadas |
| Permissions | Cada par (papel × ação) | Média | 100% das células da matriz |
| Security | Headers, cookies, axes, password policy, auditoria | Rápida | 100% das regras SEC-01..07 |
| Smoke (pós-deploy) | Fluxos críticos em produção | Rápida | Login + 1 CRUD por módulo |
| Performance | Listagens com 500 registros < 500ms | Lenta | Mínima |

---

## 3. Gates de Cobertura

| App | Gate mínimo |
|---|---|
| `core` (mixins, AuditLog, SecurityLog) | 90% |
| `accounts` | 90% |
| `tenants` | 90% |
| `files` | 90% |
| `people` | 80% |
| `communities` | 80% |
| `ministries` | 80% |
| `gatherings` | 80% |
| `schedules` | 80% |
| `dashboard` | 70% |

**Pipeline CI falha se cobertura cair abaixo do gate.**

---

## 4. Estrutura de Arquivos

Cada app tem `tests/` com testes próximos do contexto:

```
apps/people/
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # fixtures locais (factories de Person, mocks)
│   ├── test_models.py
│   ├── test_services.py      # create_person, anonymize_person, export_person_data, import_csv
│   ├── test_views.py
│   ├── test_signals.py       # AuditLog em post_save/post_delete
│   └── test_permissions.py   # PASTOR vs LEADER vs MEMBER
```

Testes transversais ficam em `apps/core/tests/`:

```
apps/core/tests/
├── test_tenant_isolation.py    # Cross-tenant em todas as views autenticadas
├── test_permissions_matrix.py  # Matriz completa de ACCESS_MATRIX.md
├── test_security_headers.py    # Headers em prod
├── test_audit.py               # AuditLog dispara em ações sensíveis
└── test_security_log.py        # SecurityLog dispara em eventos críticos
```

---

## 5. Fixtures Globais (`conftest.py` na raiz)

```python
# conftest.py
import pytest
from django.utils import timezone
from django_tenants.utils import schema_context

# Nota (RN-003a / multi-role): `User.roles` é ArrayField. Fixtures sempre passam
# `roles=[...]` (lista), nunca `role='...'`. Verificação via `user.has_any_role(...)`.

@pytest.fixture
def public_user(db):
    """User criado no schema public."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email='admin@platform.com',
        password='Test1234!',
        roles=['pastor'],
    )

@pytest.fixture
def church_a(db):
    """Tenant A com seu Pastor."""
    from apps.tenants.models import Church, Domain
    church = Church.objects.create(name='Igreja A', slug='a', schema_name='tenant_a')
    Domain.objects.create(domain='a.testserver', tenant=church, is_primary=True)
    return church

@pytest.fixture
def church_b(db):
    """Tenant B com seu Pastor (para testes de isolamento)."""
    from apps.tenants.models import Church, Domain
    church = Church.objects.create(name='Igreja B', slug='b', schema_name='tenant_b')
    Domain.objects.create(domain='b.testserver', tenant=church, is_primary=True)
    return church

@pytest.fixture
def pastor_a(db, church_a):
    from apps.accounts.models import User
    return User.objects.create_user(
        email='pastor@a.com',
        password='Test1234!',
        roles=['pastor'],
        church=church_a,
    )

@pytest.fixture
def pastor_b(db, church_b):
    from apps.accounts.models import User
    return User.objects.create_user(
        email='pastor@b.com',
        password='Test1234!',
        roles=['pastor'],
        church=church_b,
    )

@pytest.fixture
def leader_a(db, church_a):
    from apps.accounts.models import User
    return User.objects.create_user(
        email='leader@a.com',
        password='Test1234!',
        roles=['leader'],
        church=church_a,
    )

@pytest.fixture
def person_in_a(db, church_a):
    from apps.people.models import Person
    with schema_context('tenant_a'):
        return Person.objects.create(
            name='Joao Silva',
            email='joao@example.com',
            consent_given_at=timezone.now(),
        )

@pytest.fixture
def tenant_a_client(client, pastor_a):
    """Client autenticado no tenant A."""
    client.force_login(pastor_a)
    client.defaults['HTTP_HOST'] = 'a.testserver'
    return client

@pytest.fixture
def tenant_b_client(client, pastor_b):
    """Client autenticado no tenant B."""
    client.force_login(pastor_b)
    client.defaults['HTTP_HOST'] = 'b.testserver'
    return client
```

---

## 6. Testes Obrigatórios

### 6.1 Tenant Isolation

`apps/core/tests/test_tenant_isolation.py` percorre todas as views autenticadas e verifica:

```python
@pytest.mark.django_db
def test_pastor_a_cannot_see_person_from_b(tenant_a_client, person_in_b):
    response = tenant_a_client.get(f'/pessoas/{person_in_b.id}/')
    assert response.status_code == 404  # nunca 403 com dado vazado

@pytest.mark.django_db
@pytest.mark.parametrize('url_name', [
    'people:list', 'people:detail', 'communities:list', 'ministries:list',
    'gatherings:list', 'schedules:list', 'files:list', 'dashboard:home',
])
def test_all_authenticated_views_require_tenant(client, url_name):
    response = client.get(reverse(url_name))
    assert response.status_code in (302, 403)  # redireciona para login ou bloqueia
```

### 6.2 Permissions Matrix

`apps/core/tests/test_permissions_matrix.py` cobre cada célula de [`ACCESS_MATRIX.md`](ACCESS_MATRIX.md).

> **Atualização OD-019 (2026-06-04):** a matriz cresceu — nova coluna **Secretário**
> e o teto da Gestão de Acessos. Casos obrigatórios a acrescentar a `PERMISSION_CASES`
> conforme as views nascem: Secretário pode gerir Pessoas/Comunidades/Ministérios/
> Usuários mas **não** anonimizar/exportar/excluir nem mexer em financeiro; e as
> travas `test_secretary_cannot_grant_pastor` / `test_no_self_role_escalation`
> (RISK-015). Multi-líder (M2M) entra no isolation/escopo, não na matriz de papéis.

Exemplo do esqueleto parametrizado:

```python
PERMISSION_CASES = [
    # (papel, url_name, http_method, expected_status)
    ('pastor', 'people:create', 'POST', 302),
    ('leader', 'people:create', 'POST', 302),  # vincula à sua comunidade
    ('member', 'people:create', 'POST', 403),
    ('pastor', 'people:anonymize', 'POST', 302),
    ('leader', 'people:anonymize', 'POST', 403),
    # ... uma linha por célula da matriz
]

@pytest.mark.django_db
@pytest.mark.parametrize('role,url_name,method,expected', PERMISSION_CASES)
def test_permissions_matrix(role, url_name, method, expected, ...):
    ...
```

### 6.3 Auth e Sessions

| Teste | Cobre |
|---|---|
| `test_login_email_only` | RF-010 |
| `test_login_wrong_password_does_not_leak_user_existence` | RF-010 |
| `test_login_inactive_user_blocked` | RF-022 |
| `test_password_reset_no_enumeration` | RF-011 |
| `test_password_reset_token_expires_24h` | RF-011 |
| `test_axes_lockout_after_5_failures` | RF-012 |
| `test_axes_lockout_logged_in_security_log` | RF-012 |
| `test_password_policy_min_8_chars` | RNF-004 |
| `test_password_cannot_be_email_or_name` | RNF-004 |
| `test_session_cookies_secure_httponly_samesite` | RNF-002 |
| `test_security_headers_present_in_prod` | RNF-003 |

### 6.4 Convites

| Teste | Cobre |
|---|---|
| `test_invite_unique_per_church` | RF-013 |
| `test_invite_accepts_multiple_roles` | RN-003a |
| `test_accept_invite_creates_user_and_marks_accepted_at` | RF-014 |
| `test_invite_expires_after_7_days` | RF-013 |
| `test_invite_token_single_use` | RF-014 |
| `test_resend_invite_renews_expiration` | RF-015 |
| `test_no_church_migration_supported` | RN-003 |

### 6.4a Multi-role

| Teste | Cobre |
|---|---|
| `test_user_has_any_role_returns_true_if_intersection_non_empty` | RN-003a |
| `test_user_has_all_roles_requires_subset` | RN-003a |
| `test_treasurer_plus_leader_unions_permissions` | RN-003a |
| `test_pastor_role_dominates_others` | RN-003a |
| `test_remove_pastor_blocked_if_last_pastor_in_church` | RN-004 |

### 6.4b MFA

| Teste | Cobre |
|---|---|
| `test_mfa_totp_opt_in_setup_and_login` | OD-002 (Sprint 2) |
| `test_mfa_backup_codes_single_use` | OD-002 (Sprint 2) |
| `test_mfa_enforced_for_pastor_role` | OD-002 (Sprint 7) |
| `test_mfa_enforced_for_platform_admin` | OD-002 (Sprint 7) |
| `test_member_or_leader_does_not_require_mfa` | OD-002 (Sprint 7) |

### 6.4c Platform Admin e SupportAccess

| Teste | Cobre |
|---|---|
| `test_platform_admin_blocked_without_support_access` | RN-015, RISK-009 |
| `test_grant_support_access_creates_4h_window_and_security_log` | RN-015 |
| `test_support_access_expired_auto_blocks` | RN-015 |
| `test_revoke_support_access_blocks_immediately` | RN-015 |
| `test_platform_admin_every_action_audited_during_support_access` | RN-015 |
| `test_grant_support_access_requires_mfa_on_admin` | OD-002 + RISK-009 |

### 6.5 LGPD

| Teste | Cobre |
|---|---|
| `test_person_create_requires_consent_when_email_or_phone` | RN-005, RF-030 |
| `test_anonymize_person_replaces_pii_and_sets_inactive` | RN-006, RF-034 |
| `test_anonymize_person_audited` | RNF-009 |
| `test_export_person_data_returns_json_and_csv` | RF-035 |
| `test_export_person_data_audited` | RNF-009 |
| `test_person_fk_set_null_after_anonymize` | RN-007 |
| `test_celery_beat_purge_after_30_days` | A1 |

### 6.6 Auditoria e SecurityLog

| Teste | Cobre |
|---|---|
| `test_person_actions_audited` (create/update/delete/export/anonymize) | RNF-009 |
| `test_role_change_audited_and_security_logged` | RF-021 |
| `test_login_success_logged` | RNF-010 |
| `test_login_failure_logged` | RNF-010 |
| `test_auditlog_no_cross_schema_fk` (verifica `user_id IntegerField`) | TENANT-04, RN-014 |
| `test_auditlog_scoped_by_tenant_id` | RNF-006 |

### 6.7 Escalas

| Teste | Cobre |
|---|---|
| `test_schedule_create_validates_ministry_membership` | RF-070 |
| `test_schedule_conflict_blocked` | RF-071, RN-011 |
| `test_schedule_exception_requires_competent_coordinator` | RF-072 |
| `test_schedule_exception_creates_approval_and_audits` | RF-072 |

### 6.8 Arquivos

| Teste | Cobre |
|---|---|
| `test_upload_validates_mime_via_magic` | RF-080, RN-012 |
| `test_upload_rejects_file_above_10mb` | RF-080 |
| `test_upload_rejects_svg` (XSS) | SEC-05 |
| `test_download_requires_permission` | RF-081, RN-013 |
| `test_download_unauthorized_returns_404` | RF-081 |
| `test_no_permanent_public_url` | RNF-018 |
| `test_delete_file_audited` | RF-082 |
| `test_r2_path_isolated_per_tenant` | OD-003a, RISK-001 |
| `test_signed_url_expires_in_60s` | OD-003a |

### 6.9 Dashboard

| Teste | Cobre |
|---|---|
| `test_dashboard_scoped_no_leak` | RF-090, RISK-001 |
| `test_dashboard_leader_sees_only_own_community` | RF-091 |
| `test_dashboard_coordinator_sees_only_own_ministry` | RF-091 |

### 6.10 Plano

| Teste | Cobre |
|---|---|
| `test_plan_limit_enforced_on_person_create` | RN-008, OPS-04 |
| `test_plan_limit_enforced_on_community_create` | RN-008 |
| `test_unlimited_plan_max_persons_zero` | RN-008 |

### 6.11 Backup

| Teste | Cobre |
|---|---|
| `test_backup_cron_documented` (smoke) | RF-100, RNF-015 |
| Restore manual mensal (não automatizado) | RF-101, RNF-016, RNF-023 (RTO/RPO) |

### 6.12 Healthcheck e Observabilidade

| Teste | Cobre |
|---|---|
| `test_health_endpoint_returns_200` | RNF-022 |
| `test_health_endpoint_no_auth_required` | RNF-022 |
| `test_ready_endpoint_returns_200_when_pg_and_redis_ok` | RNF-022 |
| `test_ready_endpoint_returns_503_when_pg_down` | RNF-022 |
| `test_ready_endpoint_returns_503_when_redis_down` | RNF-022 |

### 6.13 Performance e N+1

| Teste | Cobre |
|---|---|
| `test_no_n_plus_one_in_listings` (varre cada `ListView` com `nplusone.Middleware`) | RNF-024, P-ARQ-09 |
| `test_listings_paginated` (lista com 30 registros retorna 25 por página) | RNF-021 |
| `test_list_performance` (500 registros < 500ms) | RNF-011 |

---

## 7. Padrões de Teste

### 7.1 Use `pytest.mark.django_db`

```python
@pytest.mark.django_db
def test_x():
    ...
```

### 7.2 Use `schema_context` para tenant

```python
from django_tenants.utils import schema_context

with schema_context('tenant_a'):
    Person.objects.create(...)
```

### 7.3 Use parametrize para matrizes

```python
@pytest.mark.parametrize('role,can_create', [
    ('pastor', True),
    ('leader', True),
    ('member', False),
])
def test_create_permission(role, can_create, ...):
    ...
```

### 7.4 Nomes descritivos

- **Bom:** `test_anonymize_person_replaces_pii_and_sets_inactive`
- **Ruim:** `test_anonymize_works`

### 7.5 Um assert por conceito, não um assert por teste

Vários `assert` no mesmo teste são OK se cobrem o mesmo conceito.

### 7.6 Não mockar o banco

Use `pytest-django` com banco real (Postgres em dev e CI). Mocks só para integrações externas (Sentry, S3, email).

---

## 8. CI / Pipeline

Estrutura mínima do pipeline:

1. `uv sync` — instala dependências
2. `ruff check` — lint
3. `black --check` — format check
4. `pip-audit` — CVEs
5. `safety check` — CVEs adicionais
6. `pytest --cov=apps --cov-report=term-missing --cov-fail-under=<gate>` — testes com cobertura
7. Bloquear merge se algum passo falhar

---

## 9. Definition of Done por Sprint

Uma sprint só fecha quando:

- [ ] Todos os testes da sprint passam localmente e no CI
- [ ] `test_tenant_isolation_matrix` aplicável passa (Sprints 1–7)
- [ ] `test_permissions_matrix` aplicável passa (Sprints 2–7)
- [ ] Auditoria das ações sensíveis está ativa e testada
- [ ] `pip-audit` + `safety check` sem CVEs novas
- [ ] Cobertura por app respeita o gate (Seção 3)
- [ ] Lighthouse mobile ≥ 90 nas telas tocadas (Sprints 1–7)
- [ ] Documentação atualizada (`PRD.md`, docs deste diretório, `OPEN_DECISIONS.md`)

---

## 10. Anti-Padrões em Testes

| ID | Não fazer |
|---|---|
| TAP-01 | Mockar o ORM ou o banco. Use Postgres real. |
| TAP-02 | Testar implementação em vez de comportamento. |
| TAP-03 | Compartilhar estado entre testes (use fixtures + transações). |
| TAP-04 | Pular testes (`@pytest.mark.skip`) sem ticket vinculado. |
| TAP-05 | Asserts vagos (`assert response` em vez de `assert response.status_code == 200`). |
| TAP-06 | Testes flaky tolerados. Falha intermitente vira issue imediata. |
| TAP-07 | Esquecer `@pytest.mark.django_db` em teste que toca o ORM. |
| TAP-08 | Hardcodar UUIDs/IDs em vez de usar fixtures. |
