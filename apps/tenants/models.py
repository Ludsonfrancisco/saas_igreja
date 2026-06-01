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
    accent_color = models.CharField(max_length=7, default='#7C3F06')
    hot_color = models.CharField(max_length=7, default='#FF9C1A')
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
