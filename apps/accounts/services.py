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

from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.core.audit import log_security_event, record_audit

_VALID_ROLES = set(User.Role.values)


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
