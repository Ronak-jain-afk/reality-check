# reality-check

**Stop coding agents from hallucinating files, functions, classes, APIs, dependencies, env vars, and architecture.**

A two-layer defense:
1. **Rules injected into every session** (always active, never on-demand)
2. **`verify_references` tool** — the agent can call it to check any claim against the actual filesystem, manifests, and package registries

## Install as OpenCode plugin (recommended)

The plugin is loaded at startup and stays active for every session.

Add to `opencode.json`:

```json
{
  "plugin": ["reality-check"]
}
```

Or pin a version:

```json
{
  "plugin": ["reality-check@0.1.0"]
}
```

OpenCode auto-installs npm plugins using Bun on startup. No manual download needed.

### Install as agent skill (alternative)

```bash
npx skills add Ronak-jain-afk/reality-check
```

### Manual install

```bash
cp -r reality-check/ ~/.agents/skills/reality-check/
```

## What it does

The plugin injects these rules into every session's context and provides a `verify_references` tool the agent can call at any time.

### Governing rule

> Before stating or coding against any file, function, class, API, dependency, environment variable, or architectural fact, confirm it exists by searching or reading **this repo in the current session**. If unverifiable, say exactly: `Not found — searched for [X]` and **stop**. Never substitute a plausible guess.

### Five category rules

| Category | What it prevents | Verification method |
|----------|-----------------|-------------------|
| **Filesystem** | Claiming files that don't exist | `Glob(pattern)` → `Read(path)` |
| **Symbols** | Referencing functions/classes/types that aren't there | `Grep(pattern)` |
| **Dependencies & APIs** | Suggesting packages not in manifest or registry | `Read(manifest)` + registry check |
| **Environment & Config** | Using env vars or config keys that aren't documented | `Glob(".env*")` → `Read(path)` |
| **Architecture** | Describing how components connect without reading code | `Grep("import.*X")` |

### Custom tool: `verify_references`

The agent calls this to check text against the actual project:

```
verify_references(
  text: "Modify src/auth/middleware.py to add rate limiting",
  manifest: "package.json,requirements.txt",
  env_file: ".env.example",
  source_dirs: "src/,lib/"
)
```

Output:

```
reality-check verification report:
  ✗ [file] src/auth/middleware.py — file not found
  ✓ [symbol] calculateTotal — found in src/utils.ts:15
  ✗ [package] fake-package-xyz — not in manifest; not found on npm or PyPI
  ---
  SUMMARY: 1 passed, 2 failed
```

## Backstop script (standalone)

`scripts/verify-diff.py` is the same verification logic as a standalone Python script. Stdlib only — no dependencies.

```bash
python scripts/verify-diff.py \
  --diff <response-file> \
  --manifest package.json \
  --manifest requirements.txt \
  --env-file .env.example \
  --source-dirs src/
```

## File reference

| File | Purpose |
|------|---------|
| `src/index.ts` | Plugin entry point — injects rules, registers `verify_references` tool |
| `src/verify.ts` | Verification logic (file, symbol, package, env scanning) |
| `scripts/verify-diff.py` | Same logic as standalone Python script |
| `SKILL.md` | Agent skill entrypoint (for `npx skills add` installs) |

## Build from source

```bash
npm install
npm run build
```

Published to npm. To publish your own fork:

```bash
npm login
npm publish
```

## Design

- **Always active**: loaded at startup as a plugin, never on-demand like a skill
- **Compaction-safe**: rules are re-injected on session compaction
- **No dependencies**: the verification tool uses Node.js built-in APIs
- **Conservative**: flags potential issues; the agent can justify flagged items
