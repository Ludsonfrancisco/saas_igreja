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
| Secretário | Admin da igreja, sem financeiro | `'secretary' in user.roles` — cadastra/edita pessoas, grupos e escalas e **concede acessos (com teto)**; NÃO faz financeiro nem ações irreversíveis (anonimizar/excluir) |
| Líder de Comunidade | Sua(s) comunidade(s) | `'leader' in user.roles` + comunidades onde é `Community.leader` |
| Coordenador de Ministério | Seu(s) ministério(s) | `'leader' in user.roles` + ministérios onde é `Ministry.coordinator` |
| Tesoureiro | Escopo financeiro — **ativo no MVP** (básico, Sprint 6.7); avançado Sprint 8 (OD-024) | `'treasurer' in user.roles` |
| Voluntário escalado | Suas escalas (read-only) | Pessoa com `Schedule`; **sem login** — acessa as próprias escalas/próximos encontros via **magic-link** (token assinado, read-only, sem conta/senha/MFA), **OD-022**. Distinto do Membro geral |
| Membro / Pessoa | — (sem acesso no MVP) | `'member' in user.roles` — **OD-004 (fechada):** sem login no MVP; existe apenas como `Person`. Sem acesso (≠ Voluntário escalado, que tem magic-link) |

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

- Líder de Comunidade: o `Person` está em `Community.leaders` (M2M) e seu `user_id` é o do líder logado.
- Coordenador de Ministério: o `Person` está em `Ministry.coordinators` (M2M) e seu `user_id` é o do coordenador.

Permissões são resolvidas via vínculo (`ScopedToCommunityMixin`, `ScopedToMinistryMixin`). Mesma pessoa pode ser líder de N comunidades e/ou coordenador de N ministérios. **E o inverso também (decisão 2026-06-04 / OD-019):** uma mesma comunidade pode ter VÁRIOS líderes e um ministério VÁRIOS coordenadores — `Community.leaders` e `Ministry.coordinators` são **M2M** de `Person` (antes eram FK única). O vínculo ao login é `Person.user_id` (IntegerField, TENANT-04).

---

## 2. Convenção

- ✅ = permitido
- ❌ = bloqueado
- 🟡 = permitido com escopo (sua comunidade, seu ministério, próprio registro)
- 📝 = exige auditoria reforçada (`SecurityLog`)

---

## 3. Matriz por Módulo

### 3.1 Plataforma e Tenants

| Ação | Platform Admin | Pastor | Secretário | Líder Com. | Coord. Min. | Tesoureiro | Membro |
|---|---|---|---|---|---|---|---|
| Listar igrejas | ✅ 📝 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Criar/provisionar igreja | ✅ 📝 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Suspender/reativar igreja | ✅ 📝 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Acessar dados de igreja (suporte) | ✅ 📝 com `SupportAccess` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Editar dados da sua igreja | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Alterar `has_communities` | ❌ | ✅ 📝 | ❌ | ❌ | ❌ | ❌ | ❌ |
| Alterar paleta/logo | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Alterar `privacy_policy_url` | ❌ | ✅ 📝 | ❌ | ❌ | ❌ | ❌ | ❌ |

### 3.2 Usuários e Acessos

| Ação | Platform Admin | Pastor | Secretário | Líder Com. | Coord. Min. | Tesoureiro | Membro |
|---|---|---|---|---|---|---|---|
| Listar usuários da igreja | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Convidar usuário | ❌ | ✅ 📝 | ✅ 📝 | ❌ | ❌ | ❌ | ❌ |
| Reenviar convite | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Cancelar convite | ❌ | ✅ 📝 | ✅ 📝 | ❌ | ❌ | ❌ | ❌ |
| Aceitar próprio convite | — | — | — | — | — | — | ✅ (convidado) |
| Conceder/alterar papéis (exceto `pastor`) | ❌ | ✅ 📝 | ✅ 📝 🔒 | ❌ | ❌ | ❌ | ❌ |
| **Conceder o papel `pastor`** | ❌ | ✅ 📝 | ❌ 🔒 | ❌ | ❌ | ❌ | ❌ |
| **Alterar os próprios papéis (auto-escalonar)** | ❌ | ❌ 🔒 | ❌ 🔒 | ❌ | ❌ | ❌ | ❌ |
| Remover último Pastor | ❌ | ❌ (regra RN-004) | ❌ | ❌ | ❌ | ❌ | ❌ |
| Desativar usuário (não-Pastor) | ❌ | ✅ 📝 | ✅ 📝 🔒 | ❌ | ❌ | ❌ | ❌ |
| **Desativar um Pastor** | ❌ | ✅ 📝 | ❌ 🔒 | ❌ | ❌ | ❌ | ❌ |
| Reativar usuário | ❌ | ✅ 📝 | ✅ 📝 | ❌ | ❌ | ❌ | ❌ |

> 🔒 **Travas de segurança da Gestão de Acessos (OD-019 / RISK-015).** O Secretário concede acesso, mas com teto: (a) **não pode conceder/atribuir o papel `pastor`** nem **desativar um Pastor** — só Pastor cria/derruba Pastor; (b) **ninguém altera os próprios papéis** (sem auto-escalonamento); (c) tudo escopado ao tenant (`church`); (d) toda concessão é auditada (`AuditLog` + `SecurityLog` `role_change`); (e) RN-004 (último Pastor) permanece. MFA do Secretário passa a ser exigido na Sprint 7 (junto com Pastor/PlatformAdmin).

### 3.2.1 Fluxo de Gestão de Acessos (OD-019)

Tela administrativa (Pastor ou Secretário) que concede acesso a um membro de forma
unificada — funções **+** escopo de grupo numa só operação:

1. Seleciona o **`Person`** (membro) e garante que ele tenha um **`User`** (login):
   se não tiver, dispara um **convite** (fluxo da Sprint 2). O vínculo é gravado em
   `Person.user_id` (IntegerField, TENANT-04 — nunca FK).
2. Marca as **funções** (multi-select → `User.roles`): `leader`, `treasurer`,
   `secretary`. O papel `pastor` é exceção (ver travas 🔒).
3. Para função **com escopo**, seleciona o(s) **grupo(s)**: `leader` →
   comunidade(s) (`Community.leaders`, M2M) e/ou ministério(s)
   (`Ministry.coordinators`, M2M). O acesso resultante **cai em cascata** sobre os
   membros daquele grupo (resolvido por `ScopedToCommunityMixin`/
   `ScopedToMinistryMixin`, lookup `*_user_id`).

**Travas obrigatórias (🔒 — RISK-015):** Secretário NÃO concede/atribui `pastor`
nem desativa Pastor; ninguém altera os próprios papéis; tudo escopado ao tenant e
auditado (`role_change`); RN-004 (último Pastor) intacta.

### 3.3 Pessoas

| Ação | Platform Admin | Pastor | Secretário | Líder Com. | Coord. Min. | Tesoureiro | Membro |
|---|---|---|---|---|---|---|---|
| Listar todas as pessoas | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Listar pessoas da sua comunidade | ❌ | ✅ | ✅ | 🟡 | ❌ | ❌ | ❌ |
| Listar pessoas do seu ministério | ❌ | ✅ | ✅ | ❌ | 🟡 | ❌ | ❌ |
| Ver detalhe de pessoa | ❌ | ✅ | ✅ | 🟡 (sua comunidade) | 🟡 (seu ministério) | ❌ | ❌ |
| Criar pessoa | ❌ | ✅ | ✅ | ✅ (vincula à sua comunidade) | ❌ | ❌ | ❌ |
| Editar pessoa | ❌ | ✅ | ✅ | 🟡 (sua comunidade) | ❌ | ❌ | ❌ |
| Mudar status (visitor→member→leader) | ❌ | ✅ 📝 | ✅ 📝 | ❌ | ❌ | ❌ | ❌ |
| Importar CSV | ❌ | ✅ 📝 | ✅ 📝 | ❌ | ❌ | ❌ | ❌ |
| Anonimizar pessoa | ❌ | ✅ 📝 | ❌ 🔒 | ❌ | ❌ | ❌ | ❌ |
| Exportar dados de pessoa | ❌ | ✅ 📝 | ❌ 🔒 | ❌ | ❌ | ❌ | ❌ |

### 3.4 Comunidades

| Ação | Platform Admin | Pastor | Secretário | Líder Com. | Coord. Min. | Tesoureiro | Membro |
|---|---|---|---|---|---|---|---|
| Listar comunidades | ❌ | ✅ | ✅ | ✅ (todas; ver só sua em detalhe) | ❌ | ❌ | ❌ |
| Criar comunidade | ❌ | ✅ (se `has_communities=True`) | ✅ (se `has_communities=True`) | ❌ | ❌ | ❌ | ❌ |
| Editar comunidade | ❌ | ✅ | ✅ | 🟡 (sua) | ❌ | ❌ | ❌ |
| Excluir comunidade | ❌ | ✅ 📝 | ❌ 🔒 | ❌ | ❌ | ❌ | ❌ |
| Definir líderes (1+, M2M) | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Vincular pessoa | ❌ | ✅ | ✅ | 🟡 (sua) | ❌ | ❌ | ❌ |

### 3.5 Ministérios

| Ação | Platform Admin | Pastor | Secretário | Líder Com. | Coord. Min. | Tesoureiro | Membro |
|---|---|---|---|---|---|---|---|
| Listar ministérios | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Criar ministério | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Editar ministério | ❌ | ✅ | ✅ | ❌ | 🟡 (seu) | ❌ | ❌ |
| Excluir ministério | ❌ | ✅ 📝 | ❌ 🔒 | ❌ | ❌ | ❌ | ❌ |
| Definir coordenadores (1+, M2M) | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Vincular pessoa | ❌ | ✅ | ✅ | ❌ | 🟡 (seu) | ❌ | ❌ |

### 3.6 Encontros e Presença

> **OD-019 (Secretário) + decisão Sprint 4 (2026-06-04):** o Secretário é **admin como o Pastor** em Encontros/Presença — cria/edita **qualquer** encontro (todos os tipos, sem escopo) e marca presença. **Exceção:** **excluir encontro continua exclusivo do Pastor** (🔒, ação destrutiva). `created_by` (`user_id` do criador, TENANT-04) habilita a trava "editar pelo criador" para Líder/Coordenador.

| Ação | Platform Admin | Pastor | Secretário | Líder Com. | Coord. Min. | Tesoureiro | Membro |
|---|---|---|---|---|---|---|---|
| Listar encontros da igreja | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Criar encontro (tipo WORSHIP) | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Criar encontro (tipo COMMUNITY) | ❌ | ✅ | ✅ | 🟡 (sua) | ❌ | ❌ | ❌ |
| Criar encontro (tipo EVENT/MEETING) | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Editar encontro | ❌ | ✅ | ✅ | 🟡 (criador ou sua comunidade) | 🟡 (criador) | ❌ | ❌ |
| Excluir encontro | ❌ | ✅ 📝 | ❌ 🔒 | ❌ | ❌ | ❌ | ❌ |
| Marcar presença em lote | ❌ | ✅ | ✅ | 🟡 (sua comunidade) | 🟡 (seu ministério) | ❌ | ❌ |
| Editar presença individual | ❌ | ✅ | ✅ | 🟡 (sua comunidade) | 🟡 (seu ministério) | ❌ | ❌ |

### 3.7 Escalas e Voluntários

> **OD-019 (Secretário) + decisão Sprint 5 (2026-06-05):** o Secretário é **admin no CRUD** de escalas (lista/cria/edita/exclui em qualquer ministério, como o Pastor). **Exceção:** **não aprova exceção de conflito** (❌ 🔒) — o override de conflito fica restrito ao **Pastor + Coordenador competente** (coordenador do `Schedule.ministry`), preservando o controle de quem autoriza furar a regra.

| Ação | Platform Admin | Pastor | Secretário | Líder Com. | Coord. Min. | Tesoureiro | Membro |
|---|---|---|---|---|---|---|---|
| Listar escalas | ❌ | ✅ | ✅ | ❌ | 🟡 (seu ministério) | ❌ | ❌ |
| Criar escala | ❌ | ✅ | ✅ | ❌ | 🟡 (seu ministério) | ❌ | ❌ |
| Editar escala | ❌ | ✅ | ✅ | ❌ | 🟡 (seu ministério) | ❌ | ❌ |
| Excluir escala | ❌ | ✅ | ✅ | ❌ | 🟡 (seu ministério) | ❌ | ❌ |
| Aprovar exceção de conflito | ❌ | ✅ 📝 | ❌ 🔒 | ❌ | 🟡 📝 (seu ministério) | ❌ | ❌ |
| Ver próprias escalas | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### 3.8 Arquivos e PDFs

| Ação | Platform Admin | Pastor | Líder Com. | Coord. Min. | Tesoureiro | Membro |
|---|---|---|---|---|---|---|
| Upload de arquivo geral | ❌ | ✅ 📝 | ❌ | ❌ | ❌ | ❌ |
| Upload em comunidade | ❌ | ✅ 📝 | 🟡 📝 (sua) | ❌ | ❌ | ❌ |
| Upload em ministério | ❌ | ✅ 📝 | ❌ | 🟡 📝 (seu) | ❌ | ❌ |
| Upload em financeiro | ❌ | ✅ 📝 | ❌ | ❌ | ✅ 📝 (Sprint 8) | ❌ |
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
| Home "Painel Oikonos": KPIs da igreja + próximas programações (RF-103, OD-030) | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Home: card "Saúde do Ministério" / GAP de voluntários (RF-104) | ❌ | ✅ (todos) | ❌ | 🟡 (seu) | ❌ | ❌ |
| Calendário de agenda (RF-102) — **movido da home para Encontros** (OD-030; pendente de wiring) | ❌ | ✅ | ✅ | ✅ | — | — |

> **OD-030 (2026-06-09):** a home virou o painel "Painel Oikonos" (design `igreja-athos-dashboard`), aberto a **todo papel logado** (`TenantRequiredMixin`): KPIs da igreja (agregados coarse) + próximas programações + card Saúde do Ministério (este escopado por papel — Pastor/Secretário todos, Coordenador o seu). O **calendário de agenda (RF-102)** saiu da home; o código (fragmentos `/inicio/calendario/`, `/inicio/dia/`) está pronto para wiring em **Encontros**.

### 3.10 Auditoria

| Ação | Platform Admin | Pastor | Líder Com. | Coord. Min. | Tesoureiro | Membro |
|---|---|---|---|---|---|---|
| Ver `AuditLog` da igreja | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Ver `SecurityLog` da igreja | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Ver auditoria de Platform Admin (com `SupportAccess`) | ✅ próprio | ✅ da própria igreja | ❌ | ❌ | ❌ | ❌ |

### 3.11 Financeiro (Sprint 6.7 · OD-024a)

Gate: **`TreasurerOrPastorMixin`** (Pastor **ou** Tesoureiro) + `TenantRequiredMixin`.
O **Secretário NÃO faz financeiro** (OD-019: admin geral, sem tesouraria). Lançamentos
auditados (`AuditLogMixin`); `Transaction.contributor` → `Person` `SET_NULL` (LGPD).

| Ação | Platform Admin | Pastor | Líder Com. | Coord. Min. | Tesoureiro | Membro |
|---|---|---|---|---|---|---|
| Painel financeiro (`/financeiro/`) — KPIs/saldo | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ |
| Extrato + filtros (`/financeiro/lancamentos/`) | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ |
| Criar/editar/excluir lançamento | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ |
| Categorias (criar/editar) | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ |
| Exportar CSV (auditado `export`) | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ |

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
    """Pastor ou Tesoureiro (financeiro básico no MVP, Sprint 6.7, OD-024a)."""
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
| Tesoureiro só atua em escopo financeiro | Básico no MVP (Sprint 6.7); avançado Sprint 8 (OD-024) |
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
