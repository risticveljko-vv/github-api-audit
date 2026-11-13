// Day 2: reproduce each lead with a plain curl request (confirmation rule, step 1).
//
// Usage:  node --env-file=.env scripts/day2-repro.mjs runs/leads.json         # sends one GET per lead to api.github.com
//         node scripts/day2-repro.mjs runs/leads.json --dry                    # prints the curl lines, sends nothing
//
// runs/leads.json is written after Run 1 by hand: [{"id": "E3-1", "why": "...", "path": "/repos/o/r/..."}, ...].
// Paths are relative to https://api.github.com and must start with "/". GET only, one request at a time, under
// 30 a minute. The token reaches curl on stdin (-H @-), so it never appears in argv, the shell history or a saved
// file. Each lead saves <id>.body.json and <id>.headers.txt (response headers only) to runs/day2-<UTC stamp>/, plus
// repro.json with the status and the curl line, token shown as $GITHUB_AUDIT_TOKEN. runs/ is git-ignored.
import { spawnSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { setTimeout as sleep } from "node:timers/promises";

const LIVE = "https://api.github.com";
const HEADERS = ["Accept: application/vnd.github+json", "X-GitHub-Api-Version: 2026-03-10",
  "User-Agent: github-api-audit (risticveljko-vv)"];
const file = process.argv[2];
const dry = process.argv.includes("--dry");
if (!file || file.startsWith("--")) { console.error("usage: day2-repro.mjs <leads.json> [--dry]"); process.exit(2); }
const leads = JSON.parse(readFileSync(file, "utf8"));
for (const l of leads) {
  if (!/^[A-Za-z0-9-]+$/.test(l.id)) throw new Error(`bad lead id: ${l.id}`);
  if (!l.path?.startsWith("/")) throw new Error(`lead ${l.id}: path must start with /`);
}

const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
const out = `runs/day2-${stamp}`;
if (!dry) mkdirSync(out, { recursive: true });
const rows = [];
for (const { id, why, path } of leads) {
  const shown = `curl -sS -H "Authorization: Bearer $GITHUB_AUDIT_TOKEN" ${HEADERS.map(h => `-H "${h}"`).join(" ")} "${LIVE}${path}"`;
  if (dry) { console.log(`${id}: ${shown}`); continue; }
  const key = process.env.GITHUB_AUDIT_TOKEN;
  if (!key) throw new Error("GITHUB_AUDIT_TOKEN missing from .env");
  await sleep(2100); // under 30 a minute
  const r = spawnSync("curl", ["-sS", "-H", "@-", ...HEADERS.flatMap(h => ["-H", h]), "-o", `${out}/${id}.body.json`,
    "-w", "%{http_code}", "-D", `${out}/${id}.headers.txt`, LIVE + path], { input: `Authorization: Bearer ${key}\n`, encoding: "utf8" });
  const status = r.stdout.trim();
  rows.push({ id, why, status, curl: shown, at: new Date().toISOString() });
  console.log(`${id}  HTTP ${status}  ${why}`);
}
if (!dry) writeFileSync(`${out}/repro.json`, JSON.stringify(rows, null, 2) + "\n");
