# Reality-Check — Verification Report Template

Copy and populate this at the end of every task. Remove lines that don't apply.

```
## Reality-Check Verification Report
- Files inspected: [path, path, ...]
- Symbols verified: [name → confirmed in file:line, ...]
- Dependencies checked: [name → in manifest / registry confirmed, ...]
- Environment vars checked: [name → in config file, ...]
- Architecture traced: [relationship → confirmed via Grep, ...]
- Utilities reused: [existing util reused instead of rewriting: location]
- Remaining unknowns: [anything referenced but not yet verified]
```

## Instructions

- **Files inspected**: list every file `Read` this session that was relevant
- **Symbols verified**: for each function/class/type referenced, note which file confirmed it
- **Dependencies checked**: for each package, note if it was in the manifest or verified on registry
- **Environment vars checked**: for each env var, note which config file documented it
- **Architecture traced**: for each claim about how parts connect, note the import/call grep that confirmed it
- **Utilities reused**: note any existing utility you reused instead of writing from scratch
- **Remaining unknowns**: if something was referenced but couldn't be verified, *this is a bug* — list it here so the backstop script catches it
