---
name: f2-configurable-terms
description: How to use the configurable church labels (terms.community/ministry) in templates, incl. gender-neutral pt-BR phrasing and the |add filter-chain trick
metadata:
  type: project
---

F2/OD-032 = rótulos configuráveis por igreja para Comunidade e Ministério. Context processor `apps/core/context_processors.py` (`church_theme`) injeta `terms` em TODO template:
`terms.community` / `terms.community_plural` / `terms.ministry` / `terms.ministry_plural` (defaults: Comunidade/Comunidades/Ministério/Ministérios). Minúsculas no meio de frase: `{{ terms.community|lower }}`.

**Why:** uma igreja pode chamar Comunidade de "Célula" (f) ou "Grupo" (m); Ministério de "Departamento" (m) ou "Equipe" (f). O termo muda de GÊNERO.

**How to apply (gramática neutra — regra do dono):** nunca prenda artigo/adjetivo flexionado ao termo. Padrões que funcionaram para os dois gêneros:
- "Adicionar/Editar {{ terms.x|lower }}" (verbo neutro em vez de "Nova/Novo")
- "Sem {{ terms.x_plural|lower }} ainda" (plural evita nenhum/nenhuma)
- "Qualquer {{ terms.x|lower }}" (filtro "todas/todos" → "Qualquer" é invariável)
- "de cada {{ terms.x|lower }}" / "por {{ terms.x|lower }}" (evita "do seu/da sua")
- "Reunião de {{ terms.community|lower }}" (evita "nesta célula")
- Para frase genérica que significa "a congregação" (não o model Community), trocar por "da igreja" (não usar terms).

**Trick p/ compor string em `{% include with %}`:** `chart_title='Frequência por '|add:community_lc` onde `community_lc` vem de um `{% with community_lc=terms.community|lower %}`. NÃO encadeie `'Texto '|add:terms.x|lower` direto — o `|lower` minúsculiza o texto inteiro. Sempre lowercase o termo ANTES, num `{% with %}`.

**Testes:** defaults batem exatamente com Comunidade/Ministério, então trocar hardcoded "Comunidade/Ministério" → `{{ terms.* }}` NÃO quebra asserts. MAS onde a cópia usava "célula"/"departamento" (não-default), o render passa a mostrar o default → ajustar o assert. Caso real: `apps/communities/tests/test_page_stats.py` asserava `'Frequência por célula'` → virou `'Frequência por comunidade'` (o chart_title da `community_list.html` agora usa o term).

**NÃO MEXER:** `apps/tenants/templates/tenants/church_settings.html` — é a tela que CONFIGURA os rótulos; ali "Comunidade/Ministério" são literais de instrução.

Card labels como "Células"/"Membros nas células" vêm de `apps/communities/services.py` (Python), não de template — fora do escopo de varredura de template e seus asserts (`cards['Células']`) continuam verdes.
