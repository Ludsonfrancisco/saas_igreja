---
name: user-profile
description: Project owner of SaaS Igreja — governance-strict, scope-disciplined, authorizes work block-by-block
metadata:
  type: user
---

The user is the owner of the SaaS Igreja project (multi-tenant Django SaaS for churches). They work under strict governance (CLAUDE.md G-01..G-05): work is authorized block-by-block, never touch git (no commit/push/merge/PR — G-03), stay strictly in declared scope, and ask before making out-of-scope technical decisions (G-05).

**How to apply:** Implement only the explicitly authorized sub-tasks; do not add adjacent features even if tempting. When a spec point is ambiguous, choose the most security-conservative option and flag it clearly in the report rather than inventing scope. Every implemented task must trace to an RF/RNF/RN or TECH_SPEC rule. Report file paths, exact verification output, and judgment calls at the end. See [[project-tenant-provisioning]].
