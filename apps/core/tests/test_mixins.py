"""Sprint 2 / Frente 3 — mixins de papel e escopo (RN-003a / P-ARQ-08).

`RoleRequiredMixin` e subclasses sao a camada de view da autorizacao multi-role:
negam com `PermissionDenied` (HTTP 403) quem nao tem nenhum dos `required_roles`
e liberam quem tem qualquer um (uniao). Os `ScopedTo*` sao filtros de queryset
model-agnosticos: Pastor curto-circuita; outros filtram pelo proprio escopo.

Testamos os mixins de papel com `RequestFactory` (sem precisar de tenant: a
barreira de papel nao toca em banco). Os mixins de escopo sao verificados com um
queryset falso para confirmar curto-circuito (Pastor) e filtro por lookup string
sem importar Community/Ministry.
"""

import pytest
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from django.views.generic import View

from apps.accounts.models import User
from apps.core.mixins import (
    LeaderOrPastorMixin,
    PastorRequiredMixin,
    RoleRequiredMixin,
    ScopedToCommunityMixin,
    ScopedToMinistryMixin,
    TreasurerOrPastorMixin,
)


def _view(mixin_cls):
    """Monta uma CBV minima com o mixin de papel sob teste."""

    class _V(mixin_cls, View):
        def get(self, request, *args, **kwargs):
            from django.http import HttpResponse

            return HttpResponse('ok')

    return _V.as_view()


def _request(roles, authenticated=True):
    req = RequestFactory().get('/x/')
    req.user = User(roles=roles)
    # Em CBV de teste, is_authenticated e propriedade do User; para anonimo
    # forcamos um objeto sem papeis e is_authenticated=False.
    if not authenticated:

        class _Anon:
            is_authenticated = False

            def has_any_role(self, *roles):
                return False

        req.user = _Anon()
    return req


# --------------------------------------------------------------------------- #
# RoleRequiredMixin / subclasses
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_pastor_required_denies_non_pastor():
    view = _view(PastorRequiredMixin)
    with pytest.raises(PermissionDenied):
        view(_request(['leader', 'treasurer']))


@pytest.mark.django_db
def test_pastor_required_allows_pastor():
    view = _view(PastorRequiredMixin)
    resp = view(_request(['pastor']))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_leader_or_pastor_allows_both():
    view = _view(LeaderOrPastorMixin)
    assert view(_request(['leader'])).status_code == 200
    assert view(_request(['pastor'])).status_code == 200
    # E nega quem nao tem nenhum dos dois.
    with pytest.raises(PermissionDenied):
        view(_request(['treasurer']))


@pytest.mark.django_db
def test_treasurer_or_pastor_allows_both():
    view = _view(TreasurerOrPastorMixin)
    assert view(_request(['treasurer'])).status_code == 200
    assert view(_request(['pastor'])).status_code == 200
    with pytest.raises(PermissionDenied):
        view(_request(['leader']))


@pytest.mark.django_db
def test_role_mixin_denies_unauthenticated():
    view = _view(PastorRequiredMixin)
    with pytest.raises(PermissionDenied):
        view(_request([], authenticated=False))


@pytest.mark.django_db
def test_multi_role_user_satisfies_union():
    """['treasurer','leader'] passa em Leader e Tesoureiro; falha em Pastor-only."""
    assert (
        _view(LeaderOrPastorMixin)(_request(['treasurer', 'leader'])).status_code == 200
    )
    assert (
        _view(TreasurerOrPastorMixin)(_request(['treasurer', 'leader'])).status_code
        == 200
    )
    with pytest.raises(PermissionDenied):
        _view(PastorRequiredMixin)(_request(['treasurer', 'leader']))


def test_role_required_mixin_default_required_roles_empty():
    """A base sem required_roles nega todo mundo (uniao vazia)."""
    assert RoleRequiredMixin.required_roles == ()


# --------------------------------------------------------------------------- #
# ScopedTo* mixins — model-agnosticos (importam/instanciam sem Community/Ministry)
# --------------------------------------------------------------------------- #
class _FakeQS:
    """Queryset falso que registra os filtros aplicados (sem tocar em banco)."""

    def __init__(self):
        self.filters = None

    def filter(self, **kwargs):
        self.filters = kwargs
        return self


class _FakeUser:
    def __init__(self, roles, user_id=7):
        self._roles = roles
        self.id = user_id

    def has_any_role(self, *roles):
        return bool(set(roles) & set(self._roles))


def _scoped_instance(mixin_cls, roles):
    """Instancia o mixin com um super().get_queryset() que devolve _FakeQS."""

    class _Base:
        def get_queryset(self):
            return _FakeQS()

    class _Scoped(mixin_cls, _Base):
        pass

    inst = _Scoped()
    req = RequestFactory().get('/x/')
    req.user = _FakeUser(roles)
    inst.request = req
    return inst


def test_scoped_to_community_pastor_short_circuits():
    inst = _scoped_instance(ScopedToCommunityMixin, ['pastor'])
    qs = inst.get_queryset()
    # Pastor ve tudo: nenhum filtro aplicado.
    assert qs.filters is None


def test_scoped_to_community_non_pastor_filters_by_leader():
    inst = _scoped_instance(ScopedToCommunityMixin, ['leader'])
    qs = inst.get_queryset()
    # TENANT-04: o staff Person guarda `user_id` (IntegerField, não-FK) -> lookup
    # `leader__user_id` (e NÃO `leader__user__id`). Default configurável.
    assert qs.filters == {'leader__user_id': 7}


def test_scoped_to_ministry_pastor_short_circuits():
    inst = _scoped_instance(ScopedToMinistryMixin, ['pastor'])
    assert inst.get_queryset().filters is None


def test_scoped_to_ministry_non_pastor_filters_by_coordinator():
    inst = _scoped_instance(ScopedToMinistryMixin, ['leader'])
    # TENANT-04: lookup por `coordinator__user_id` (não-FK).
    assert inst.get_queryset().filters == {'coordinator__user_id': 7}
