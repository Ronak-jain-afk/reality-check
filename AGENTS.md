# reality-check

Distributable agent skill that prevents coding agents from hallucinating files, functions, classes, APIs, dependencies, env vars, and architecture.

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Entrypoint — trigger, one governing rule + 5 category rules, before-writing-code checklist, backstop script instructions |
| `reference/end-of-task.md` | Verification report template to append after every task |
| `scripts/verify-diff.py` | Deterministic backstop — scans diffs against filesystem/manifest/registries |
| `plan.md` | Original brief |
| `ADVANCED_PLAN.md` | Full design doc |

## Installation

Place the `SKILL.md`, `reference/`, and `scripts/` directory under your agent skills path (e.g. `~/.agents/skills/reality-check/`).

## Testing

Run the backstop against a sample response:

```bash
python scripts/verify-diff.py \
  --diff <response-file> \
  --manifest package.json \
  --manifest requirements.txt \
  --env-file .env.example \
  --source-dirs src/
```

See `ADVANCED_PLAN.md` for the 5 test scenarios (3 should-trigger, 2 should-not).

## Key design

- Two-layer defense: prompt rules (judgment) + deterministic script (fact-check)
- Stdlib-only backstop — no dependencies
- Registry verification (npm/PyPI) via public API endpoints
- Five category rules each with explicit tool calls (`Glob`, `Grep`, `Read`, `WebFetch`)
