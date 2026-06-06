from django.db import models


class BaseModel(models.Model):
    """Base abstrata. Auditoria temporal nao e opcional (P-ARQ-02)."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ('-created_at',)


class AuditLogMixin(models.Model):
    """Marca um model para auditoria automatica (create/update/delete).

    Mecanismo escolhido (judgment call): mixin de MODEL ABSTRATO sem campos. O
    fato de ser abstrato garante que NAO cria tabela nem migracao propria — e
    apenas um marcador de tipo. Os receivers em `apps.core.signals` detectam
    instancias via `isinstance(instance, AuditLogMixin)` no post_save/post_delete
    e chamam `record_audit(...)`. Manter a logica de auditoria nos signals (e nao
    em metodos sobrescritos de save/delete) respeita P-ARQ-06 (signals conectados
    no `ready()`, nunca em models.py) e cobre tambem deletes em lote/cascata.

    Uso: `class Person(AuditLogMixin, BaseModel): ...`. Nada mais e necessario;
    a auditoria passa a ser automatica. AuditLog/SecurityLog NAO herdam deste
    mixin (evita recursao — eles sao o destino da auditoria, nao a fonte).
    """

    class Meta:
        abstract = True


class AuditLog(models.Model):
    """Log de acoes para conformidade LGPD. Vive no schema do tenant."""

    ACTION_CHOICES = [
        ('create', 'Criacao'),
        ('read', 'Leitura'),
        ('update', 'Alteracao'),
        ('delete', 'Exclusao'),
        ('export', 'Exportacao'),
        ('anonymize', 'Anonimizacao'),
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

    def __str__(self):
        return f'{self.action} {self.model_name}#{self.object_id} ({self.tenant_id})'


class SecurityLog(models.Model):
    """Log de eventos de seguranca (login, lockout, mudanca de papel, etc.)."""

    EVENT_CHOICES = [
        ('login_success', 'Login bem-sucedido'),
        ('login_failure', 'Login falho'),
        ('lockout', 'Lockout (axes)'),
        ('password_reset_requested', 'Reset de senha solicitado'),
        ('password_reset_completed', 'Reset de senha concluido'),
        ('role_change', 'Mudanca de papel'),
        ('user_deactivated', 'Usuario desativado'),
        ('user_reactivated', 'Usuario reativado'),
        ('mfa_enabled', 'MFA ativado'),
        ('mfa_disabled', 'MFA desativado'),
        ('person_exported', 'Pessoa exportada'),
        ('person_anonymized', 'Pessoa anonimizada'),
        ('platform_admin_access', 'Acesso de Platform Admin'),
        ('support_access_granted', 'Acesso de suporte concedido'),
        ('support_access_revoked', 'Acesso de suporte revogado'),
        ('sensitive_file_upload', 'Upload de arquivo sensivel'),
        ('sensitive_file_download', 'Download de arquivo sensivel'),
        ('schedule_exception_approved', 'Excecao de conflito de escala aprovada'),
        ('volunteer_schedule_access', 'Acesso de voluntario a escala (magic-link)'),
    ]
    user_id = models.IntegerField(null=True)
    tenant_id = models.CharField(max_length=60, db_index=True)
    event_type = models.CharField(max_length=40, choices=EVENT_CHOICES, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.event_type} ({self.tenant_id})'
