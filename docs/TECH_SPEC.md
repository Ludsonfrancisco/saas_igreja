# TECH SPEC — SaaS Igreja

> **Versão:** 1.0
> **Data:** 2026-05-27
> **Status:** Source of truth técnica. Conflitos com [`../PRD.md`](../PRD.md): produto vence em escopo, este documento vence em decisão técnica.

Este documento detalha decisões técnicas, modelos completos, estrutura de apps, princípios e anti-padrões. Os requisitos funcionais e não funcionais estão no [`PRD.md`](../PRD.md).

---

## 1. Stack Oficial

| Camada | Tecnologia | Versão mínima | Papel |
|---|---|---|---|
| Backend | Django | 5.2+ | Framework principal |
| Frontend | HTMX + Alpine.js + TailwindCSS | HTMX 1.9+ | SSR + interatividade pontual |
| ORM | Django ORM | — | Persistência |
| Banco | PostgreSQL | 15+ | Requisito de schema-per-tenant |
| Multi-tenancy | django-tenants | última estável | Schema-per-tenant |
| Auth | django-allauth | última estável | Login por email |
| Brute force | django-axes | última estável | Account lockout |
| Testes | pytest + pytest-django + pytest-cov | — | Test suite |
| Lint/format | Ruff + Black | — | Qualidade |
| Package manager | uv | — | Dependências |
| Monitoramento | Sentry SDK | — | Erros + tags por tenant |
| Async | Redis + Celery + Celery Beat | última estável | Importação CSV, purge LGPD semanal, emails (decisão OD-003) |
| Email transacional | `django-anymail[brevo]` | última estável | Convites + recuperação de senha via Brevo free tier (decisão OD-012); desde Sprint 2 |
| Validação de arquivos | `python-magic` | última estável | Validação de MIME real no upload (RF-080 / RN-012); desde Sprint 6 |
| Config / secrets | `python-decouple` | última estável | Variáveis de ambiente e secrets fora do código (SEC-06); desde Sprint 1 |
| PDF (pós-MVP) | WeasyPrint | — | Relatórios complexos |
| Storage de mídia | Cloudflare R2 (S3-compatible) via `django-storages` | última estável | MVP desde Sprint 6 (decisão OD-003a / OD-007) |
| Detecção de N+1 | `nplusone` | última estável | Raise em dev/CI quando há query N+1 (P-ARQ-09 / RNF-024); desde Sprint 1 |
| Profiling de queries (dev) | `django-debug-toolbar` | última estável | Apenas dev; análise de queries em fluxos novos; desde Sprint 1 |
| Deploy | Docker + EasyPanel Free + Cloudflare Free | — | Bootstrapped |
| CI/CD | GitHub Actions | — | Lint, testes, auditoria de deps (decisão OD-015); desde Sprint 1 |

### 1.1 Proibições explícitas

- **SQLite** (incompatível com django-tenants — AP-13).
- **Next.js, React SPA, Vue SPA, Prisma, Auth.js, FastAPI, SQLAlchemy** (fora do stack oficial).
- **WhatsApp Business Platform/Cloud API oficial** (custo proibitivo).
- **LangChain, LangGraph, IA generativa** (fora do MVP).
- **Stripe e billing automatizado** (cobrança manual no MVP).
- **Prometheus, Grafana** (Sentry resolve no MVP).
- **`fields = '__all__'` em ModelForm** (mass assignment — AP-10).
- **`@csrf_exempt`** (a menos que justificado e auditado).
- **Raw SQL com f-strings ou concatenação** (use ORM ou parâmetros).

---

## 2. Estrutura de Diretórios

```
saas_igreja/
├── compose/
│   ├── django/Dockerfile          # Multi-stage (builder + production)
│   ├── celery/Dockerfile          # FROM django stage
│   └── production.yml             # Gunicorn + Celery + Redis + Postgres + Sentry
├── docker-compose.yml             # Dev: PostgreSQL + Redis + app
├── pyproject.toml                 # uv + Ruff + Black config
├── tailwind.config.js             # Paleta Athos
├── package.json                   # TailwindCSS CLI
├── .env.example                   # Variáveis de ambiente (sem secrets reais)
├── manage.py
├── PRD.md                         # Source of truth de produto
├── docs/                          # Esta pasta
├── referencias/
│   ├── templates/igreja_saas_novo.html  # Referência de qualidade do app (DS na Sprint 6.5)
│   └── design_system/                    # Direção de marca + análise de concorrentes
│
├── core/
│   ├── settings/
│   │   ├── base.py                # Settings comuns
│   │   ├── dev.py                 # PostgreSQL via docker-compose; DEBUG=True
│   │   └── prod.py                # PostgreSQL gerenciado/VPS; SECURE_*
│   ├── celery.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
└── apps/
    ├── core/                      # BaseModel, mixins, middleware, AuditLog, SecurityLog
    │   ├── models.py              # BaseModel + AuditLog + SecurityLog
    │   ├── mixins.py              # TenantRequiredMixin (re-export), PastorRequiredMixin, etc.
    │   ├── middleware.py          # Headers de segurança extras + MFARequiredForRoleMiddleware (Sprint 7)
    │   ├── services.py            # Helpers compartilhados
    │   ├── validators.py          # FileExtensionValidator, MagicValidator
    │   ├── admin.py               # TenantAdminMixin (proíbe admin padrão em prod)
    │   ├── apps.py
    │   └── tests/
    │       ├── test_tenant_isolation.py
    │       ├── test_permissions_matrix.py
    │       ├── test_security_headers.py
    │       └── test_audit.py
    │
    ├── accounts/                  # User, Invite, allauth
    │   ├── models.py              # User + UserManager + Invite
    │   ├── backends.py            # EmailBackend
    │   ├── forms.py
    │   ├── views.py
    │   ├── urls.py
    │   ├── signals.py             # Conectar em apps.py.ready()
    │   ├── validators.py          # PasswordPolicyValidator
    │   ├── services.py            # create_invite, accept_invite, change_role
    │   ├── admin.py               # TenantAdminMixin
    │   └── templates/accounts/
    │
    ├── tenants/                   # Church, Plan, Domain, TenantMiddleware
    │   ├── models.py              # Church(TenantMixin), Plan, Domain
    │   ├── middleware.py          # TenantMiddleware (resolve subdomain → schema)
    │   ├── views.py
    │   ├── services.py            # create_church_with_admin
    │   ├── signals.py             # Cria schema on Church.create
    │   ├── admin.py
    │   └── templates/tenants/
    │
    ├── people/
    │   ├── models.py              # Person (consent_given_at)
    │   ├── views.py               # Todas com TenantRequiredMixin
    │   ├── services.py            # create_person, import_csv, anonymize_person, export_person_data
    │   ├── signals.py             # AuditLog em post_save/post_delete
    │   ├── forms.py
    │   ├── urls.py
    │   ├── admin.py               # TenantAdminMixin
    │   └── templates/people/
    │
    ├── communities/
    │   └── (mesma estrutura)
    │
    ├── ministries/
    │   └── (mesma estrutura)
    │
    ├── gatherings/                # Gathering + Attendance
    │   ├── models.py
    │   ├── services.py            # mark_attendance_bulk (update_or_create)
    │   ├── signals.py
    │   └── (resto)
    │
    ├── schedules/                 # Schedule + ScheduleConflictApproval
    │   ├── models.py
    │   ├── services.py            # create_schedule, detect_conflict, approve_exception
    │   └── (resto)
    │
    ├── files/                     # FileAsset, upload/download seguros
    │   ├── models.py
    │   ├── services.py            # upload_file, generate_signed_url
    │   ├── views.py               # Download view com permissão
    │   └── (resto)
    │
    └── dashboard/
        ├── views.py
        ├── services.py            # church_metrics
        └── templates/dashboard/

├── templates/                     # Base templates compartilhados
│   ├── base.html
│   ├── components/                # navbar, sidebar, modal, table, card, badge, pagination, form
│   └── partials/                  # Fragments HTMX
│
├── static/
│   ├── css/
│   ├── js/
│   └── img/
│
└── media/                         # Uploads (volume separado em prod)
```

---

## 3. Princípios Arquiteturais

| ID | Princípio | Aplicação |
|---|---|---|
| P-ARQ-01 | App-per-Bounded-Context | URLs, views, models, signals, templates e admin convivem na app. Cross-context só por FK string ou service. |
| P-ARQ-02 | Todo model herda de `BaseModel` | `created_at` e `updated_at` desde o início. Index em `created_at`. **Exceções:** models que herdam de `TenantMixin` (`Church`, que já define `created_at`) e tabelas-catálogo de plataforma (`Plan`) são isentos; `AuditLog`/`SecurityLog` também não herdam (têm `created_at` próprio e schema/índices específicos). |
| P-ARQ-03 | Login por email | `USERNAME_FIELD = 'email'` desde a primeira migração. Trocar User depois é proibido (AP-02). |
| P-ARQ-04 | Service Layer leve | Fluxos com >1 efeito vão em `services.py`. CBVs delegam. CRUD trivial não precisa de service. |
| P-ARQ-05 | Multi-tenant via django-tenants | Toda view tenant-scoped usa `TenantRequiredMixin`. |
| P-ARQ-06 | Signals em `signals.py` | Conectados em `apps.py.ready()`. Nunca em `models.py`. |
| P-ARQ-07 | Status com `TextChoices` | Não usar booleanos compostos para status (AP-03). |
| P-ARQ-08 | Permissões em três camadas | View, service e queryset. Frontend espelha; nunca é segurança. |
| P-ARQ-09 | Prevenção de N+1 | Toda listagem/detalhe que toca FK ou M2M usa `select_related` / `prefetch_related`. `nplusone` ligado em testes (`raise_in_dev=True`). PR com N+1 não passa no CI. |

---

## 4. Multi-Tenancy

### 4.1 Modelo

Schema-per-tenant via `django-tenants`. Cada igreja tem um schema PostgreSQL isolado.

### 4.2 Regras críticas

| ID | Regra |
|---|---|
| TENANT-01 | Schema-per-tenant. Nenhum tenant compartilha tabela operacional. |
| TENANT-02 | SSL wildcard `*.saasigreja.com` via Cloudflare. Nenhum tenant sem HTTPS. |
| TENANT-03 | Dois modelos, um código. `has_communities` controla menus/labels. |
| TENANT-04 | `User` é model público. Tenants usam `user_id IntegerField`, não FK para `User`. |
| TENANT-05 | Toda view autenticada usa `TenantRequiredMixin`. Django Admin padrão proibido em prod. |
| TENANT-06 | Testes percorrem todas as views autenticadas com dois tenants distintos. |
| TENANT-07 | Logs não contêm PII desnecessária. Sentry `before_send` sanitiza. |

### 4.3 Resolução de tenant

`TenantMiddleware` resolve uma vez por request:

1. Lê `Host: <slug>.saasigreja.com`.
2. Consulta `public.tenants_church WHERE slug=<slug>`.
3. Define `search_path TO tenant_<slug>, public`.
4. Coloca `request.tenant = Church(...)` para uso nas views.

---

## 5. Modelos

### 5.1 BaseModel

```python
# apps/core/models.py
class BaseModel(models.Model):
    """Base abstrata. Auditoria temporal não é opcional."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ('-created_at',)
```

### 5.2 User, Invite, PlatformAdmin e SupportAccess (schema `public`)

```python
# apps/accounts/models.py
from django.contrib.postgres.fields import ArrayField

class User(AbstractUser):
    """Usuário customizado. Login por email. Pertence a uma única Church."""
    username = None
    email = models.EmailField(unique=True, db_index=True)
    church = models.ForeignKey(
        'tenants.Church',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    class Role(models.TextChoices):
        PASTOR = 'pastor', 'Lider Principal'
        SECRETARY = 'secretary', 'Secretario'  # OD-019: admin sem financeiro
        LEADER = 'leader', 'Lider'  # comunidade E ministerio (diferenca = vinculo)
        TREASURER = 'treasurer', 'Tesoureiro'
        MEMBER = 'member', 'Membro'

    # Multi-role: lista de papéis. Permissões = união. Exemplo: ['treasurer', 'leader'].
    roles = ArrayField(
        models.CharField(max_length=20, choices=Role.choices),
        default=list,
        blank=True,
        help_text='Lista de papeis. Permissoes sao a uniao das permissoes de cada papel.',
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = UserManager()

    def has_any_role(self, *roles):
        """True se o usuario tem qualquer um dos papeis listados."""
        return bool(set(roles) & set(self.roles))

    def has_all_roles(self, *roles):
        """True se o usuario tem todos os papeis listados."""
        return set(roles).issubset(set(self.roles))


class Invite(BaseModel):
    """Convite para novo usuário se juntar à igreja. Pode atribuir múltiplas roles."""
    church = models.ForeignKey('tenants.Church', on_delete=models.CASCADE)
    email = models.EmailField()
    roles = ArrayField(
        models.CharField(max_length=20, choices=User.Role.choices),
        default=list,
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    invited_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='invites_sent',
    )
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('church', 'email')


class PlatformAdmin(BaseModel):
    """Operador da plataforma. Separado de User comum. MFA obrigatório."""
    user = models.OneToOneField('User', on_delete=models.CASCADE, related_name='platform_admin')
    is_active = models.BooleanField(default=True)


class SupportAccess(BaseModel):
    """Acesso temporário de Platform Admin a um tenant para suporte.

    Sem SupportAccess ativo, middleware bloqueia Platform Admin em qualquer URL do tenant.
    Toda ação durante o acesso é auditada em AuditLog + SecurityLog.
    """
    admin = models.ForeignKey(PlatformAdmin, on_delete=models.CASCADE)
    church = models.ForeignKey('tenants.Church', on_delete=models.CASCADE)
    justification = models.TextField(help_text='Motivo do suporte (ticket, contato, etc.)')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(help_text='Acesso expira automaticamente em 4 horas')

    class Meta:
        indexes = [models.Index(fields=['church', 'ended_at', 'expires_at'])]

    @property
    def is_active(self):
        from django.utils import timezone
        now = timezone.now()
        return self.ended_at is None and self.expires_at > now
```

**Regras críticas de User/Invite:**

- `User.email` é único globalmente.
- Um `User` pertence a **uma única `Church`** (`church` FK simples, não M2M).
- **Migração entre igrejas não é suportada.** Para mudar de igreja, o usuário deve ser excluído na igreja antiga e recriado via novo convite na igreja nova.
- `User.roles` é lista. Permissões = união das permissões de cada role. Exemplo: usuário com `['treasurer', 'leader']` tem acesso financeiro **+** escopo de líder.
- Verificação de papel sempre via `user.has_any_role('pastor', 'leader')`, nunca `user.role == ...`.

### 5.3 Church e Plan (schema `public`)

```python
# apps/tenants/models.py
class Church(TenantMixin):
    """Tenant principal. Cada igreja = 1 schema PostgreSQL."""
    name = models.CharField(max_length=120)
    slug = models.CharField(max_length=60, unique=True)
    leader_title = models.CharField(
        max_length=40,
        default='Pastor',
        help_text='Titulo do lider principal (Pastor, Padre, Reverendo, etc.)',
    )
    has_communities = models.BooleanField(
        default=True,
        help_text='True = igreja em celulas. False = tradicional.',
    )
    accent_color = models.CharField(max_length=7, default='#864507')  # primary Oikonos
    hot_color = models.CharField(max_length=7, default='#F59A17')
    logo = models.ImageField(upload_to='logos/', null=True, blank=True)
    privacy_policy_url = models.URLField(blank=True, default='')

    class Plan(models.TextChoices):
        FREE = 'free', 'Gratis (ate 50 pessoas)'
        BASIC = 'basic', 'Basico (ate 200 pessoas)'
        PRO = 'pro', 'Profissional (pessoas ilimitadas)'

    plan = models.CharField(max_length=10, choices=Plan.choices, default=Plan.FREE)
    created_at = models.DateTimeField(auto_now_add=True)


class Plan(models.Model):
    """Plano do SaaS. Limites por plano."""
    PLAN_LIMITS = {
        'free': {'max_persons': 50, 'max_communities': 5},
        'basic': {'max_persons': 200, 'max_communities': 20},
        'pro': {'max_persons': 0, 'max_communities': 0},  # 0 = ilimitado
    }

    name = models.CharField(max_length=10, choices=Church.Plan.choices, primary_key=True)
    max_persons = models.PositiveIntegerField(default=50, help_text='0 = ilimitado')
    max_communities = models.PositiveIntegerField(default=5, help_text='0 = ilimitado')
    price_monthly = models.DecimalField(max_digits=8, decimal_places=2, default=0)
```

### 5.4 Person (schema `tenant`)

```python
# apps/people/models.py
class Person(BaseModel, AuditLogMixin):  # Sprint 3: + AuditLogMixin (audit auto)
    """Pessoa vinculada à igreja. LGPD-aware."""
    class Status(models.TextChoices):
        VISITOR = 'visitor', 'Visitante'
        CONGREGANT = 'congregant', 'Congregado'
        MEMBER = 'member', 'Membro'
        LEADER = 'leader', 'Lider'
        INACTIVE = 'inactive', 'Inativo'

    name = models.CharField(max_length=120)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.VISITOR,
        db_index=True,
    )
    # Sprint 3 / OD-019: vínculo OPCIONAL ao User (público) de um staff que loga
    # (líder/coordenador). NÃO é FK (TENANT-04: model de tenant nunca referencia
    # User por FK) — guarda o id do User, igual a AuditLog.user_id. NULL p/ membros.
    user_id = models.IntegerField(null=True, blank=True, db_index=True)
    community = models.ForeignKey(
        'communities.Community',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    ministries = models.ManyToManyField('ministries.Ministry', blank=True)
    consent_given_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Obrigatorio quando email ou telefone esta preenchido (LGPD)',
    )
    # Sprint 3: instante da anonimização (soft delete). Alimenta o purge físico
    # semanal após 30 dias (RN-006). NULL = pessoa ativa.
    anonymized_at = models.DateTimeField(null=True, blank=True, db_index=True)
    notes = models.TextField(blank=True, default='')
```

### 5.5 Community e Ministry (schema `tenant`)

```python
# apps/communities/models.py
class Community(BaseModel, AuditLogMixin):
    """Comunidade. Ativa apenas se Church.has_communities=True."""
    name = models.CharField(max_length=80)
    # OD-019 (2026-06-04): M2M, não FK — uma comunidade pode ter VÁRIOS líderes
    # (ex.: casal de líderes, líder + auxiliar). Cada líder é um Person cujo
    # `user_id` aponta ao User-staff. Escopo: ScopedToCommunityMixin -> leaders__user_id.
    leaders = models.ManyToManyField('people.Person', blank=True, related_name='communities_led')
    meeting_day = models.CharField(max_length=15, null=True, blank=True)
    meeting_time = models.TimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)


# apps/ministries/models.py
class Ministry(BaseModel, AuditLogMixin):
    """Ministério ou departamento."""
    name = models.CharField(max_length=80)
    # OD-019: M2M, não FK — vários coordenadores por ministério.
    coordinators = models.ManyToManyField('people.Person', blank=True, related_name='ministries_led')
    # Sprint 6.6 (RF-104/OD-029): meta de voluntários p/ card "Saúde do Ministério" (GAP = atuais × needed).
    volunteers_needed = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
```

### 5.6 Gathering e Attendance (schema `tenant`)

```python
# apps/gatherings/models.py
class Gathering(BaseModel, AuditLogMixin):
    """Encontro: culto, reunião de comunidade, evento ou reunião.

    Herda `AuditLogMixin`: create/update/delete auditados automaticamente (core
    signals). `created_by` (Sprint 4) guarda o `user_id` do criador (TENANT-04 —
    nunca FK para User) e habilita a trava "editar pelo criador" da §3.6 (Líder/
    Coordenador editam encontros que criaram, além do escopo por comunidade).
    """
    class Type(models.TextChoices):
        WORSHIP = 'worship', 'Culto'
        COMMUNITY = 'community', 'Reuniao de Comunidade'
        EVENT = 'event', 'Evento'
        MEETING = 'meeting', 'Reuniao'

    gathering_type = models.CharField(max_length=12, choices=Type.choices, db_index=True)
    title = models.CharField(max_length=120, null=True, blank=True)
    date = models.DateField(db_index=True)
    community = models.ForeignKey(
        'communities.Community',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    description = models.TextField(blank=True, default='')
    # user_id do criador (TENANT-04: id do User publico, NAO FK). Sprint 4 / §3.6.
    created_by = models.IntegerField(null=True, blank=True, db_index=True)


class Attendance(BaseModel):
    """Presença de uma Pessoa em um Encontro. Unique por (person, gathering).

    OD-020: `person` é `on_delete=SET_NULL` (RN-007) — o purge físico da Pessoa
    preserva a presença histórica do encontro (contagem mantida, identidade
    esquecida). `gathering` é CASCADE (apagar o encontro apaga sua lista).
    """
    person = models.ForeignKey(
        'people.Person', on_delete=models.SET_NULL, null=True, blank=True
    )
    gathering = models.ForeignKey(
        'Gathering',
        on_delete=models.CASCADE,
        related_name='attendances',
    )
    is_present = models.BooleanField(default=True)

    class Meta:
        unique_together = ('person', 'gathering')
```

### 5.7 Schedule (schema `tenant`)

```python
# apps/schedules/models.py
class Schedule(BaseModel, AuditLogMixin):
    """Escala de voluntário em ministério para um Gathering.

    Herda `AuditLogMixin` (create/update/delete auditados). `person` é
    `on_delete=SET_NULL` por RN-007 / OD-020 (FKs para Person preservam o
    histórico — corrige o CASCADE original desta spec, alinhando ao Attendance).
    """
    ministry = models.ForeignKey('ministries.Ministry', on_delete=models.CASCADE)
    person = models.ForeignKey(
        'people.Person', on_delete=models.SET_NULL, null=True, blank=True
    )
    gathering = models.ForeignKey('gatherings.Gathering', on_delete=models.CASCADE)
    role = models.CharField(max_length=60, blank=True, default='')
    notes = models.TextField(blank=True, default='')


class ScheduleConflictApproval(BaseModel):
    """Aprovação explícita de conflito de escala."""
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    approved_by_id = models.IntegerField(help_text='User.id do coordenador competente')
    justification = models.TextField()
    approved_at = models.DateTimeField(auto_now_add=True)
```

### 5.8 FileAsset (schema `tenant`)

```python
# apps/files/models.py
class FileAsset(BaseModel):
    """Metadados de arquivo. Arquivo real em storage."""
    filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=80)
    size_bytes = models.PositiveIntegerField()
    storage_path = models.CharField(max_length=500)
    uploaded_by_id = models.IntegerField()
    related_model = models.CharField(max_length=80, blank=True, default='')
    related_object_id = models.CharField(max_length=40, blank=True, default='')
```

### 5.9 AuditLog e SecurityLog (schema `tenant`)

```python
# apps/core/models.py
class AuditLog(models.Model):
    """Log de ações para conformidade LGPD. Vive no schema do tenant."""
    ACTION_CHOICES = [
        ('create', 'Criação'),
        ('read', 'Leitura'),
        ('update', 'Alteração'),
        ('delete', 'Exclusão'),
        ('export', 'Exportação'),
        ('anonymize', 'Anonimização'),
    ]
    user_id = models.IntegerField(null=True, help_text='User.id no schema public')
    tenant_id = models.CharField(
        max_length=60,
        db_index=True,
        help_text='Schema name do tenant, injetado pelo TenantMiddleware',
    )
    action = models.CharField(max_length=12, choices=ACTION_CHOICES, db_index=True)
    model_name = models.CharField(max_length=80)
    object_id = models.CharField(max_length=40)
    object_repr = models.CharField(max_length=200, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['tenant_id', 'action']),
            models.Index(fields=['tenant_id', 'model_name', 'object_id']),
        ]


class SecurityLog(models.Model):
    """Log de eventos de segurança (login, lockout, mudança de papel, etc.)."""
    EVENT_CHOICES = [
        ('login_success', 'Login bem-sucedido'),
        ('login_failure', 'Login falho'),
        ('lockout', 'Lockout (axes)'),
        ('password_reset_requested', 'Reset de senha solicitado'),
        ('password_reset_completed', 'Reset de senha concluido'),
        ('role_change', 'Mudanca de papel'),
        ('user_deactivated', 'Usuario desativado'),
        ('user_reactivated', 'Usuario reativado'),
        ('person_exported', 'Pessoa exportada'),
        ('person_anonymized', 'Pessoa anonimizada'),
        ('platform_admin_access', 'Acesso de Platform Admin'),
        ('sensitive_file_upload', 'Upload de arquivo sensivel'),
        ('sensitive_file_download', 'Download de arquivo sensivel'),
    ]
    user_id = models.IntegerField(null=True)
    tenant_id = models.CharField(max_length=60, db_index=True)
    event_type = models.CharField(max_length=40, choices=EVENT_CHOICES, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
```

#### 5.9.1 Placement de schema (crítico — TENANT-04 / RN-014)

`AuditLog` e `SecurityLog` **vivem no schema do tenant**, não no `public`. Isso é o que torna válido o uso de `user_id IntegerField` + `tenant_id CharField` (sem FK cross-schema). Regra de configuração obrigatória em `core/settings/base.py`:

- O app `core` precisa estar listado em **`TENANT_APPS`** (e também em `SHARED_APPS` se contiver elementos compartilhados), de modo que `AuditLog`/`SecurityLog` migrem para **cada schema de tenant**.
- `BaseModel` é abstrato (não gera tabela), então não exige decisão de schema.
- Mixins, middleware e validators do `core` **não são models** e não afetam a migração de schema.
- **Risco se violado:** se `AuditLog`/`SecurityLog` forem migrados apenas para `public`, perde-se o isolamento por tenant e quebra-se RN-014/TENANT-04 (RISK-001). Validado por `test_auditlog_no_cross_schema_fk` e `test_auditlog_scoped_by_tenant_id`.

> Se no momento da implementação ficar inevitável separar os models compartilhados dos models de tenant dentro do `core`, mover `AuditLog`/`SecurityLog` para um submódulo dedicado migrado via `TENANT_APPS` (decisão técnica a registrar na Sprint 2, não inferir).

---

## 6. Estilo de Código

| ID | Regra |
|---|---|
| STYLE-01 | PEP8 rigoroso. Aspas simples. Código em inglês, interface em pt-BR. Max line 88 (Black). |
| STYLE-02 | Class-Based Views por padrão. Lógica complexa em `services.py`. |
| STYLE-03 | Recursos nativos do Django primeiro. Adicionar dependência só se nativo não resolver. |
| STYLE-04 | HTMX para interatividade. Alpine.js apenas para micro-interações. Nunca SPA. |
| STYLE-05 | TailwindCSS com tokens Athos. Nenhuma cor hardcoded em template (AP-05). |

---

## 7. Segurança

| ID | Regra |
|---|---|
| SEC-01 | Isolamento multi-tenant inegociável. Toda view autenticada com `TenantRequiredMixin`. Django Admin padrão proibido em prod. |
| SEC-02 | Login por email; password policy (8+ chars, 1 número, 1 especial, diferente do email/nome); `django-axes` lockout (5 tentativas → 15 min). |
| SEC-03 | LGPD: `consent_given_at`, `anonymize_person()`, `export_person_data()`, `privacy_policy_url`, `AuditLog`. |
| SEC-04 | Headers obrigatórios em prod (ver bloco abaixo). |
| SEC-05 | Proteção contra OWASP Top 10. ModelForm com `fields` explícito (nunca `__all__`). |
| SEC-06 | Secrets via `python-decouple` ou env vars. `.env` em `.gitignore`. |
| SEC-07 | `pip-audit` + `safety check` no CI. Lock file com versões pinadas. |
| SEC-08 | MFA: opt-in TOTP (allauth) desde Sprint 2. Enforcement obrigatório na Sprint 7 via `MFARequiredForRoleMiddleware` (decisão OD-002), aplicado a usuários com `'pastor' in roles` e a `PlatformAdmin`. Posição na cadeia: **após** `AuthenticationMiddleware` e **após** `TenantMiddleware`; login sem MFA configurado redireciona para setup, login com MFA configurado exige TOTP. Não bloqueia `leader`/`treasurer`/`member`. |

### 7.1 Bloco obrigatório em `core/settings/prod.py`

```python
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
X_FRAME_OPTIONS = 'DENY'
```

#### Redirect de autenticação (`core/settings/base.py`)

`LoginRequiredMixin`/`TenantRequiredMixin` redirecionam o não-autenticado para
`LOGIN_URL`. O default do Django (`/accounts/login/`) **não existe** neste
projeto — as rotas de auth do allauth vivem sob o prefixo `contas/`. Por isso
`LOGIN_URL` aponta para a rota **nomeada** do allauth (resolvida via `reverse()`),
robusta a mudança de prefixo:

```python
LOGIN_URL = 'account_login'      # -> /contas/login/
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = 'account_login'
```

Regressão coberta por `test_list_users_requires_login` e
`test_login_url_resolves_to_allauth_named_route`.

---

## 8. Operacional

| ID | Regra |
|---|---|
| OPS-01 | Tasks pesadas em Celery. Importação CSV, geração de PDF, emails em massa. |
| OPS-02 | Idempotência em tasks e importações. CSV usa `import_id` para evitar duplicata. |
| OPS-03 | Docker multi-stage. EasyPanel para prod. SQLite proibido. |
| OPS-04 | Enforcement de limites do plano. `people/services.py.create_person` verifica `church.plan.max_persons` antes do save. |
| OPS-05 | Enforcement de consentimento LGPD na **camada de service** (`people/services.py.create_person` e `import_csv`): se `email` ou `phone` preenchido, `consent_given_at` é obrigatório (RN-005 / RNF-007). O `ModelForm` espelha a regra para UX, mas a barreira efetiva é o service — garante cobertura no caminho de importação CSV (RF-033), que **não** passa por `ModelForm`. Validado por `test_person_create_requires_consent_when_email_or_phone` e por teste equivalente no fluxo CSV. |

---

## 9. Anti-Padrões

| ID | Não fazer |
|---|---|
| AP-01 | Decorator de permissão sem `TenantRequiredMixin`. |
| AP-02 | Trocar `User` model depois do primeiro migrate. |
| AP-03 | Booleanos para status com mais de 2 estados. |
| AP-04 | Importação CSV síncrona com >500 linhas. |
| AP-05 | Cor hardcoded em template. |
| AP-06 | Duplicar models para os dois modelos de igreja. `Community` serve para ambos. |
| AP-07 | Refatorar no meio de uma sprint. |
| AP-08 | Prompt/PR sem referenciar PRD e design system. |
| AP-09 | View sem `TenantRequiredMixin`. |
| AP-10 | `ModelForm` com `fields = '__all__'`. |
| AP-11 | Dado pessoal sem `consent_given_at`. |
| AP-12 | Secret no código ou no `docker-compose.yml`. |
| AP-13 | SQLite em dev com django-tenants. Dev também usa PostgreSQL via docker-compose. |

---

## 10. Notas de Atenção

| ID | Tema | Decisão |
|---|---|---|
| A1 | soft vs hard delete LGPD | `anonymize_person()` faz soft delete imediato (status=INACTIVE + substitui PII). Celery Beat semanal faz purge físico. FKs para Person com `on_delete=SET_NULL`. |
| A2 | Attendance duplicado | `update_or_create` para `(person, gathering)`. Nunca criar duplicado. |
| A3 | Celery no MVP | **Decidido (OD-003): incluído desde Sprint 1.** Importação CSV, purge LGPD semanal e emails justificam. |
| A4 | WeasyPrint | Pesado (~200MB no Docker). MVP usa browser print (`@media print`). WeasyPrint entra na Fase 2 com relatórios complexos. |
| A5 | django-guardian | Overkill no MVP. Permissões hierárquicas (pastor > leader > coordinator > member) resolvem com mixins customizados em `User.roles`. Guardian disponível para per-object permissions no futuro. |
| A6 | Performance e paginação (RNF-011/RNF-021) | Toda listagem >25 registros usa paginação backend (`Paginator`); proibido carregar lista completa no template. Índices de consulta já declarados nos models (`status`, `date`, `created_at`, `tenant_id`+ação). Meta: listagem ≤500 registros <500ms. N+1 coberto por P-ARQ-09 (`nplusone`). |
| A7 | Acessibilidade (RNF-012/RNF-020) | WCAG AA: contraste via tokens Athos (nunca cor hardcoded — AP-05), `<label>` em todos os campos de form, navegação por teclado, foco visível. Mobile-first ≥360px. Meta Lighthouse mobile ≥90 nas telas principais. |

---

## 11. Design System

> **Implementação:** especificado aqui; **consolidado na Sprint 6.5** (`base.html` + `tailwind.config` compilado + biblioteca de componentes + estilização de 100% das telas). Até a 6.5, as telas operacionais usam markup mínimo pt-BR. Detalhe operacional em `docs/SPRINTS.md` (Sprint 6.5, princípios DS-01..08).

- **Referência viva:** `referencias/templates/igreja_saas_novo.html` (padrão de qualidade do app) + `referencias/` (direção da marca). **Marca ≠ tema:** a marca/landing é **Terracota & Âmbar fixa** (Fraunces/Inter); o **app** usa a Paleta Athos abaixo como **base neutra temável por igreja**.
- **Paleta do APP (premium — `referencias/templates/igreja_saas_personalizado.html`):** `#864507` (accent/primary), `#6A3302` (accent-2/hover), `#F59A17` (hot/âmbar), `#F8F1E8` (bg), `#F6EADC` (bg-soft), `#FFFEFA` (paper), `#161412` (ink), `#6C6259` (muted), `#EADFD2` (hairline), `#557A35` (success), `#B43A21` (danger). _(accent/hot são temáveis por igreja; o resto é base neutra.)_ **Premium:** body com radial-gradients quentes, `.card`/`.stat-pill` com sombras suaves, nav-rail com gradiente, hovers sutis, scrollbar fina.
- **Logo/identidade:** o **logo** (símbolo terracota + wordmark OIKONOS) vem da identidade `oikonos_identidade_6_partes/` (mark terracota `#C75A3B`); convive com a UI premium (paleta quente). Logo em `static/img/oikonos-logo.png`.
- **Tipografia (atualizada Sprint 6.6 / Athos v2):** **Inter** (corpo) + **Poppins** (display/títulos/marca) + `tabular-nums` em KPIs/números. _(Até a 6.5 o app usava Poppins para tudo; a v2 adota o pareamento Inter+Poppins confirmado pelo protótipo `igreja_saas_personalizado.html`.)_
- **Customização por tenant:** `Church.accent_color`/`hot_color` (defaults `#864507`/`#F59A17`) + `Church.logo` injetados em CSS variables no `<html>` — base neutra + acento por igreja.
- **Mobile-first (DS-03):** papéis operacionais (Líder/Coordenador/voluntário) priorizam mobile (bottom-nav); admin (Pastor/Secretário/Tesoureiro) cobrem desktop **e** mobile. Acessibilidade WCAG AA; Lighthouse mobile ≥ 90 (Sprint 6.5).
- **Shell Athos v2 (Sprint 6.6 · RF-105/OD-028):** o `app_base.html` migra do nav-rail **horizontal** para **sidebar vertical** escura (sticky ~244px). Re-skin de 100% das telas na **paleta Oikonos v2** (terra `#C2552C`/`#A8431F`, laranja `#E0892D`, âmbar `#EBB45C`, canvas `#F1EADF`), mantida temável por igreja. Home nova: calendário de agenda (`Gathering.date`), próximas programações e card "Saúde do Ministério" (GAP de voluntários, OD-029).

### 11.1 TailwindCSS — build (v4, CSS-first; **implementado Sprint 6.5/Bloco 1**)

Tailwind **v4** (config no CSS via `@theme`, sem `tailwind.config.js`). Compilado pelo **CLI standalone** via `pytailwindcss` (pip, **sem Node/node_modules**).

- **Fonte:** `static/src/input.css` (`@import 'tailwindcss'` + `@theme` com a Paleta Athos + `@source` apontando para `templates/` e `apps/`).
- **Acento temável por igreja:** no `@theme`, `--color-accent: var(--accent)` / `--color-hot: var(--hot)`; os defaults ficam em `:root` e são **sobrescritos por igreja** no `base.html` (`apps.core.context_processors.church_theme` lê `Church.accent_color`/`hot_color`/`logo`). A base neutra (bg/ink/paper/…) é fixa.
- **Build:** `uv run tailwindcss -i static/src/input.css -o static/css/app.css --minify` → `app.css` servido via `{% static %}` (compilado/purgado, não CDN → DS-05/Lighthouse).
- **Tipografia (Google Fonts — Athos v2):** **Inter** (corpo), **Poppins** (display/marca); `tabular-nums` nos números/KPIs.

```css
/* static/src/input.css (trecho) */
@import 'tailwindcss';
@source '../../templates';
@source '../../apps';
@theme {
  --color-accent: var(--accent);   /* Church.accent_color */
  --color-hot: var(--hot);         /* Church.hot_color */
  --color-bg: #efe7da; --color-paper: #fff; --color-ink: #161412; /* … base neutra fixa */
  --font-sans: 'Inter', system-ui, sans-serif;      /* corpo (Athos v2) */
  --font-display: 'Poppins', system-ui, sans-serif; /* display/marca */
}
:root { --accent: #864507; --hot: #f59a17; }  /* defaults premium; base.html sobrescreve por igreja */
```

---

## 12. Healthcheck e Observabilidade

### 12.1 Endpoints

| Endpoint | Auth | Verifica | Retorna |
|---|---|---|---|
| `/health/` | Não | Processo Django responsivo | 200 OK sempre que processo vivo |
| `/ready/` | Não | Postgres + Redis acessíveis | 200 OK se ambos OK; 503 caso contrário |

Implementação em `apps/core/views.py`:

```python
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET
import redis

@require_GET
def health(request):
    return JsonResponse({'status': 'ok'})

@require_GET
def ready(request):
    checks = {}
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        checks['postgres'] = 'ok'
    except Exception as exc:
        checks['postgres'] = f'fail: {exc!r}'
    try:
        r = redis.from_url(settings.REDIS_URL, socket_timeout=2)
        r.ping()
        checks['redis'] = 'ok'
    except Exception as exc:
        checks['redis'] = f'fail: {exc!r}'
    healthy = all(v == 'ok' for v in checks.values())
    return JsonResponse(checks, status=200 if healthy else 503)
```

Rotas registradas no schema `public` (acessíveis sem subdomínio de tenant).

### 12.2 CI/CD

**Decisão:** **GitHub Actions** (assume repositório em GitHub).

Pipeline mínimo (`.github/workflows/ci.yml`):
1. `uv sync`
2. `ruff check` + `black --check`
3. `pip-audit` + `safety check`
4. `pytest --cov=apps --cov-fail-under=<gate>` (com Postgres 15 + Redis em service containers)
5. Falha bloqueia merge na `main`

Deploy: EasyPanel detecta push em `main` e faz redeploy. Sem deploy automático em PR.

### 12.3 Logging

- Formatter sanitiza email/telefone via regex antes de gravar log.
- Sentry recebe via `before_send` (já configurado).
- `LOG_LEVEL=INFO` em prod; `DEBUG` apenas em dev.

---

## 13. Decisões Técnicas Pendentes

Ver [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md) para o tracking completo.

Decisões já fechadas:

- OD-002 (MFA): split opt-in Sprint 2 + enforcement Sprint 7.
- OD-003 (Celery): Celery + Redis no MVP desde Sprint 1.
- OD-003a / OD-007 (Storage): Cloudflare R2 (S3-compatible) desde Sprint 6.
- OD-004 (login de Membro): **fechada (2026-06-01)** — Membro existe apenas como `Person`, sem login no MVP. Mantém a app `accounts` enxuta; `member` permanece em `Role.choices` para evitar migração na Fase 2.
- OD-006 (VPS): Hostinger KVM 2 (8GB, 2 vCPU, 100GB NVMe).
- OD-012 (Email): Brevo free tier via `django-anymail`.
- OD-015 (CI/CD): **GitHub Actions** (Seção 12.2).
- OD-016 (RTO/RPO baseline beta): RTO 4h / RPO 24h, limitado pelo `pg_dump` diário (PRD §20.4).
- OD-017 (exclusão de tenant): **fechada (2026-06-01)** — igreja não é hard-deletável no MVP, apenas suspensa (RF-003). `on_delete=CASCADE` permanece no model, mas nenhum caminho de produto dispara delete de `Church`.
- OD-018 (enforcement LGPD `consent_given_at`): **fechada (2026-06-01)** — validação na camada de service (`create_person`/`import_csv`), espelhada no form. Ver §OPS-05.

Decisões **abertas com impacto direto em código** (não inferir — perguntar ao dono, G-05):

| OD | Impacto técnico | Onde toca |
|---|---|---|
| OD-010 | Retenção de logs (`AuditLog`/`SecurityLog`) — crescimento de tabela e purge | Models §5.9; futura task de purge/particionamento (Sprint 7) |
| OD-014 | Confirmação dupla na anonimização de Pessoa | UX de `anonymize_person` (Sprint 3) |
