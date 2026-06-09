---
name: owner-workflow
description: Como o dono conduz o trabalho — bloco por vez, governança inviolável, nunca versionar pelo agente
metadata:
  type: feedback
---

O dono autoriza UMA sprint (G-01) e libera UM bloco por vez (G-02); implementar só o bloco liberado, escopo cirúrgico.

**Why:** modelo de revisão incremental do projeto (SDD); cada bloco é revisado antes do próximo.

**How to apply:**
- NUNCA `git commit/push/merge` nem abrir PR (G-03) — deixar tudo no workspace para o dono versionar (G-04).
- Decisão fora do escopo do bloco atual → consultar o dono (G-05), não assumir.
- Toda task deve referenciar RF/RNF/RN/OD do PRD; sem requisito, não implementar.
- Ao terminar um bloco, reportar em texto: arquivos tocados, build, riscos de re-teste, e qualquer decisão que extrapole o escopo (para validação). Confirmar explicitamente que não commitou.

Ver [[shell-athos-v2]].
