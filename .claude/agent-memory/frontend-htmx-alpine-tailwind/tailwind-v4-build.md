---
name: tailwind-v4-build
description: Build do Tailwind v4 (CSS-first), paleta Oikonos v2 e mecanismo de tema por igreja (accent/hot via CSS vars)
metadata:
  type: project
---

Tailwind v4 CSS-first, sem tailwind.config.js. Fonte em `static/src/input.css` (`@theme` + `@source '../../templates'` e `'../../apps'`).

**Build (NÃO usar CDN — gate Lighthouse):**
`uv run tailwindcss -i static/src/input.css -o static/css/app.css --minify`
(CLI standalone via pytailwindcss, v4.3.0; recompilar sempre após editar tokens/classes novas).

**Paleta Oikonos v2 (Athos v2 · Sprint 6.6):** accent `#C2552C` / accent-2 `#A8431F` (temáveis por igreja), hot/âmbar `#EBB45C`, laranja `#E0892D` (token `--color-orange`, base neutra fixa), canvas `--color-bg #f1eadf`. Sidebar escura: `--color-sidebar #211a14`, `--color-sidebar-ink`, `--color-sidebar-muted`.

**Tema por igreja (DS-01):** `--color-accent: var(--accent)` no `@theme`; defaults em `:root` do input.css; `apps/core/context_processors.py::church_theme` lê `Church.accent_color/hot_color` e o `base.html` injeta `--accent/--accent-2/--hot` em `:root`. **Os defaults do context_processor DEVEM espelhar o `:root` do input.css** — há teste `test_church_theme_falls_back_to_oikonos_without_tenant` que trava o valor (hoje `#C2552C`). Ao trocar a paleta, atualizar os dois + o teste.

**Tipografia Athos v2:** Inter (`--font-sans`, corpo) + Poppins (`--font-display`, marca). Ambas via Google Fonts no `base.html`. `tabular-nums` em KPIs via classe `.tnum` (e embutido em `.stat-num`).

Ver [[shell-athos-v2]].
