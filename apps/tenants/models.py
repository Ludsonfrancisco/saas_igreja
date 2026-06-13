from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django_tenants.models import DomainMixin, TenantMixin


class Church(TenantMixin):
    """Tenant principal. Cada igreja = 1 schema PostgreSQL."""

    auto_create_schema = True

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
    # F2 / OD-032 / RF-126-127: rótulos configuráveis por igreja (só UI; o model segue
    # Community/Ministry). Espelha `leader_title`. A UI lê estes termos via o context
    # processor `church_terms` + a tag {% term %}. Ex.: "Célula"/"Departamento".
    community_label = models.CharField(
        max_length=30,
        default='Comunidade',
        help_text='Como esta igreja chama a Comunidade (ex.: Celula, Grupo, GC).',
    )
    community_label_plural = models.CharField(max_length=30, default='Comunidades')
    ministry_label = models.CharField(
        max_length=30,
        default='Ministério',
        help_text='Como esta igreja chama o Ministerio (ex.: Departamento, Equipe).',
    )
    ministry_label_plural = models.CharField(max_length=30, default='Ministérios')
    # Escalas v2 (RN-023 / OD-031): dia em que abrem as pendências de escala do mês
    # SEGUINTE. Antes desse dia, eventos do próximo mês não geram pendência. Faixa
    # 1–28 evita meses curtos (fevereiro). O mês corrente está sempre na janela.
    schedule_pending_open_day = models.PositiveSmallIntegerField(
        default=25,
        validators=[MinValueValidator(1), MaxValueValidator(28)],
        help_text='Dia em que abrem as pendencias de escala do mes seguinte (1-28).',
    )
    # Defaults = cores da marca Oikonos (primary/âmbar). Cada igreja customiza.
    accent_color = models.CharField(max_length=7, default='#864507')
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

    name = models.CharField(
        max_length=10,
        choices=Church.Plan.choices,
        primary_key=True,
    )
    max_persons = models.PositiveIntegerField(default=50, help_text='0 = ilimitado')
    max_communities = models.PositiveIntegerField(default=5, help_text='0 = ilimitado')
    price_monthly = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    def __str__(self):
        return self.get_name_display()


class Domain(DomainMixin):
    """Dominio/subdominio que mapeia para uma Church (django-tenants)."""

    pass
