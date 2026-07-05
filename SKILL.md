---
name: reality-check
description: >
  Prevents coding agents from hallucinating files, functions, classes, APIs,
  dependencies, env vars, or architecture. Apply on any coding task — editing,
  adding features, fixing bugs, refactoring, suggesting dependencies, or
  describing architecture. Ignore for purely conversational or brainstorming
  requests. Manual invoke with $reality-check.
---

# Reality-Check Skill

One governing rule, five categories, two enforcement layers. Prevents agents
from claiming or coding against anything in the repo that hasn't been verified
this session.

## Governing Rule (MUST)

> Before stating or coding against any file, function, class, API, dependency,
> environment variable, or architectural fact, confirm it exists by searching
> or reading **this repo in the current session**. If unverifiable, say
> exactly: `Not found — searched for [X]` and **stop**. Never substitute a
> plausible guess.

## Category Rules

| # | Category | MUST rule | Tool calls |
|---|----------|-----------|------------|
| 1 | **Filesystem** | Verify every referenced file path exists before reading, editing, or stating it exists. | `Glob(pattern)` then `Read(path)` |
| 2 | **Symbols** | Search for every function/class/type/variable name before claiming it exists or modifying it. | `Grep(pattern)` with language-specific `include` filter |
| 3 | **Dependencies & APIs** | Check the project manifest for any package before suggesting it. For unlisted packages, verify it exists on the real registry (npm, PyPI, crates.io). | `Read(manifest)`, `WebFetch(registry URL)` |
| 4 | **Environment & Config** | Read `.env*`, `wrangler.jsonc`, or equivalent before referencing any env var, secret, or config key. | `Glob(".env*")`, `Read(path)` |
| 5 | **Architecture** | Grep for actual imports/usages before describing how components connect. Never infer architecture from memory. | `Grep("import.*X")`, `Grep("require.*X")` |

## Trigger

**Auto-triggers** when the task involves modifying code, adding features,
fixing bugs, refactoring, suggesting dependencies, or describing repo
architecture.

**Does NOT trigger** on purely conversational questions, brainstorming without
implementation, or code review of external code not in the repo.

**Manual invoke:** `$reality-check` — prints this rule summary and offers to
run the backstop script on the last response.

## Before-Writing-Code Checklist

Before creating any new file or making significant edits:

1. **Existing implementations?** `Grep` for feature keywords across the project
2. **Existing utilities?** `Glob` for `utils/`, `helpers/`, `lib/` — read them
3. **Existing tests?** `Glob` for `test_*`, `*_test.*`, `*.test.*`, `*.spec.*`
4. **Config conventions?** Read relevant config files for the feature area
5. **Existing types/interfaces?** `Grep` for type/interface definitions

## End-of-Task Verification

At the end of every task, run the backstop script:

```bash
python <skill-dir>/scripts/verify-diff.py \
  --diff <path-to-diff-or-response> \
  --manifest <manifest-files> \
  --env-file <.env.example> \
  --source-dirs <src-dirs>
```

Then populate and append the verification report template from
[reference/end-of-task.md](reference/end-of-task.md).

Fix any failures before declaring the task done.
