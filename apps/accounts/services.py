"""Service layer da autorizacao multi-role (RN-003a / RN-004 / P-ARQ-04, P-ARQ-08).

Camada de servico LEVE (P-ARQ-04): regras de negocio de papel/estado de conta
que NAO cabem na view nem no model. Cada operacao sensivel grava trilha dupla
via os helpers never-raise de `apps.core.audit`:

- `record_audit(action='update', ...)`  -> AuditLog (dados alterados).
- `log_security_event(event_type=...)`   -> SecurityLog (evento de seguranca).

Invariante de seguranca (RN-004 — "ultimo Pastor"): uma igreja NUNCA pode ficar
sem nenhum Pastor ativo. A guarda e aplicada em `change_roles` (remocao de
papel) e — por decisao conservadora (CLAUDE.md: "regra mais conservadora em
seguranca") — TAMBEM em `deactivate_user`, ja que desativar o ultimo Pastor
deixaria a igreja sem comando de fato. O SPRINTS.md amarra RN-004 explicitamente
apenas a `change_roles`; a extensao a `deactivate_user` esta sinalizada na
entrega para revisao do dono.

Multi-role: a verificacao de Pastor e sempre `'pastor' in roles` (RN-003a),
nunca igualdade de campo unico. PII NUNCA entra no payload de log (TENANT-07):
apenas ids e listas de papeis (papeis nao sao PII).

`actor` (quem executa a acao) e opcional. Os helpers ja resolvem `user_id` a
partir do thread-local do request; mas quando ha `actor` explicito (ex.: chamadas
fora de um request HTTP, como testes ou tasks), passamos `user_id=actor.id` ao
logar para que a trilha registre o AUTOR — distinto do `target_user_id` no
payload, que identifica o usuario AFETADO.
"""

import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError
from django.utils import timezone
from django_tenants.utils import schema_context

from apps.accounts.models import Invite, SupportAccess, User
from apps.core.audit import log_security_event, record_audit

_VALID_ROLES = set(User.Role.values)

# Janela de validade do convite (RN-003a). Apos isso, o aceite e recusado.
_INVITE_TTL = timedelta(days=7)

# Janela de validade do SupportAccess (RN-015 / RISK-009). Acesso de suporte
# expira automaticamente em 4 horas (alem de poder ser revogado antes).
_SUPPORT_ACCESS_TTL = timedelta(hours=4)


def _actor_id(actor):
    """Id do autor da acao para a trilha, ou None (cai para o thread-local)."""
    return actor.id if actor is not None else None


def _has_other_active_pastor(*, church, excluding_user_id):
    """True se EXISTE outro Pastor ativo na mesma igreja (RN-004).

    Considera multi-role: filtra por `roles contains ['pastor']`, nao igualdade.
    Exclui o proprio usuario sob avaliacao. Igreja nula (User sem church) nao tem
    "outro Pastor" a preservar — retorna False e a guarda nao deixa esvaziar.
    """
    if church is None:
        return False
    return (
        User.objects.filter(church=church, is_active=True, roles__contains=['pastor'])
        .exclude(id=excluding_user_id)
        .exists()
    )


def change_roles(*, user, new_roles, actor=None):
    """Altera os papeis de `user` para `new_roles`, com trilha de auditoria.

    Regras:
    - `new_roles` deve ser subconjunto das choices validas (User.Role) — senao
      `ValidationError`.
    - RN-004 (ultimo Pastor): se a operacao REMOVE 'pastor' de quem o tinha e nao
      ha NENHUM outro Pastor ativo na mesma igreja, rejeita com `ValidationError`.
      A verificacao e por `'pastor' in roles` (multi-role), nao igualdade.

    Em sucesso, grava AuditLog(action='update', changes={'roles': [antes, depois]})
    e SecurityLog(event_type='role_change', payload com ids e listas de papeis).
    Retorna o `user` atualizado.
    """
    new_roles = list(new_roles)
    invalid = set(new_roles) - _VALID_ROLES
    if invalid:
        raise ValidationError(f'Papeis invalidos: {", ".join(sorted(invalid))}.')

    roles_before = list(user.roles)
    removing_pastor = 'pastor' in roles_before and 'pastor' not in new_roles
    if removing_pastor and not _has_other_active_pastor(
        church=user.church, excluding_user_id=user.id
    ):
        raise ValidationError('Nao e possivel remover o ultimo Pastor da igreja.')

    user.roles = new_roles
    user.save(update_fields=['roles'])

    record_audit(
        action='update',
        instance=user,
        changes={'roles': [roles_before, new_roles]},
        user_id=_actor_id(actor),
    )
    log_security_event(
        event_type='role_change',
        user_id=_actor_id(actor),
        payload={
            'target_user_id': user.id,
            'roles_before': roles_before,
            'roles_after': new_roles,
        },
    )
    return user


def deactivate_user(*, user, actor=None):
    """Desativa `user` (is_active=False), com guarda RN-004 e trilha de auditoria.

    Guarda conservadora (extensao de RN-004): se `user` e o ULTIMO Pastor ativo da
    igreja, a desativacao e rejeitada com `ValidationError` — desativar deixaria a
    igreja sem nenhum Pastor ativo. (O SPRINTS.md amarra RN-004 apenas a
    change_roles; ver docstring do modulo.)

    Em sucesso, grava SecurityLog(event_type='user_deactivated') e
    AuditLog(action='update', changes={'is_active': [True, False]}). Retorna o
    `user`. Idempotente-amigavel: se ja inativo, apenas re-grava o estado.
    """
    is_last_active_pastor = (
        'pastor' in user.roles
        and user.is_active
        and not _has_other_active_pastor(church=user.church, excluding_user_id=user.id)
    )
    if is_last_active_pastor:
        raise ValidationError('Nao e possivel desativar o ultimo Pastor da igreja.')

    was_active = user.is_active
    user.is_active = False
    user.save(update_fields=['is_active'])

    record_audit(
        action='update',
        instance=user,
        changes={'is_active': [was_active, False]},
        user_id=_actor_id(actor),
    )
    log_security_event(
        event_type='user_deactivated',
        user_id=_actor_id(actor),
        payload={'target_user_id': user.id},
    )
    return user


def reactivate_user(*, user, actor=None):
    """Reativa `user` (is_active=True), com trilha de auditoria.

    Grava SecurityLog(event_type='user_reactivated') e
    AuditLog(action='update', changes={'is_active': [False, True]}). Retorna o
    `user`.
    """
    was_active = user.is_active
    user.is_active = True
    user.save(update_fields=['is_active'])

    record_audit(
        action='update',
        instance=user,
        changes={'is_active': [was_active, True]},
        user_id=_actor_id(actor),
    )
    log_security_event(
        event_type='user_reactivated',
        user_id=_actor_id(actor),
        payload={'target_user_id': user.id},
    )
    return user


# --- Convites (Frente 4 — RN-003a) -----------------------------------------
#
# O TOKEN do convite e um segredo: ele autoriza a criacao de uma conta. Por isso
# NUNCA entra em AuditLog/SecurityLog (changes/object_repr/payload) — aparece
# SOMENTE no corpo do email enviado ao convidado (TENANT-07 / §12.3). As funcoes
# abaixo seguem o mesmo padrao das demais deste modulo: `*` keyword-only,
# trilha de auditoria via helpers never-raise e `_actor_id` para registrar o
# autor da acao.


def _send_invite_email(invite, accept_url):
    """Envia o email de convite com o link de aceite (unico lugar com o token).

    Em dev o backend e o console (settings.dev); em prod, Brevo via anymail. O
    `from_email=None` faz o Django usar `DEFAULT_FROM_EMAIL`. `fail_silently=False`
    para que falha de envio seja visivel ao chamador (a view trata e avisa).
    """
    message = (
        'Voce foi convidado para participar de uma igreja no SaaS Igreja.\n\n'
        'Para criar sua conta e definir sua senha, acesse o link abaixo:\n\n'
        f'{accept_url}\n\n'
        'Este convite expira em 7 dias. Se voce nao esperava este convite, '
        'apenas ignore esta mensagem.'
    )
    send_mail(
        subject='Voce foi convidado para o SaaS Igreja',
        message=message,
        from_email=None,
        recipient_list=[invite.email],
        fail_silently=False,
    )


def create_invite(*, church, email, roles, invited_by, build_accept_url):
    """Cria um convite e envia o email com o link de aceite (RN-003a).

    Regras:
    - `roles` deve ser um subconjunto NAO VAZIO das choices validas (User.Role);
      caso contrario `ValidationError`.
    - email e normalizado (strip + lower) antes de persistir/checar unicidade.
    - `unique_together (church, email)` impede convite duplicado para o mesmo
      email na mesma igreja: a colisao vira `ValidationError` amigavel.

    `build_accept_url` e um callable `(token) -> str` (a view passa um lambda com
    `request.build_absolute_uri`), mantendo o service desacoplado de HTTP.

    Em sucesso, grava AuditLog(action='create') SEM o token e retorna o Invite.
    """
    roles = list(roles)
    invalid = set(roles) - _VALID_ROLES
    if not roles or invalid:
        raise ValidationError('Selecione ao menos um papel valido para o convite.')

    email = email.strip().lower()

    try:
        invite = Invite.objects.create(
            church=church,
            email=email,
            roles=roles,
            invited_by=invited_by,
            expires_at=timezone.now() + _INVITE_TTL,
        )
    except IntegrityError as exc:
        raise ValidationError(
            'Ja existe um convite para este email nesta igreja.'
        ) from exc

    accept_url = build_accept_url(invite.token)
    _send_invite_email(invite, accept_url)

    record_audit(action='create', instance=invite, user_id=invited_by.id)
    return invite


def accept_invite(
    *, token, password, first_name='', last_name='', expected_church=None
):
    """Aceita um convite: cria o usuario e marca o convite como usado (RN-003a).

    Defesas:
    - token inexistente -> `ValidationError('Convite invalido.')` (mesma mensagem
      generica para nao revelar existencia de tokens).
    - `expected_church` (a view passa `request.tenant`): se o convite e de OUTRA
      igreja, recusa como invalido — barreira cross-tenant (RISK-001).
    - single-use: convite ja aceito -> recusa.
    - expiracao: `expires_at` no passado -> recusa.

    O usuario criado herda exatamente as `roles` do convite (multi-role) e fica
    vinculado a `invite.church`. O proprio usuario e o autor do aceite, entao a
    trilha registra `user_id=user.id`.
    """
    try:
        invite = Invite.objects.select_related('church').get(token=token)
    except Invite.DoesNotExist as exc:
        raise ValidationError('Convite invalido.') from exc

    if expected_church is not None and invite.church_id != expected_church.id:
        raise ValidationError('Convite invalido.')
    if invite.accepted_at is not None:
        raise ValidationError('Este convite ja foi utilizado.')
    if invite.expires_at < timezone.now():
        raise ValidationError('Este convite expirou.')

    user = User.objects.create_user(
        email=invite.email,
        password=password,
        roles=list(invite.roles),
        church=invite.church,
        first_name=first_name,
        last_name=last_name,
    )

    invite.accepted_at = timezone.now()
    invite.save(update_fields=['accepted_at'])

    record_audit(action='create', instance=user, user_id=user.id)
    return user


def resend_invite(*, invite, actor=None, build_accept_url):
    """Regenera o token e reenvia o email de um convite pendente (RN-003a).

    Regenerar o token INVALIDA o link antigo (single-use por construcao: so o
    ultimo token vale). Convite ja aceito nao pode ser reenviado.

    Em sucesso, grava AuditLog(action='update', changes={'resent': True}) — sem
    token — e retorna o Invite atualizado.
    """
    if invite.accepted_at is not None:
        raise ValidationError('Convite ja aceito nao pode ser reenviado.')

    invite.token = uuid.uuid4()
    invite.expires_at = timezone.now() + _INVITE_TTL
    invite.save(update_fields=['token', 'expires_at'])

    accept_url = build_accept_url(invite.token)
    _send_invite_email(invite, accept_url)

    record_audit(
        action='update',
        instance=invite,
        changes={'resent': True},
        user_id=_actor_id(actor),
    )
    return invite


def cancel_invite(*, invite, actor=None):
    """Cancela (hard delete) um convite pendente (RN-003a).

    A auditoria e gravada ANTES do delete para capturar object_id/object_repr do
    convite (apos o delete, a pk se perde). Sem token na trilha. Retorna None.
    """
    record_audit(action='delete', instance=invite, user_id=_actor_id(actor))
    invite.delete()
    return None


# --- SupportAccess (Frente 5 — RN-015 / RISK-009) --------------------------
#
# Grant/revoke de SupportAccess acontecem na AREA DE PLATAFORMA, servida no
# schema `public`. Mas o SecurityLog SOBRE o acesso a uma igreja Y pertence ao
# SecurityLog da igreja Y (que so existe no schema do tenant). Por isso gravamos
# o evento DENTRO do schema da igreja-alvo via `schema_context(...)`: chamar
# `log_security_event` direto no public cairia na guarda de schema public do
# helper e NADA seria gravado.
#
# A `justification` pode conter dados de ticket/contato — NUNCA entra no payload
# do log (TENANT-07); fica apenas no model SupportAccess.


def grant_support_access(*, admin, church, justification):
    """Concede SupportAccess de um Platform Admin a uma igreja por 4h (RN-015).

    RISK-009: Platform Admin so acessa um tenant com SupportAccess vigente. Este
    service cria o registro com `expires_at = now + 4h` e audita a concessao no
    SecurityLog DA IGREJA-ALVO (schema do tenant), via `schema_context`.

    Gate §215: o admin precisa ter MFA TOTP ativo na propria conta; senao
    `ValidationError` (nada e criado). Validacao: `justification` nao pode ser
    vazia (ticket/motivo obrigatorio) — senao `ValidationError`. Retorna o
    `SupportAccess` criado.

    Retenção/trilha: o evento `support_access_granted` vive no SecurityLog do
    tenant; a `justification` fica SO no model (fora do log — pode conter PII de
    ticket, TENANT-07).
    """
    # Gate §215 (RISK-009): o PlatformAdmin so concede SupportAccess se ele
    # proprio tiver MFA TOTP ativo. `is_mfa_enabled` consulta o Authenticator
    # (model SHARED, no public) do usuario do admin; grant roda no public, entao o
    # acesso e direto, sem `schema_context`. O enforcement AMPLO (exigir MFA em
    # cada USO do acesso, via middleware) e Sprint 7 — aqui e so na concessao.
    from allauth.mfa.models import Authenticator
    from allauth.mfa.utils import is_mfa_enabled

    if not is_mfa_enabled(admin.user, [Authenticator.Type.TOTP]):
        raise ValidationError(
            'Ative a verificacao em duas etapas (MFA) na sua conta antes de '
            'conceder acesso de suporte.'
        )

    if not justification or not justification.strip():
        raise ValidationError(
            'Justificativa e obrigatoria para conceder acesso de suporte.'
        )

    support_access = SupportAccess.objects.create(
        admin=admin,
        church=church,
        justification=justification,
        expires_at=timezone.now() + _SUPPORT_ACCESS_TTL,
    )

    with schema_context(church.schema_name):
        log_security_event(
            event_type='support_access_granted',
            user_id=admin.user_id,
            payload={
                'support_access_id': support_access.id,
                'admin_id': admin.id,
                'expires_at': support_access.expires_at.isoformat(),
            },
        )
    return support_access


def revoke_support_access(*, support_access):
    """Revoga (encerra) um SupportAccess vigente (RN-015 / RISK-009).

    Marca `ended_at = now` e audita `support_access_revoked` no SecurityLog DA
    IGREJA-ALVO (schema do tenant), via `schema_context`. Idempotente: se o acesso
    ja estava encerrado (`ended_at` nao-nulo), retorna sem re-gravar nada.

    Retorna o proprio `support_access`.
    """
    if support_access.ended_at is not None:
        return support_access

    support_access.ended_at = timezone.now()
    support_access.save(update_fields=['ended_at'])

    with schema_context(support_access.church.schema_name):
        log_security_event(
            event_type='support_access_revoked',
            user_id=support_access.admin.user_id,
            payload={
                'support_access_id': support_access.id,
                'admin_id': support_access.admin_id,
            },
        )
    return support_access
