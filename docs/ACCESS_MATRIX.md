# ACCESS MATRIX — SaaS Igreja

> **Versão:** 1.0
> **Data:** 2026-05-27
> **Status:** Source of truth de autorização. Decisões abertas: ver [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md).

Matriz detalhada de permissões por módulo, ação e papel. Toda barreira efetiva é backend. Menu/template não é segurança.

---

## 1. Papéis

`User.roles` é uma **lista** (ArrayField). Permissões são a **união** das permissões de cada papel.

| Papel | Escopo | Onde vive |
|---|---|---|
| Platform Admin | Plataforma | `PlatformAdmin` (model separado); acesso a tenant exige `SupportAccess` ativo |
| Pastor / Admin da Igreja | Tenant inteiro | `'pastor' in user.roles` |
| Líder de Comunidade | Sua(s) comunidade(s) | `'leader' in user.roles` + comunidades onde é `Community.leader` |
| Coordenador de Ministério | Seu(s) ministério(s) | `'leader' in user.roles` + ministérios onde é `Ministry.coordinator` |
| Tesoureiro | Escopo financeiro (pós-MVP) | `'treasurer' in user.roles` |
| Voluntário | Suas escalas | Pessoa com `Schedule`; não tem login dedicado no MVP |
| Membro / Pessoa | Próprio perfil | `'member' in user.roles` — **Decisão aberta** OD-004 |

### 1.1 Multi-role com união de permissões

Um usuário pode ter mais de uma role simultânea. Permissões são acumuladas:

| `user.roles` | Acessos efetivos |
|---|---|
| `['pastor']` | Tudo do Pastor |
| `['leader']` | Tudo do Líder/Coordenador (escopo pelo vínculo) |
| `['treasurer']` | Tudo do Tesoureiro |
| `['treasurer', 'leader']` | União: Tesoureiro **+** Líder/Coordenador no escopo dos seus vínculos |
| `['pastor', 'treasurer']` | Pastor já cobre tudo; `treasurer` é redundante (sem efeito extra) |

**Regra de inclusão:** Pastor tem acesso completo dentro do tenant. Adicionar outras roles a um Pastor não amplia nem restringe — Pastor sempre vence.

### 1.2 Diferenciação Líder de Comunidade vs Coordenador de Ministério

Ambos usam a role `leader`. A diferença é por **vínculo**:

- Líder de Comunidade: `Community.leader` aponta para o `Person` cujo `User` é o líder.
- Coordenador de Ministério: `Ministry.coordinator` aponta para o `Person` cujo `User` é o coordenador.

Permissões são resolvidas via vínculo (`ScopedToCommunityMixin`, `ScopedToMinistryMixin`). Mesma pessoa pode ser líder de N comunidades e/ou coordenador de N ministérios.

---

## 2. Convenção

- ✅ = permitido
- ❌ = bloqueado
- 🟡 = permitido com escopo (sua comunidade, seu ministério, próprio registro)
- 📝 = exige auditoria reforçada (`SecurityLog`)

---

## 3. Matriz por Módulo

### 3.1 Plataforma e Tenants

| Ação | Platform Admin | Pastor | Líder Com. | Coord. Min. | Tesoureiro | Membro |
|---|---|---|---|---|---|---|
| Listar igrejas | ✅ 📝 | ❌ | ❌ | ❌ | ❌ | ❌ |
| Criar/provisionar igreja | ✅ 📝 | ❌ | ❌ | ❌ | ❌ | ❌ |
| Suspender/reativar igreja | ✅ 📝 | ❌ | ❌ | ❌ | ❌ | ❌ |
| Acessar dados de igreja (suporte) | ✅ 📝 com `SupportAccess` | ❌ | ❌ | ❌ | ❌ | ❌ |
| Editar dados da sua igreja | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Alterar `has_communities` | ❌ | ✅ 📝 | ❌ | ❌ | ❌ | ❌ |
| Alterar paleta/logo | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Alterar `privacy_policy_url` | ❌ | ✅ 📝 | ❌ | ❌ | ❌ | ❌ |

### 3.2 Usuários e Acessos

| Ação | Platform Admin | Pastor | Líder Com. | Coord. Min. | Tesoureiro | Membro |
|---|---|---|---|---|---|---|
| Listar usuários da igreja | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Convidar usuário | ❌ | ✅ 📝 | ❌ | ❌ | ❌ | ❌ |
| Reenviar convite | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Cancelar convite | ❌ | ✅ 📝 | ❌ | ❌ | ❌ | ❌ |
| Aceitar próprio convite | — | — | — | — | — | ✅ (convidado) |
| Alterar papel de usuário | ❌ | ✅ 📝 | ❌ | ❌ | ❌ | ❌ |
| Remover último Pastor | ❌ | ❌ (regra RN-004) | ❌ | ❌ | ❌ | ❌ |
| Desativar usuário | ❌ | ✅ 📝 | ❌ | ❌ | ❌ | ❌ |
| Reativar usuário | ❌ | ✅ 📝 | ❌ | ❌ | ❌ | ❌ |

### 3.3 Pessoas

| Ação | Platform Admin | Pastor | Líder Com. | Coord. Min. | Tesoureiro | Membro |
|---|---|---|---|---|---|---|
| Listar todas as pessoas | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Listar pessoas da sua comunidade | ❌ | ✅ | 🟡 | ❌ | ❌ | ❌ |
| Listar pessoas do seu ministério | ❌ | ✅ | ❌ | 🟡 | ❌ | ❌ |
| Ver detalhe de pessoa | ❌ | ✅ | 🟡 (sua comunidade) | 🟡 (seu ministério) | ❌ | ❌ |
| Criar pessoa | ❌ | ✅ | ✅ (vincula à sua comunidade) | ❌ | ❌ | ❌ |
| Editar pessoa | ❌ | ✅ | 🟡 (sua comunidade) | ❌ | ❌ | ❌ |
| Mudar status (visitor→member→leader) | ❌ | ✅ 📝 | ❌ | ❌ | ❌ | ❌ |
| Importar CSV | ❌ | ✅ 📝 | ❌ | ❌ | ❌ | ❌ |
| Anonimizar pessoa | ❌ | ✅ 📝 | ❌ | ❌ | ❌ | ❌ |
| Exportar dados de pessoa | ❌ | ✅ 📝 | ❌ | ❌ | ❌ | ❌ |

### 3.4 Comunidades

| Ação | Platform Admin | Pastor | Líder Com. | Coord. Min. | Tesoureiro | Membro |
|---|---|---|---|---|---|---|
| Listar comunidades | ❌ | ✅ | ✅ (todas; ver só sua em detalhe) | ❌ | ❌ | ❌ |
| Criar comunidade | ❌ | ✅ (se `has_communities=True`) | ❌ | ❌ | ❌ | ❌ |
| Editar comunidade | ❌ | ✅ | 🟡 (sua) | ❌ | ❌ | ❌ |
| Excluir comunidade | ❌ | ✅ 📝 | ❌ | ❌ | ❌ | ❌ |
| Definir líder | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Vincular pessoa | ❌ | ✅ | 🟡 (sua) | ❌ | ❌ | ❌ |

### 3.5 Ministérios

| Ação | Platform Admin | Pastor | Líder Com. | Coord. Min. | Tesoureiro | Membro |
|---|---|---|---|---|---|---|
| Listar ministérios | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Criar ministério | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Editar ministério | ❌ | ✅ | ❌ | 🟡 (seu) | ❌ | ❌ |
| Excluir ministério | ❌ | ✅ 📝 | ❌ | ❌ | ❌ | ❌ |
| Definir coordenador | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Vincular pessoa | ❌ | ✅ | ❌ | 🟡 (seu) | ❌ | ❌ |

### 3.6 Encontros e Presença

| Ação | Platform Admin | Pastor | Líder Com. | Coord. Min. | Tesoureiro | Membro |
|---|---|---|---|---|---|---|
| Listar encontros da igreja | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Criar encontro (tipo WORSHIP) | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Criar encontro (tipo COMMUNITY) | ❌ | ✅ | 🟡 (sua) | ❌ | ❌ | ❌ |
| Criar encontro (tipo EVENT/MEETING) | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Editar encontro | ❌ | ✅ | 🟡 (criador ou sua comunidade) | 🟡 (criador) | ❌ | ❌ |
| Excluir encontro | ❌ | ✅ 📝 | ❌ | ❌ | ❌ | ❌ |
| Marcar presença em lote | ❌ | ✅ | 🟡 (sua comunidade) | 🟡 (seu ministério) | ❌ | ❌ |
| Editar presença individual | ❌ | ✅ | 🟡 (sua comunidade) | 🟡 (seu ministério) | ❌ | ❌ |

### 3.7 Escalas e Voluntários

| Ação | Platform Admin | Pastor | Líder Com. | Coord. Min. | Tesoureiro | Membro |
|---|---|---|---|---|---|---|
| Listar escalas | ❌ | ✅ | ❌ | 🟡 (seu ministério) | ❌ | ❌ |
| Criar escala | ❌ | ✅ | ❌ | 🟡 (seu ministério) | ❌ | ❌ |
| Editar escala | ❌ | ✅ | ❌ | 🟡 (seu ministério) | ❌ | ❌ |
| Excluir escala | ❌ | ✅ | ❌ | 🟡 (seu ministério) | ❌ | ❌ |
| Aprovar exceção de conflito | ❌ | ✅ 📝 | ❌ | 🟡 📝 (seu ministério) | ❌ | ❌ |
| Ver próprias escalas | — | ✅ | ✅ | ✅ | ✅ | ✅ |

### 3.8 Arquivos e PDFs

| Ação | Platform Admin | Pastor | Líder Com. | Coord. Min. | Tesoureiro | Membro |
|---|---|---|---|---|---|---|
| Upload de arquivo geral | ❌ | ✅ 📝 | ❌ | ❌ | ❌ | ❌ |
| Upload em comunidade | ❌ | ✅ 📝 | 🟡 📝 (sua) | ❌ | ❌ | ❌ |
| Upload em ministério | ❌ | ✅ 📝 | ❌ | 🟡 📝 (seu) | ❌ | ❌ |
| Upload em financeiro | ❌ | ✅ 📝 | ❌ | ❌ | ✅ 📝 (pós-MVP) | ❌ |
| Listar arquivos | ❌ | ✅ | 🟡 (visíveis) | 🟡 (visíveis) | 🟡 (visíveis) | 🟡 (visíveis) |
| Download de arquivo | ❌ | ✅ 📝 | 🟡 📝 (autorizado) | 🟡 📝 (autorizado) | 🟡 📝 (autorizado) | 🟡 📝 (próprio, se autorizado) |
| Excluir arquivo | ❌ | ✅ 📝 | ❌ | ❌ | ❌ | ❌ |

### 3.9 Dashboard

| Ação | Platform Admin | Pastor | Líder Com. | Coord. Min. | Tesoureiro | Membro |
|---|---|---|---|---|---|---|
| Dashboard completo | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Dashboard simplificado da comunidade | ❌ | ✅ | 🟡 (sua) | ❌ | ❌ | ❌ |
| Dashboard simplificado do ministério | ❌ | ✅ | ❌ | 🟡 (seu) | ❌ | ❌ |
| Próprio histórico | — | ✅ | ✅ | ✅ | ✅ | ✅ |

### 3.10 Auditoria

| Ação | Platform Admin | Pastor | Líder Com. | Coord. Min. | Tesoureiro | Membro |
|---|---|---|---|---|---|---|
| Ver `AuditLog` da igreja | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Ver `SecurityLog` da igreja | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Ver auditoria de Platform Admin (com `SupportAccess`) | ✅ próprio | ✅ da própria igreja | ❌ | ❌ | ❌ | ❌ |

---

## 4. Implementação

### 4.1 Mixins

```python
# apps/core/mixins.py

class TenantRequiredMixin:
    """Re-export do django-tenants. Obrigatório em toda view autenticada."""
    pass


class RoleRequiredMixin:
    """Base. Subclasses definem required_roles (qualquer um permite)."""
    required_roles: tuple[str, ...] = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied
        if not request.user.has_any_role(*self.required_roles):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class PastorRequiredMixin(RoleRequiredMixin):
    """Apenas Pastor pode acessar."""
    required_roles = ('pastor',)


class LeaderOrPastorMixin(RoleRequiredMixin):
    """Pastor ou Leader (qualquer um cobre). Escopo verificado em get_queryset."""
    required_roles = ('pastor', 'leader')


class TreasurerOrPastorMixin(RoleRequiredMixin):
    """Pastor ou Tesoureiro (pós-MVP)."""
    required_roles = ('pastor', 'treasurer')


class ScopedToCommunityMixin:
    """Filtra queryset para comunidades onde o user é líder.

    Pastor vê tudo (curto-circuita o filtro). Outros papéis veem apenas
    comunidades onde Person vinculado ao User é Community.leader.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.has_any_role('pastor'):
            return qs
        return qs.filter(leader__user__id=self.request.user.id)


class ScopedToMinistryMixin:
    """Filtra queryset para ministérios onde o user é coordenador."""

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.has_any_role('pastor'):
            return qs
        return qs.filter(coordinator__user__id=self.request.user.id)


class PlatformAdminWithSupportAccessMixin:
    """Permite Platform Admin apenas se houver SupportAccess ativo para o tenant.

    Sem SupportAccess, retorna 403 e registra SecurityLog.
    """

    def dispatch(self, request, *args, **kwargs):
        admin = getattr(request.user, 'platform_admin', None)
        if not admin or not admin.is_active:
            raise PermissionDenied
        tenant = request.tenant
        has_access = SupportAccess.objects.filter(
            admin=admin,
            church=tenant,
            ended_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).exists()
        if not has_access:
            SecurityLog.objects.create(
                user_id=request.user.id,
                tenant_id=tenant.schema_name,
                event_type='platform_admin_access',
                payload={'denied': True, 'reason': 'no_active_support_access'},
                ip_address=get_client_ip(request),
            )
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
```

### 4.2 Padrão de aplicação

Cada view sensível aplica **três camadas**:

1. **View:** mixin verifica papel.
2. **Service:** valida regra de negócio e escopo.
3. **Queryset:** filtra por tenant + escopo do papel.

```python
# Exemplo: editar comunidade
class CommunityUpdateView(
    LoginRequiredMixin,
    TenantRequiredMixin,
    LeaderOrPastorMixin,
    ScopedToCommunityMixin,
    UpdateView,
):
    model = Community
    fields = ['name', 'meeting_day', 'meeting_time', 'is_active']

    def form_valid(self, form):
        # Service valida e audita
        instance = update_community(
            community=form.instance,
            data=form.cleaned_data,
            user=self.request.user,
        )
        return redirect(instance.get_absolute_url())
```

### 4.3 Auditoria

Toda ação marcada com 📝 nesta matriz exige `SecurityLog` além do `AuditLog`. Implementar via signals em `apps/<x>/signals.py` ou explicitamente no service.

---

## 5. Regras transversais

| Regra | Aplicação |
|---|---|
| Platform Admin não acessa tenant sem `SupportAccess` ativo | `PlatformAdminWithSupportAccessMixin`; tentativa nega 403 e registra `SecurityLog` |
| `SupportAccess` expira automaticamente em 4 horas | Property `is_active` valida `ended_at IS NULL AND expires_at > now()` |
| Pastor não pode remover o último Pastor da igreja | Validação no service `change_roles`: se removendo `pastor` e ninguém mais tem `pastor in roles`, rejeita (RN-004) |
| Líder/Coordenador só vê dados do seu escopo | Mixins `ScopedToCommunityMixin` e `ScopedToMinistryMixin` + filtros em service |
| Membro/Pessoa só acessa próprio perfil | Pendente OD-004 |
| Tesoureiro só atua em escopo financeiro | Pós-MVP |
| Convite usa token UUID único, expira em 7 dias | Service `accept_invite` valida |
| Multi-role: permissões são união | `user.has_any_role(*roles)` retorna `True` se interseção não-vazia |
| Migração entre igrejas não é suportada | Para mudar de igreja: excluir conta + recriar via novo convite |

---

## 6. Testes obrigatórios

Cada célula desta matriz precisa de teste em `test_permissions_matrix.py`:

- Para cada (papel, ação): verificar resposta esperada (200, 302, 403 ou 404).
- Para cada ação com escopo (🟡): verificar que ator de outro escopo recebe 404 (nunca 403 com dado vazado).
- Para cada ação 📝: verificar entrada correspondente em `SecurityLog`.

Ver [`TEST_STRATEGY.md`](TEST_STRATEGY.md) para fixtures e padrão de teste.
