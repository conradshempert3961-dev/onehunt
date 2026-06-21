#!/usr/bin/env node
/**
 * ONEHUNT shim — matches the guide: node server.mjs --login / node server.mjs
 * Wraps FreeDeepseekAPI (server.js) on port 18632 by default.
 */
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);

if (args.includes("--login")) {
  const result = spawnSync("node", ["scripts/deepseek_chrome_auth.js"], {
    cwd: root,
    stdio: "inherit",
  });
  process.exit(result.status ?? 1);
}

process.env.PORT = process.env.PORT || "18632";
process.env.HOST = process.env.HOST || "127.0.0.1";
await import(path.join(root, "server.js"));
