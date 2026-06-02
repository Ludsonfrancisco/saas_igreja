"""Helpers reutilizaveis de auditoria (AuditLog) e seguranca (SecurityLog).

Este modulo concentra as duas portas de entrada para gravar logs de auditoria,
de forma que views, services, signals e (futuramente) os fluxos de auth chamem
sempre o mesmo caminho consistente:

- `record_audit(...)`     -> grava um AuditLog (acoes sobre dados: create/read/
                              update/delete/export/anonymize) no schema do tenant.
- `log_security_event(...)` -> grava um SecurityLog (eventos de seguranca: login,
                              lockout, mudanca de papel, SupportAccess, etc.).

Invariantes (TECH_SPEC §5.9 / §12.3 / RN-014 / TENANT-04/07):

1. tenant_id vem de `connection.schema_name` (django-tenants). Nao ha FK
   cross-schema; o vinculo ao usuario e `user_id` (IntegerField puro do public).
2. Guarda de schema public: AuditLog/SecurityLog vivem APENAS nos schemas de
   tenant. Se a operacao estiver acontecendo no schema public (ex.: criacao de
   User), nao ha tabela de log la — retornamos None silenciosamente em vez de
   estourar `relation does not exist`.
3. Nunca levantar: auditoria e transversal e NAO pode quebrar a operacao de
   negocio. Qualquer falha e capturada e logada como warning, sem PII.
4. Sem PII no log de aplicacao (TENANT-07): nao registramos email/telefone nas
   mensagens de warning; apenas o nome do model/evento.
"""

import logging

from django.db import connection
from django_tenants.utils import get_public_schema_name

from apps.core.middleware import get_current_ip, get_current_user_id

logger = logging.getLogger(__name__)


def _is_public_schema():
    """True quando a operacao corrente esta no schema public (sem tenant)."""
    return connection.schema_name == get_public_schema_name()


def record_audit(
    *,
    action,
    instance=None,
    model_name=None,
    object_id=None,
    object_repr='',
    changes=None,
    user_id=None,
    ip_address=None,
):
    """Grava um AuditLog no schema do tenant atual. Retorna a instancia ou None.

    Acoes auditaveis (LGPD): create/read/update/delete/export/anonymize. O
    tenant_id e derivado de `connection.schema_name`; user_id/ip caem para o
    contexto do request (thread-local) quando nao informados.

    Quando `instance` e passado, model_name/object_id/object_repr sao derivados
    dele (a menos que explicitamente sobrepostos).

    Retenção/trilha: a linha vive no schema do tenant e e parte da trilha de
    auditoria LGPD; nao e apagada por operacoes de negocio.

    Guarda de schema public: se estamos no public (ex.: criacao de User), nao ha
    tabela de log de tenant — retorna None sem gravar. Nunca levanta excecao.
    """
    try:
        if _is_public_schema():
            return None

        if instance is not None:
            model_name = model_name or instance.__class__.__name__
            if object_id is None and instance.pk is not None:
                object_id = str(instance.pk)
            if not object_repr:
                object_repr = str(instance)[:200]

        # Import tardio: evita import circular (models -> ... -> audit) e mantem
        # o modulo importavel mesmo antes do app registry estar pronto.
        from apps.core.models import AuditLog

        return AuditLog.objects.create(
            tenant_id=connection.schema_name,
            user_id=user_id if user_id is not None else get_current_user_id(),
            action=action,
            model_name=model_name or '',
            object_id=str(object_id) if object_id is not None else '',
            object_repr=object_repr or '',
            changes=changes or {},
            ip_address=ip_address if ip_address is not None else get_current_ip(),
        )
    except Exception:
        # Sem PII (TENANT-07): so o action/model, nunca o conteudo do objeto.
        logger.warning(
            'Falha ao gravar AuditLog (action=%s, model=%s)',
            action,
            model_name,
            exc_info=True,
        )
        return None


def log_security_event(
    *,
    event_type,
    user_id=None,
    payload=None,
    ip_address=None,
):
    """Grava um SecurityLog no schema do tenant atual. Retorna a instancia ou None.

    Eventos de seguranca: login_success/failure, lockout, password_reset_*,
    role_change, user_(de)activated, person_exported/anonymized,
    platform_admin_access, sensitive_file_upload/download.

    IMPORTANTE (caller): `payload` deve vir JA SANITIZADO. NUNCA passar senha,
    token de reset, codigo TOTP/backup, ou outro segredo cru — apenas metadados
    nao-sensiveis (ex.: {'roles_added': [...]}, {'reason': '...'}). Idem PII:
    evite email/telefone crus no payload (TENANT-07 / §12.3).

    Mesma guarda de schema public e mesmo comportamento never-raise de
    `record_audit`.
    """
    try:
        if _is_public_schema():
            return None

        from apps.core.models import SecurityLog

        return SecurityLog.objects.create(
            tenant_id=connection.schema_name,
            user_id=user_id if user_id is not None else get_current_user_id(),
            event_type=event_type,
            payload=payload or {},
            ip_address=ip_address if ip_address is not None else get_current_ip(),
        )
    except Exception:
        logger.warning(
            'Falha ao gravar SecurityLog (event_type=%s)',
            event_type,
            exc_info=True,
        )
        return None
