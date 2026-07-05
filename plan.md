You are building an Agent Skill called "reality-check" that stops coding agents 
from hallucinating files, functions, classes, APIs, dependencies, env vars, or 
architecture. Design it, implement it, and test it end-to-end. Do not just hand 
back a markdown file — build the whole thing and prove it works.

## Step 0 — Check your own conventions first
Before writing anything, check how skills are defined in this environment 
(directory structure, frontmatter fields, how skills get invoked/triggered, 
whether scripts can be bundled and run without loading into context). Don't 
assume the format — verify it against your own docs or existing skills in 
this project.

## Step 1 — Design the skill
Core rule the skill must enforce: never state or code against something in 
the repo (a file, function, class, API, dependency, env var, or architectural 
fact) without having just confirmed it by searching/reading the repo in this 
session. If it can't be confirmed, say so explicitly, state what was searched, 
and stop — never substitute a plausible guess.

Requirements for the SKILL.md itself:
- Write rules as a small number of imperative MUST statements, not a long 
  list of "never assume X" variations that all restate the same idea. 
  Collapse repetition — one governing rule + distinct categories 
  (filesystem, symbols, dependencies/APIs, env vars/config, architecture).
- Name the actual tool calls to use for verification (grep/glob-equivalent 
  search, then read) — don't leave "verify it exists" abstract.
- Give dependencies their own explicit checked step: before ever suggesting 
  a package/library, confirm it's in the actual manifest (package.json, 
  requirements.txt, Cargo.toml, etc.) or is a real, currently-published 
  package — this is a known live risk (hallucinated package names getting 
  squatted by attackers), not just a style nitpick.
- Write a tight trigger description (what the skill does + exactly when to 
  use it) so it actually gets auto-invoked — vague descriptions cause 
  skills to sit unused. Also define an explicit manual-invoke path (slash 
  command or equivalent) in case auto-trigger doesn't fire.
- Include a short "before writing code" checklist: search for existing 
  similar implementations/utilities/tests before creating new ones.
- Include an end-of-task verification report template: files inspected, 
  symbols verified, dependencies checked, utilities reused, remaining 
  unknowns.
- Keep the main file concise. If reference material grows large, split it 
  into a separate file and link to it rather than bloating SKILL.md.

## Step 2 — Add a deterministic backstop
Prompted instructions get ignored under context pressure. Write a small 
script (bundle it with the skill) that scans a completed response/diff for 
referenced file paths, symbol names, and package names, and checks each one 
against the actual repo/manifest/registry. It should flag anything 
referenced but not verifiable. This is the enforcement layer — the skill's 
prompt is the judgment layer, the script is the fact-check layer.

## Step 3 — Build test scenarios
Before declaring this done, construct at least:
- 3 scenarios where the skill SHOULD trigger and catch a real problem 
  (e.g., asked to modify a function that doesn't exist under the name 
  given, asked to add a dependency not in the manifest, asked to describe 
  architecture of a repo it hasn't read yet).
- 2 scenarios where it should NOT block or add unnecessary friction 
  (trivial, already-verified, or purely conversational requests) — to 
  make sure it doesn't become annoying dead weight.

## Step 4 — Run it and report
Actually invoke the skill against these scenarios in a real or scratch 
repo. For each scenario, report: did it trigger correctly, did it verify 
before claiming, did it correctly say "not found" instead of guessing, 
did the backstop script catch anything the prompt missed. Fix and re-run 
anything that fails before calling this done.

## Deliverables
- The skill directory (SKILL.md + any reference files + the backstop script)
- The test scenarios and their actual observed outcomes
- A short summary of anything you had to fix during testing and why
