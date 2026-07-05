# Reality-Check Skill — Advanced Plan

## Architecture Overview

```
reality-check/
├── SKILL.md                  # Entrypoint — trigger, rules, workflow, checklist
├── reference/
│   └── end-of-task.md        # Verification report template (keeps SKILL.md concise)
└── scripts/
    └── verify-diff.py        # Deterministic backstop — scans diffs for unverified refs
```

Two-layer defense:
1. **Judgment layer** (SKILL.md prompt rules) — trains the model to verify before claiming
2. **Fact-check layer** (verify-diff.py script) — post-hoc scan catches anything the prompt missed

---

## 1. SKILL.md Design

### Frontmatter

```yaml
---
name: reality-check
description: >
  Prevents coding agents from hallucinating files, functions, classes, APIs,
  dependencies, env vars, or architecture. Use when modifying code, adding
  features, fixing bugs, refactoring, suggesting dependencies, describing
  architecture, or any task that references entities in the repo. Auto-triggers
  on any coding task. Manual invoke with $reality-check.
---
```

### Trigger Description Strategy

- **Auto-trigger keywords** in description: "modifying code", "adding features", "fixing bugs", "refactoring", "suggesting dependencies", "describing architecture"
- **Negative trigger** (DO NOT USE): purely conversational questions, brainstorming without implementation, code review of external code not in repo
- **Manual invoke**: `$reality-check` — shows a quick summary of the rules + offers to run the backstop script

### Core Rules — One Governing Imperative + Five Categories

**Governing rule (MUST):**
> Before stating or coding against any file, function, class, API, dependency, environment variable, or architectural fact, confirm it exists by searching/reading the repo in the current session. If unverifiable, explicitly say "Not found — searched [X]" and stop. Never substitute a plausible guess.

**Five categories (each with a single MUST statement and the specific tool calls):**

| # | Category | MUST rule | Tool calls to use |
|---|----------|-----------|-------------------|
| 1 | **Filesystem** | MUST verify every referenced file path exists via `Glob` or `Read` before reading, editing, or stating it exists. | `Glob(pattern)` then `Read(path)` |
| 2 | **Symbols** | MUST search for every function/class/type/variable name via `Grep` or `Read` before claiming it exists or modifying it. | `Grep(pattern, include="*.{js,ts,py,rs,go}")` |
| 3 | **Dependencies & APIs** | MUST check the project manifest (`package.json`, `requirements.txt`, `Cargo.toml`, `go.mod`, `composer.json`, `Gemfile`, etc.) for any package before suggesting it as a dependency. For new (not yet installed) packages, MUST verify the package exists on the real registry (npm, PyPI, crates.io, etc.) by checking a known-good source — never rely on prior knowledge alone. | `Read(manifest)`, `WebFetch(registry URL)` |
| 4 | **Environment & Config** | MUST read `.env.example`, `wrangler.jsonc`, `docker-compose.yml`, or equivalent config files before referencing any environment variable, secret, or configuration key. | `Glob(".env*")`, `Read(path)` |
| 5 | **Architecture** | MUST trace the actual call/import graph by `Grep`-ing for imports/usages before describing how components connect. Never describe architecture from memory. | `Grep("import.*X")`, `Grep("require.*X")`, `Grep("from X import")` |

### Before-Writing-Code Checklist (in SKILL.md)

Before creating any new file or making significant edits:

1. **Search for existing similar implementations:** `Grep` for keywords related to the feature across the whole project
2. **Check for existing utilities:** `Glob` for utility files (`utils/`, `helpers/`, `lib/`) and read them to find reusable functions
3. **Check for existing tests:** `Glob` for `test_*`, `*_test.*`, `*.test.*`, `*.spec.*` files that test related functionality
4. **Check configuration:** Read relevant config files to understand existing conventions
5. **Check for existing types/interfaces:** `Grep` for type/interface definitions related to the task

### End-of-Task Verification Report Template (in reference/end-of-task.md)

```
## Reality-Check — Verification Report
- Files inspected: [list of files read this session]
- Symbols verified: [list of function/class/type names confirmed via Grep]
- Dependencies checked: [list of packages confirmed in manifest + registry if new]
- Environment vars checked: [list of env vars confirmed in config files]
- Architecture traced: [list of call/import relationships confirmed via Grep]
- Utilities reused: [list of existing utilities reused instead of rewritten]
- Remaining unknowns: [list of anything referenced but not yet verified]
```

The template is stored in `reference/end-of-task.md` and the SKILL.md instructs the model to populate and append it at the end of every task (or at minimum reflect on each item).

---

## 2. Backstop Script Design

**File:** `scripts/verify-diff.py`

### Purpose
A deterministic, prompt-independent fact-checker. After the model produces a response or diff, this script scans the output for references (file paths, symbol names, package names) and cross-checks each against the actual filesystem, manifest, and package registry.

### What It Scans
1. **File paths** — matches patterns like `src/foo/bar.ts`, `./utils/helper.py`, absolute paths
2. **Symbol names** — matches identifiers in code blocks (function definitions, class names, imports, API method calls)
3. **Package names** — matches strings like `npm install foo`, `pip install bar`, `import baz`, `require("qux")`
4. **Environment variables** — matches `process.env.FOO`, `os.getenv("FOO")`, `$FOO`

### What It Checks
| Entity | Check | Source |
|--------|-------|--------|
| File paths | Does the file exist? | `os.path.exists()` / `glob` |
| Symbol names | Is the symbol defined in any source file listed in the manifest? | `Grep` / `ast.parse()` |
| Package names | Is it in the manifest? If not, does it exist on the registry? | `Read(manifest)` + `urllib` to npm/PyPI API |
| Env vars | Is it documented in `.env.example` or equivalent? | `Read(.env.example)` |

### Output Format
```
reality-check verify-diff report:
  ✓ src/main.py — file exists
  ✗ src/nonexistent.py — file not found (referenced in line 42)
  ✓ calculateTotal() — symbol found in src/utils.ts:15
  ✗ bogusFunction() — symbol not found anywhere (referenced in line 78)
  ✓ express — in package.json
  ✗ fake-package-xyz123 — not in package.json; not found on npm (referenced in line 120)
  ✓ DATABASE_URL — in .env.example
  ✗ SECRET_KEY — not in .env.example (referenced in line 55)
  ---
  SUMMARY: 5 passed, 3 failed
```

### Usage
```bash
python .agents/skills/reality-check/scripts/verify-diff.py \
  --diff <path-to-diff-or-response> \
  --manifest package.json \
  --manifest requirements.txt \
  --env-file .env.example \
  --source-dirs src/,lib/
```

The SKILL.md instructs the model to run this script at the end of every task and fix any failures.

### Implementation Notes
- Minimal dependencies: stdlib only (`os`, `re`, `json`, `glob`, `urllib.request`, `sys`, `argparse`)
- Registry checks use public API endpoints (npm: `https://registry.npmjs.org/<package>`, PyPI: `https://pypi.org/pypi/<package>/json`)
- Cache registry responses within a session to avoid rate limiting
- Handle common false positives (test paths, example code that's intentionally fictional)

---

## 3. Test Scenarios

### Should-Trigger Scenarios (3)

**Scenario 1: Hallucinated file path**
- Input: "Modify the authentication logic in `src/auth/middleware.py`"
- The repo has no `src/auth/middleware.py` file
- Expected: Skill blocks or flags the claim, runs `Glob` or `Read`, reports "Not found — searched `src/auth/middleware.py`"
- How to test: Feed the prompt to a model with the skill loaded against a scratch repo without that file

**Scenario 2: Non-existent dependency**
- Input: "Add the `django-hstore` package to requirements.txt and use it"
- `django-hstore` is not in requirements.txt (or similar manifest) — the skill must check the manifest, then check if the package exists on PyPI
- Expected: Skill catches that it's not in the manifest, checks PyPI — reports "Not in manifest; not found on PyPI"

**Scenario 3: Architecture claim without reading**
- Input: "The event system uses a pub/sub pattern with Redis as the broker"
- The repo's actual event code uses a different pattern (e.g., direct callbacks, no Redis)
- Expected: Skill blocks, says "Searched repo for event implementation — no Redis broker found; event system uses callbacks in `src/events.py`"

### Should-Not-Trigger Scenarios (2)

**Scenario 4: Trivial, already-verified request**
- Input: "Fix the typo in the docstring of `calculateTotal` in `src/utils.ts` line 42"
- The session has already read `src/utils.ts` and confirmed `calculateTotal` exists
- Expected: No friction — proceeds normally

**Scenario 5: Purely conversational**
- Input: "What's the difference between SQL and NoSQL databases?"
- No files, symbols, deps, or config are referenced
- Expected: No friction — proceeds normally

---

## 4. Implementation Steps

### Step 1: Create skill directory structure
```bash
mkdir -p /home/ronak/.agents/skills/reality-check/{reference,scripts}
```

### Step 2: Write SKILL.md
- Frontmatter with trigger description
- Governing rule + 5 category rules
- Tool call mappings
- Before-writing-code checklist
- Instructions to run backstop script at end of task
- Reference to `reference/end-of-task.md`
- Manual invocation flow for `$reality-check`

### Step 3: Write reference/end-of-task.md
- Verification report template
- Instructions on how to populate each section

### Step 4: Write scripts/verify-diff.py
- Parse args (diff file, manifests, env files, source dirs)
- Regex scan for file paths, symbol names, package references, env vars
- Cross-check each against filesystem/manifest/registry/config
- Produce structured output with pass/fail per reference
- Summary count

### Step 5: Create test scenarios
- Build a small scratch repo with known contents
- Create test harness script that feeds each scenario to the model and records outcomes
- For the backstop script, create unit tests (or just run it against known inputs)

### Step 6: Test the backstop script
- Run against a diff with real references → verify it correctly passes/fails each
- Run against a clean diff → verify zero false positives
- Run against a diff with unknown package → verify it checks the registry correctly

### Step 7: Test the full skill
- Load the skill in a session
- Feed each scenario
- Record: did the prompt-layer catch it? Did the script catch it? Was there any false positive friction?

### Step 8: Iterate on failures
- Fix anything that didn't work
- Document fixes

---

## 5. Edge Cases & Non-Goals

### Edge Cases to Handle
- **Generated code** (tests, mocks, scaffolding) — these may reference files that don't exist yet; the skill should allow creation after verification that nothing similar exists
- **External resources** (URLs, documentation links) — verify the URL is reachable, but don't block on it
- **Template/boilerplate code** that ships with a framework — allow if the framework is confirmed in the manifest
- **Monorepos with multiple manifests** — check all manifests in the workspace, not just one
- **Multiple languages in one repo** — detect language from file extensions and use the correct registry/manifest convention
- **Registry API failures** (npm/PyPI down) — report "Registry check failed (unreachable), proceeding with caution" rather than blocking progress
- **Dynamic imports** (`import(foo)`) — flag as unchecked, don't try to resolve dynamically

### Non-Goals
- Enforcing code style or formatting (that's linters/formatters)
- Reviewing correctness of logic (that's code review)
- Running tests (that's CI)
- Preventing all mistakes — only preventing hallucinated references
- Replacing the model's general knowledge — only checking claims about THIS repo
