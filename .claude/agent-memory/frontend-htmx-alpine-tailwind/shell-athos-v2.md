---
name: shell-athos-v2
description: Estrutura do shell app_base.html Athos v2 (sidebar vertical desktop + drawer hambúrguer mobile) e seus partials de navegação
metadata:
  type: project
---

Shell do app autenticado migrado de nav-rail HORIZONTAL (6.5) para SIDEBAR VERTICAL (Athos v2, Sprint 6.6 Bloco 1).

**Arquivos do shell:**
- `templates/app_base.html` — `{% block shell %}` com wrapper `x-data="{ open: false }"` (estado do drawer). Desktop (lg+): `<aside class="sidebar ... hidden lg:flex">` sticky 244px. Mobile: overlay `bg-ink/50` + `<aside ...>` drawer `fixed inset-y-0 left-0` com `x-trap.noscroll="open"`, `role=dialog`, `aria-modal`. Hambúrguer no header (`lg:hidden`) com `:aria-expanded="open"` + `aria-controls="mobile-drawer"`. Menu do usuário usa `x-data="{ menu: false }"` separado (não colidir com `open` do drawer).
- `templates/components/sidebar_nav.html` — APENAS a lista de `{% side_link %}` por papel (espelha ACCESS_MATRIX); incluído 2x (sidebar desktop + drawer). O container é de quem inclui. Drawer fecha ao tocar link via `@click="open = false"` no `<nav>` (bubbling).
- `templates/components/_side_link.html` — item `.side-item` (renderizado por `{% side_link %}`).
- Tag `side_link` em `apps/core/templatetags/nav_extras.py` (compartilha `_is_active` com lógica exact/match/prefixo).

**Removido (era shell antigo):** `components/nav.html`, `components/_nav_link.html`, e a tag `nav_link`. Classes `.nav-rail`/`.nav-item` saíram do input.css.

**Foco preso:** `x-trap` exige o plugin Alpine Focus — carregado em `base.html` ANTES do core Alpine: `@alpinejs/focus@3.14.1`.

Lógica de papéis (idêntica à 6.5): Painel sempre; Pessoas/Comunidades/Ministérios/Encontros/Escalas = pastor|secretary|leader; Arquivos = +treasurer; Acessos/Convites = pastor|secretary.

Ver [[tailwind-v4-build]].
