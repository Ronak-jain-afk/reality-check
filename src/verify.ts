import { readdirSync, readFileSync, existsSync, statSync } from "fs";
import { join, relative } from "path";

const BUILTINS = new Set([
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
]);

export interface VerificationResult {
  kind: "file" | "symbol" | "package" | "env";
  name: string;
  ok: boolean;
  message: string;
}

const registryCache = new Map<string, boolean | null>();

async function registryCheck(name: string, registryUrl: string): Promise<boolean | null> {
  const key = `${name}|${registryUrl}`;
  const cached = registryCache.get(key);
  if (cached !== undefined) return cached;

  const url = registryUrl.includes("pypi")
    ? `${registryUrl.replace(/\/$/, "")}/${name}/json`
    : `${registryUrl.replace(/\/$/, "")}/${name}`;

  try {
    const resp = await fetch(url, { method: "HEAD", signal: AbortSignal.timeout(10000) });
    const ok = resp.status === 200;
    registryCache.set(key, ok);
    return ok;
  } catch (e) {
    if ((e as Response)?.status) {
      registryCache.set(key, false);
      return false;
    }
    registryCache.set(key, null);
    return null;
  }
}

function loadManifest(path: string): Record<string, unknown> | unknown[] | null {
  try {
    const content = readFileSync(path, "utf-8");
    return JSON.parse(content);
  } catch {
    return null;
  }
}

function loadEnvFile(path: string): Set<string> | null {
  try {
    const content = readFileSync(path, "utf-8");
    const keys = new Set<string>();
    for (const line of content.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const key = trimmed.split("=")[0]?.trim();
      if (key) keys.add(key);
    }
    return keys;
  } catch {
    return null;
  }
}

function globSourceFiles(sourceDirs: string[]): string[] {
  const files: string[] = [];
  for (const dir of sourceDirs) {
    if (existsSync(dir) && statSync(dir).isDirectory()) {
      const entries = readdirSync(dir, { recursive: true }) as string[];
      for (const entry of entries) {
        const full = join(dir, entry);
        if (statSync(full).isFile()) files.push(full);
      }
    }
  }
  return files;
}

function addName(seen: Set<string>, name: string): void {
  const n = name.trim().replace(/["']/g, "");
  if (n && n.length > 1 && !BUILTINS.has(n)) seen.add(n);
}

function extractSymbolsFromLine(line: string, seen: Set<string>): void {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith("#") || trimmed.startsWith("//")) return;

  let m: RegExpExecArray | null;

  const defRe = /(?:def|fn|function|func)\s+(\w+)/g;
  while ((m = defRe.exec(trimmed)) !== null) addName(seen, m[1]);

  const classRe = /class\s+(\w+)/g;
  while ((m = classRe.exec(trimmed)) !== null) addName(seen, m[1]);

  const methodRe = /\.(\w+)\s*\(/g;
  while ((m = methodRe.exec(trimmed)) !== null) addName(seen, m[1]);

  const callRe = /(?<!\.|\w)([a-z_]\w*)\s*\(/g;
  while ((m = callRe.exec(trimmed)) !== null) addName(seen, m[1]);

  const fromImport = trimmed.match(/^from\s+[\w.]+\s+import\s+(.+)$/);
  if (fromImport) {
    for (const part of fromImport[1].split(",")) {
      addName(seen, part.trim().split(" as ")[0].trim());
    }
    return;
  }

  const importMatch = trimmed.match(/^import\s+([\w.]+)/);
  if (importMatch) {
    addName(seen, importMatch[1].split(".").pop()!);
    return;
  }

  const requireRe = /require\(\s*["']([^"']+)["']\s*\)/g;
  while ((m = requireRe.exec(trimmed)) !== null) addName(seen, m[1].split("/").pop()!);

  const dynamicImportRe = /import\s*\(\s*["']([^"']+)["']\s*\)/g;
  while ((m = dynamicImportRe.exec(trimmed)) !== null) addName(seen, m[1].split("/").pop()!);
}

export function scanFilePaths(text: string): string[] {
  const paths = new Set<string>();
  const re = /`?\.?\/?[\w.-]+\/(?:[\w.-]+\/)*[\w@][\w.\-~]*\.[a-zA-Z]+`?/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    const p = m[0].replace(/^`|`$/g, "");
    if (p && !p.startsWith("http://") && !p.startsWith("https://") && !p.startsWith("#")) {
      paths.add(p);
    }
  }
  return [...paths].sort();
}

export function scanSymbols(text: string): string[] {
  const symbols = new Set<string>();
  const blockRe = /```\w*\n([\s\S]*?)```/g;
  let m: RegExpExecArray | null;
  while ((m = blockRe.exec(text)) !== null) {
    for (const line of m[1].split("\n")) extractSymbolsFromLine(line, symbols);
  }
  const inlineRe = /`([^`]+)`/g;
  while ((m = inlineRe.exec(text)) !== null) extractSymbolsFromLine(m[1], symbols);
  return [...symbols].sort();
}

export function scanPackages(text: string): string[] {
  const pkgs = new Set<string>();
  const installRe = /(?:pip|npm|yarn|cargo|go|nuget|gem|brew|apt)\s+(?:install|add|require)\s+([@\w\-_.!]+)/gi;
  let m: RegExpExecArray | null;
  while ((m = installRe.exec(text)) !== null) {
    pkgs.add(m[1].toLowerCase().replace(/^@/, ""));
  }
  const proseRe = /(?:package|library|module|crate|gem)\s+['"]?([\w\-_.]+)['"]?(?:\s+(?:to|in))/gi;
  while ((m = proseRe.exec(text)) !== null) pkgs.add(m[1].toLowerCase());
  return [...pkgs].sort();
}

export function scanEnvVars(text: string): string[] {
  const envs = new Set<string>();
  let m: RegExpExecArray | null;

  const accessRe = /(?:process\.env|os\.getenv|os\.environ(?:\[|\.get)\s*\(\s*["'])([\w_]+)/g;
  while ((m = accessRe.exec(text)) !== null) envs.add(m[1]);

  const shellRe = /\$([A-Z_][A-Z0-9_]*)/g;
  while ((m = shellRe.exec(text)) !== null) envs.add(m[1]);

  const templateRe = /\benv\.([A-Z_][A-Z0-9_]*)/g;
  while ((m = templateRe.exec(text)) !== null) envs.add(m[1]);

  return [...envs].sort();
}

export async function verifyFilePaths(paths: string[], sourceDirs: string[]): Promise<VerificationResult[]> {
  return paths.map((p) => {
    let exists = existsSync(p);
    if (!exists && sourceDirs.length > 0) {
      for (const sd of sourceDirs) {
        if (existsSync(join(sd, p))) { exists = true; break; }
      }
    }
    return { kind: "file", name: p, ok: exists, message: exists ? "file exists" : "file not found" };
  });
}

export async function verifySymbols(symbols: string[], sourceDirs: string[], diffPath = ""): Promise<VerificationResult[]> {
  const absDiff = diffPath ? join(process.cwd(), diffPath) : "";
  const sourceFiles = globSourceFiles(sourceDirs).filter((f) => f !== absDiff);

  return symbols.map((sym) => {
    for (const sf of sourceFiles) {
      try {
        const content = readFileSync(sf, "utf-8");
        const wordRe = new RegExp(`\\b${escapeRegex(sym)}\\b`);
        if (!wordRe.test(content)) continue;
        const lines = content.split("\n");
        for (let i = 0; i < lines.length; i++) {
          const line = lines[i];
          const defRe = new RegExp(`(?:def|class|fn|function|func|const|let|var|type|interface|trait)\\s+${escapeRegex(sym)}\\b`);
          const propRe = new RegExp(`\\.${escapeRegex(sym)}\\s*=`);
          const importRe = new RegExp(`^import\\s+.*\\b${escapeRegex(sym)}\\b`);
          const assignRe = new RegExp(`\\b${escapeRegex(sym)}\\s*[:=]`);
          if (defRe.test(line) || propRe.test(line) || importRe.test(line) || assignRe.test(line)) {
            return { kind: "symbol", name: sym, ok: true, message: `found in ${relative(process.cwd(), sf)}:${i + 1}` };
          }
        }
        return { kind: "symbol", name: sym, ok: true, message: `found in ${relative(process.cwd(), sf)} (referenced, definition unclear)` };
      } catch { continue; }
    }
    return { kind: "symbol", name: sym, ok: false, message: "symbol not found in source files" };
  });
}

export async function verifyPackages(packages: string[], manifestPaths: string[]): Promise<VerificationResult[]> {
  const results: VerificationResult[] = [];
  for (const pkg of packages) {
    let inManifest = false;
    let manifestName = "";

    for (const mp of manifestPaths) {
      const data = loadManifest(mp);
      if (!data) continue;

      if (Array.isArray(data)) {
        for (const entry of data) {
          const entryName = (entry as string).split("==")[0].split(">=")[0].split("<")[0].trim().toLowerCase();
          if (entryName === pkg) { inManifest = true; manifestName = mp; break; }
        }
      } else if (typeof data === "object") {
        for (const section of ["dependencies", "devDependencies", "peerDependencies"]) {
          const deps = (data as Record<string, unknown>)[section] as Record<string, string> | undefined;
          if (deps && (deps[pkg] || deps[pkg.replace(/-/g, "_")])) { inManifest = true; manifestName = mp; break; }
        }
      }
      if (inManifest) break;
    }

    if (inManifest) {
      results.push({ kind: "package", name: pkg, ok: true, message: `in ${manifestName}` });
    } else {
      const npmResult = await registryCheck(pkg, "https://registry.npmjs.org/");
      if (npmResult === true) {
        results.push({ kind: "package", name: pkg, ok: true, message: "not in manifest; verified on npm" });
      } else {
        const pypiResult = await registryCheck(pkg, "https://pypi.org/pypi/");
        if (pypiResult === true) {
          results.push({ kind: "package", name: pkg, ok: true, message: "not in manifest; verified on PyPI" });
        } else if (pypiResult === null) {
          results.push({ kind: "package", name: pkg, ok: false, message: "not in manifest; registry check failed (unreachable)" });
        } else {
          results.push({ kind: "package", name: pkg, ok: false, message: "not in manifest; not found on npm or PyPI" });
        }
      }
    }
  }
  return results;
}

export async function verifyEnvVars(envVars: string[], envFilePaths: string[]): Promise<VerificationResult[]> {
  return envVars.map((v) => {
    for (const ef of envFilePaths) {
      const keys = loadEnvFile(ef);
      if (keys?.has(v)) return { kind: "env", name: v, ok: true, message: `documented in ${ef}` };
    }
    return { kind: "env", name: v, ok: false, message: "not found in env files" };
  });
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export async function verifyAll(
  text: string,
  sourceDirs: string[],
  manifestPaths: string[],
  envFilePaths: string[],
): Promise<VerificationResult[]> {
  const results: VerificationResult[] = [];

  const fileRefs = scanFilePaths(text);
  const symbolRefs = scanSymbols(text);
  const packageRefs = scanPackages(text);
  const envRefs = scanEnvVars(text);

  results.push(...await verifyFilePaths(fileRefs, sourceDirs));
  results.push(...await verifySymbols(symbolRefs, sourceDirs));
  results.push(...await verifyPackages(packageRefs, manifestPaths));
  results.push(...await verifyEnvVars(envRefs, envFilePaths));

  return results;
}
