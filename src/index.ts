import type { Plugin } from "@opencode-ai/plugin";
import { tool } from "@opencode-ai/plugin";
import { verifyAll } from "./verify.js";

export const RealityCheckPlugin: Plugin = async () => {
  return {
    tool: {
      verify_references: tool({
        description:
          "Scan text (a response, diff, or code snippet) for references to files, symbols, packages, and env vars, then verify each against the actual project filesystem, manifests, and package registries. Call this before claiming something exists in the repo.",
        args: {
          text: tool.schema
            .string()
            .describe("The text or code to scan for references"),
          manifest: tool.schema
            .string()
            .optional()
            .describe(
              "Comma-separated paths to manifest files (package.json, requirements.txt)",
            ),
          env_file: tool.schema
            .string()
            .optional()
            .describe("Comma-separated paths to env config files (.env.example)"),
          source_dirs: tool.schema
            .string()
            .optional()
            .describe("Comma-separated source directories (src/,lib/)"),
        },
        async execute(args) {
          const sourceDirs = (
            args.source_dirs || "src/,lib/"
          )
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
          const manifestPaths = (
            args.manifest || "package.json"
          )
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
          const envFilePaths = (
            args.env_file || ".env.example"
          )
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);

          const results = await verifyAll(
            args.text,
            sourceDirs,
            manifestPaths,
            envFilePaths,
          );

          let passed = 0;
          let failed = 0;
          const lines: string[] = [];
          for (const r of results) {
            if (r.ok) passed++;
            else failed++;
            lines.push(
              `  ${r.ok ? "✓" : "✗"} [${r.kind}] ${r.name} — ${r.message}`,
            );
          }

          return (
            "reality-check verification report:\n" +
            lines.join("\n") +
            `\n  ---\n  SUMMARY: ${passed} passed, ${failed} failed`
          );
        },
      }),
    },

    "experimental.session.compacting": async (_input, output) => {
      output.context.push(`## Reality-Check Rules (always active)

You MUST verify every reference before claiming it exists in the repo:

1. **Filesystem** — use Glob/Read to confirm file paths exist before editing
2. **Symbols** — use Grep to confirm function/class/type names before modifying
3. **Dependencies** — check manifest files before suggesting packages; verify unknown packages on the registry
4. **Environment** — read .env* files before referencing env vars or config keys
5. **Architecture** — grep for actual imports/usage before describing how components connect

If unverifiable, say exactly "Not found — searched for [X]" and stop. Never guess.`);
    },
  };
};
