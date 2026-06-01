import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.core.models import BaseModel


class UserManager(BaseUserManager):
    """Manager para login por email (username removido, USERNAME_FIELD='email')."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('O email e obrigatorio.')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser precisa de is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser precisa de is_superuser=True.')
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Usuario customizado. Login por email. Pertence a uma unica Church."""

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
        LEADER = 'leader', 'Lider'
        TREASURER = 'treasurer', 'Tesoureiro'
        MEMBER = 'member', 'Membro'

    # Multi-role: lista de papeis. Permissoes = uniao. Exemplo: ['treasurer', 'leader'].
    roles = ArrayField(
        models.CharField(max_length=20, choices=Role.choices),
        default=list,
        blank=True,
        help_text=(
            'Lista de papeis. Permissoes sao a uniao das permissoes de cada papel.'
        ),
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
    """Convite para novo usuario se juntar a igreja. Pode atribuir multiplas roles."""

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
    """Operador da plataforma. Separado de User comum. MFA obrigatorio."""

    user = models.OneToOneField(
        'User',
        on_delete=models.CASCADE,
        related_name='platform_admin',
    )
    is_active = models.BooleanField(default=True)


class SupportAccess(BaseModel):
    """Acesso temporario de Platform Admin a um tenant para suporte.

    Sem SupportAccess ativo, middleware bloqueia Platform Admin em qualquer URL
    do tenant. Toda acao durante o acesso e auditada em AuditLog + SecurityLog.
    """

    admin = models.ForeignKey(PlatformAdmin, on_delete=models.CASCADE)
    church = models.ForeignKey('tenants.Church', on_delete=models.CASCADE)
    justification = models.TextField(
        help_text='Motivo do suporte (ticket, contato, etc.)'
    )
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(
        help_text='Acesso expira automaticamente em 4 horas'
    )

    class Meta:
        indexes = [models.Index(fields=['church', 'ended_at', 'expires_at'])]

    @property
    def is_active(self):
        from django.utils import timezone

        now = timezone.now()
        return self.ended_at is None and self.expires_at > now
