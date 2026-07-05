#!/usr/bin/env python3
"""verify-diff.py — deterministic backstop for reality-check skill.

Scans a diff/response file for referenced file paths, symbol names, package
names, and environment variables, then cross-checks each against the actual
filesystem, project manifests, and package registries (npm, PyPI).

Usage:
  python verify-diff.py --diff <file> \
    --manifest package.json \
    --manifest requirements.txt \
    --env-file .env.example \
    --source-dirs src/,lib/

Stdlib only — no dependencies.
"""

import argparse
import glob as glob_module
import json
import os
import re
import sys
import urllib.request
import urllib.error

# ── caches ──────────────────────────────────────────────────────────────
_REGISTRY_CACHE: dict[str, bool | None] = {}
_MANIFEST_CACHE: dict[str, dict | list | None] = {}
_ENV_CACHE: dict[str, set[str] | None] = {}


# ── helpers ─────────────────────────────────────────────────────────────

_BUILTINS = frozenset({
    "print", "len", "str", "int", "float", "bool", "list", "dict", "set",
    "tuple", "range", "enumerate", "zip", "map", "filter", "sorted",
    "reversed", "open", "input", "type", "isinstance", "hasattr",
    "getattr", "setattr", "delattr", "super", "object", "property",
    "staticmethod", "classmethod", "self", "cls", "None", "True", "False",
    "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
    "RuntimeError", "StopIteration", "ImportError", "ModuleNotFoundError",
    "OSError", "FileNotFoundError", "AttributeError", "NameError",
    "Any", "Optional", "List", "Dict", "Set", "Tuple", "Callable",
    "Iterable", "Iterator", "Generator", "TypeVar", "Generic", "Protocol",
    "await", "async", "yield", "return", "if", "else", "elif", "for",
    "while", "try", "except", "finally", "with", "as", "import", "from",
    "def", "class", "pass", "raise", "assert", "del", "global", "nonlocal",
    "lambda", "match", "case", "break", "continue",
    "app", "req", "res", "err", "ctx", "env",
    "toString", "mapStateToProps", "mapDispatchToProps",
})


def read_file(path: str) -> str | None:
    try:
        with open(path) as f:
            return f.read()
    except (FileNotFoundError, IsADirectoryError):
        return None


def set_name(seen: set[str], name: str) -> None:
    n = name.strip().strip('"').strip("'")
    if n and len(n) > 1 and n not in _BUILTINS:
        seen.add(n)


def registry_check(name: str, registry_url: str) -> bool | None:
    """Check if a package exists on a registry. Returns True/False/None on error."""
    key = (name, registry_url)
    if key in _REGISTRY_CACHE:
        return _REGISTRY_CACHE[key]

    # PyPI needs /json suffix; npm works with trailing slash
    if "pypi" in registry_url.lower():
        url = f"{registry_url.rstrip('/')}/{name}/json"
    else:
        url = f"{registry_url.rstrip('/')}/{name}"

    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "reality-check/1.0")
        resp = urllib.request.urlopen(req, timeout=10)
        ok = resp.status == 200
    except urllib.error.HTTPError:
        ok = False
    except (urllib.error.URLError, OSError):
        ok = None  # unreachable
    _REGISTRY_CACHE[key] = ok
    return ok


def load_manifest(path: str) -> dict | list | None:
    if path in _MANIFEST_CACHE:
        return _MANIFEST_CACHE[path]
    content = read_file(path)
    if content is None:
        _MANIFEST_CACHE[path] = None
        return None
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = None
    _MANIFEST_CACHE[path] = data
    return data


def load_env_file(path: str) -> set[str] | None:
    if path in _ENV_CACHE:
        return _ENV_CACHE[path]
    content = read_file(path)
    if content is None:
        _ENV_CACHE[path] = None
        return None
    keys: set[str] = set()
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            keys.add(key)
    _ENV_CACHE[path] = keys
    return keys


# ── scanners ────────────────────────────────────────────────────────────

def scan_file_paths(text: str) -> set[str]:
    """Find likely file paths (relative, absolute, ./ prefix)."""
    paths: set[str] = set()
    for m in re.finditer(
        r"(?:"                                 # non-capture group for prefixes
        r"(?:`|\"|'|\(|\[|:|\s)"               # boundary before path
        r")?"
        r"(\.?/?[\w.-]+/"                       # at least one dir component
        r"(?:[\w.-]+/)*"                        # more dirs
        r"[\w@][\w.\-~]*\.[a-zA-Z]+)"           # filename with extension
        r"(?:`|\"|'|\)|\]|,|;|\s|\.(?:\s|$))?", # boundary after
        text,
    ):
        raw = m.group(1)
        p = raw.rstrip(".,;`'\"")
        if p and not p.startswith(("http://", "https://", "#")):
            paths.add(p)
    return paths


def scan_symbols(text: str) -> set[str]:
    """Find likely symbol names in code blocks / inline code."""
    symbols: set[str] = set()

    # code blocks
    for m in re.finditer(r"```\w*\n(.*?)```", text, re.DOTALL):
        for line in m.group(1).splitlines():
            _extract_symbols_from_line(line, symbols)

    # inline code like `foo()` or `Foo.bar()`
    for m in re.finditer(r"`([^`]+)`", text):
        _extract_symbols_from_line(m.group(1), symbols)

    return symbols


def _extract_symbols_from_line(line: str, seen: set[str]) -> None:
    """Pull function/class/method names from a single line of code."""
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("//"):
        return

    # function/method definitions
    for m in re.finditer(r"(?:def|fn|function|func)\s+(\w+)", line):
        set_name(seen, m.group(1))

    # class definitions
    for m in re.finditer(r"class\s+(\w+)", line):
        set_name(seen, m.group(1))

    # method calls: foo.bar() → bar
    for m in re.finditer(r"\.(\w+)\s*\(", line):
        set_name(seen, m.group(1))

    # top-level calls: bar(
    for m in re.finditer(r"(?<!\.|\w)([a-z_]\w*)\s*\(", line):
        set_name(seen, m.group(1))

    # from X import Y1, Y2 → capture Y1, Y2 as symbols
    from_import = re.match(r"from\s+[\w.]+\s+import\s+(.+)$", line)
    if from_import:
        for part in from_import.group(1).split(","):
            part = part.strip().split(" as ")[0].strip()
            set_name(seen, part)
        return  # don't also match the module path below

    # import X (top-level, not preceded by 'from')
    import_match = re.match(r"import\s+([\w.]+)", line)
    if import_match:
        mod = import_match.group(1)
        # only capture the last component as symbol
        set_name(seen, mod.split(".")[-1])
        return

    # require / dynamic import
    for m in re.finditer(r"require\(\s*[\"']([^\"']+)[\"']\s*\)", line):
        set_name(seen, m.group(1).split("/")[-1])

    for m in re.finditer(r"import\s*\(\s*[\"']([^\"']+)[\"']\s*\)", line):
        set_name(seen, m.group(1).split("/")[-1])


def scan_packages(text: str) -> set[str]:
    """Find package names from install/import commands."""
    pkgs: set[str] = set()

    # pip install / npm install / cargo add etc.
    for m in re.finditer(
        r"(?:pip|npm|yarn|cargo|go|nuget|gem|brew|apt)\s+"
        r"(?:install|add|require)\s+"
        r"([@\w\-_.!]+)",
        text,
        re.IGNORECASE,
    ):
        raw = m.group(1).lower().lstrip("@")
        pkgs.add(raw)

    # add-to-project / package references in prose: "add the foo package"
    for m in re.finditer(
        r"(?:package|library|module|crate|gem)\s+"
        r"['\"]?([\w\-_.]+)['\"]?(?:\s+(?:to|in))",
        text,
        re.IGNORECASE,
    ):
        pkgs.add(m.group(1).lower())

    return pkgs


def scan_env_vars(text: str) -> set[str]:
    """Find env var references."""
    envs: set[str] = set()

    # process.env.FOO, os.getenv("FOO"), os.environ["FOO"]
    for m in re.finditer(
        r"(?:process\.env|os\.getenv|os\.environ(?:\[|\.get)\s*"
        r"\(\s*[\"'])([\w_]+)",
        text,
    ):
        envs.add(m.group(1))

    # $FOO, ${FOO} in shell/docker context
    for m in re.finditer(r"\$([A-Z_][A-Z0-9_]*)", text):
        envs.add(m.group(1))

    # {{ env.FOO }} template references
    for m in re.finditer(r"\benv\.([A-Z_][A-Z0-9_]*)", text):
        envs.add(m.group(1))

    return envs


# ── verifiers ───────────────────────────────────────────────────────────

def verify_file_paths(
    paths: set[str], source_dirs: list[str]
) -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []
    for p in sorted(paths):
        exists = os.path.exists(p)
        if not exists and source_dirs:
            for sd in source_dirs:
                candidate = os.path.join(sd, p)
                if os.path.exists(candidate):
                    exists = True
                    break
        if exists:
            results.append((p, True, "file exists"))
        else:
            results.append((p, False, "file not found"))
    return results


def verify_symbols(
    symbols: set[str], source_dirs: list[str], diff_path: str = ""
) -> list[tuple[str, bool, str]]:
    """Check if a symbol appears in any source file (excluding the diff itself)."""
    results: list[tuple[str, bool, str]] = []
    abs_diff = os.path.abspath(diff_path) if diff_path else ""
    source_files: list[str] = []
    for sd in source_dirs:
        if os.path.isdir(sd):
            for f in glob_module.glob(f"{sd}/**/*.*", recursive=True):
                if os.path.abspath(f) != abs_diff:
                    source_files.append(f)

    for sym in sorted(symbols):
        found = False
        location = ""
        for sf in source_files:
            content = read_file(sf)
            if content and re.search(rf"\b{re.escape(sym)}\b", content):
                # try to find the definition line
                for i, line in enumerate(content.splitlines(), 1):
                    if (
                        re.search(
                            rf"(?:def|class|fn|function|func|const|let|var|type|interface|trait)\s+{re.escape(sym)}\b",
                            line,
                        )
                        or re.search(rf"\.{re.escape(sym)}\s*=", line)
                        or re.search(
                            rf"^import\s+.*\b{re.escape(sym)}\b", line
                        )
                        or re.search(
                            rf"\b{re.escape(sym)}\s*[:=]", line
                        )
                    ):
                        found = True
                        location = f"{sf}:{i}"
                        break
                if not found:
                    # broader match
                    found = True
                    location = f"{sf} (referenced, definition unclear)"
        if found:
            results.append((sym, True, f"found in {location}"))
        else:
            results.append((sym, False, "symbol not found"))
    return results


def verify_packages(
    packages: set[str],
    manifest_paths: list[str],
) -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []
    for pkg in sorted(packages):
        in_manifest = False
        manifest_name = ""

        for mp in manifest_paths:
            data = load_manifest(mp)
            if data is None:
                continue
            # npm: dependencies / devDependencies
            if isinstance(data, dict):
                for section in (
                    "dependencies",
                    "devDependencies",
                    "peerDependencies",
                ):
                    deps = data.get(section, {})
                    if pkg in deps or pkg in deps or pkg.replace("-", "_") in deps:
                        in_manifest = True
                        manifest_name = mp
                        break
                # Python: requirements.txt → list of strings
            elif isinstance(data, list):
                for entry in data:
                    entry_name = (
                        entry.split("==")[0]
                        .split(">=")[0]
                        .split("<")[0]
                        .strip()
                        .lower()
                    )
                    if entry_name == pkg:
                        in_manifest = True
                        manifest_name = mp
                        break

            if in_manifest:
                break

        if in_manifest:
            results.append(
                (pkg, True, f"in {manifest_name}")
            )
        else:
            # check registries
            npm_result = registry_check(pkg, "https://registry.npmjs.org/")
            if npm_result is True:
                results.append((pkg, True, "not in manifest; verified on npm"))
            elif npm_result is None:
                pypi_result = registry_check(
                    pkg, "https://pypi.org/pypi/"
                )
                if pypi_result is True:
                    results.append(
                        (pkg, True, "not in manifest; verified on PyPI")
                    )
                elif pypi_result is None:
                    results.append(
                        (
                            pkg,
                            False,
                            "not in manifest; registry check failed (unreachable)",
                        )
                    )
                else:
                    results.append(
                        (
                            pkg,
                            False,
                            "not in manifest; not found on npm or PyPI",
                        )
                    )
            else:
                pypi_result = registry_check(pkg, "https://pypi.org/pypi/")
                if pypi_result is True:
                    results.append(
                        (pkg, True, "not in manifest; verified on PyPI")
                    )
                elif pypi_result is None:
                    results.append(
                        (
                            pkg,
                            False,
                            "not in manifest; registry check failed (unreachable)",
                        )
                    )
                else:
                    results.append(
                        (
                            pkg,
                            False,
                            "not in manifest; not found on npm or PyPI",
                        )
                    )
    return results


def verify_env_vars(
    env_vars: set[str], env_file_paths: list[str]
) -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []
    for var in sorted(env_vars):
        found = False
        source = ""
        for ef in env_file_paths:
            keys = load_env_file(ef)
            if keys and var in keys:
                found = True
                source = ef
                break
        if found:
            results.append((var, True, f"documented in {source}"))
        else:
            results.append((var, False, "not found in env files"))
    return results


# ── report ──────────────────────────────────────────────────────────────

def print_report(
    file_results: list[tuple[str, bool, str]],
    symbol_results: list[tuple[str, bool, str]],
    package_results: list[tuple[str, bool, str]],
    env_results: list[tuple[str, bool, str]],
) -> None:
    passed = 0
    failed = 0

    def emit(kind: str, name: str, ok: bool, msg: str) -> None:
        nonlocal passed, failed
        icon = "✓" if ok else "✗"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"  {icon} [{kind}] {name} — {msg}")

    print("reality-check verify-diff report:")
    for name, ok, msg in file_results:
        emit("file", name, ok, msg)
    for name, ok, msg in symbol_results:
        emit("symbol", name, ok, msg)
    for name, ok, msg in package_results:
        emit("package", name, ok, msg)
    for name, ok, msg in env_results:
        emit("env", name, ok, msg)

    print(f"  ---\n  SUMMARY: {passed} passed, {failed} failed")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="reality-check backstop — verify references in a diff/response"
    )
    p.add_argument("--diff", required=True, help="Path to the diff or response file")
    p.add_argument(
        "--manifest",
        action="append",
        default=[],
        help="Path to a manifest file (package.json, requirements.txt, etc.)",
    )
    p.add_argument(
        "--env-file",
        action="append",
        default=[],
        help="Path to an env config file (.env.example, etc.)",
    )
    p.add_argument(
        "--source-dirs",
        default="",
        help="Comma-separated source directories to scan (src/,lib/)",
    )
    args = p.parse_args()

    content = read_file(args.diff)
    if content is None:
        print(f"Error: cannot read {args.diff}", file=sys.stderr)
        sys.exit(1)

    src_dirs = [d.strip() for d in args.source_dirs.split(",") if d.strip()]

    file_refs = scan_file_paths(content)
    symbol_refs = scan_symbols(content)
    package_refs = scan_packages(content)
    env_refs = scan_env_vars(content)

    file_results = verify_file_paths(file_refs, src_dirs)
    symbol_results = verify_symbols(symbol_refs, src_dirs, args.diff)
    package_results = verify_packages(package_refs, args.manifest)
    env_results = verify_env_vars(env_refs, args.env_file)

    print_report(file_results, symbol_results, package_results, env_results)
