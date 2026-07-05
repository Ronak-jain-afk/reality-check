# reality-check

**Stop coding agents from hallucinating files, functions, classes, APIs, dependencies, env vars, and architecture.**

A two-layer defense:
1. **Prompt rules** (SKILL.md) — trains the model to verify before claiming
2. **Deterministic backstop** (verify-diff.py) — scans diffs against the actual filesystem, project manifests, and package registries

## Quick install

### Via npx skills (recommended)

After pushing to GitHub:

```bash
npx skills add Ronak-jain-afk/reality-check
```

Variants:

```bash
# Install globally (user dir, not per-project)
npx skills add Ronak-jain-afk/reality-check --global

# Install to a specific agent
npx skills add Ronak-jain-afk/reality-check -a claude-code -a opencode

# List what's available before installing
npx skills add Ronak-jain-afk/reality-check --list
```

### Manual install

```bash
cp -r reality-check/ ~/.agents/skills/reality-check/
```

Or symlink if you want to keep it under version control:

```bash
ln -s $(pwd)/reality-check ~/.agents/skills/reality-check
```

## How it works

### Governing rule

> Before stating or coding against any file, function, class, API, dependency, environment variable, or architectural fact, confirm it exists by searching or reading **this repo in the current session**. If unverifiable, say exactly: `Not found — searched for [X]` and **stop**. Never substitute a plausible guess.

### Five category rules

| Category | What it prevents | Verification method |
|----------|-----------------|-------------------|
| **Filesystem** | Claiming files that don't exist | `Glob(pattern)` → `Read(path)` |
| **Symbols** | Referencing functions/classes/types that aren't there | `Grep(pattern)` with language-include filter |
| **Dependencies & APIs** | Suggesting packages not in manifest or registry | `Read(manifest)` + `WebFetch(registry URL)` |
| **Environment & Config** | Using env vars or config keys that aren't documented | `Glob(".env*")` → `Read(path)` |
| **Architecture** | Describing how components connect without reading the code | `Grep("import.*X")` / `Grep("require.*X")` |

### Before-writing-code checklist

Before creating files or making significant edits:
1. `Grep` for existing similar implementations
2. `Glob` utility directories (`utils/`, `helpers/`, `lib/`)
3. `Glob` existing test files
4. Read relevant config files
5. `Grep` for existing types/interfaces

## Backstop script

`scripts/verify-diff.py` is a deterministic, prompt-independent fact-checker. Stdlib only — no dependencies.

```bash
python scripts/verify-diff.py \
  --diff <response-file> \
  --manifest package.json \
  --manifest requirements.txt \
  --env-file .env.example \
  --source-dirs src/
```

It scans for:
- **File paths** — cross-checked against the filesystem
- **Symbol names** — cross-checked against source files
- **Package names** — cross-checked against manifests + npm/PyPI registries
- **Environment variables** — cross-checked against `.env.example` etc.

Output:

```
reality-check verify-diff report:
  ✗ [file] src/auth/middleware.py — file not found
  ✓ [symbol] calculateTotal — found in src/utils.ts:15
  ✗ [package] fake-package-xyz — not in manifest; not found on npm or PyPI
  ---
  SUMMARY: 1 passed, 2 failed
```

## File reference

| File | Purpose |
|------|---------|
| `SKILL.md` | Entrypoint — trigger, rules, checklist, instructions |
| `reference/end-of-task.md` | Verification report template |
| `scripts/verify-diff.py` | Deterministic backstop script |
| `AGENTS.md` | Repo-specific guidance for coding agents |
| `ADVANCED_PLAN.md` | Full design document and test scenarios |

## How to test

Run the backstop against a sample response file:

```bash
python scripts/verify-diff.py \
  --diff test/fixtures/hallucinated-file.txt \
  --manifest test/fixtures/package.json \
  --env-file test/fixtures/.env.example \
  --source-dirs test/fixtures/src/
```

See [ADVANCED_PLAN.md](ADVANCED_PLAN.md) for 5 test scenarios (3 should-trigger, 2 should-not).

## Supported registries

- **npm** — `https://registry.npmjs.org/<package>` (HEAD request)
- **PyPI** — `https://pypi.org/pypi/<package>/json` (HEAD request)

Registry checks are cached per session. Network failures report "unreachable" rather than blocking progress.

## Design principles

- **Two layers**: prompt rules teach the model; the script catches what the model misses under context pressure
- **No dependencies**: the backstop script uses Python stdlib only
- **Conservative**: the script flags potential issues. It's a helper, not a gate — the agent can justify flagged items (e.g., "this symbol comes from Flask, which is in requirements.txt")
- **No fluff**: SKILL.md is 72 lines. Reference material lives in separate files.
