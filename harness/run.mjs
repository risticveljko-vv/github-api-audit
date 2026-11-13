// Usage: node --env-file=.env harness/run.mjs live     (sends GET requests to api.github.com; Veljko's go only)
//        node harness/run.mjs mock                     (local Prism mock; sends nothing to GitHub)
//
// Tests every frame.csv row with status "test": GET only, one request at a time, at most 30 a minute.
// Three guards: --include-method GET, --include-operation-id per frame row, and harness/hooks.py, which
// refuses any non-GET request and any operation outside the frame before it is sent.
import { spawn, spawnSync } from "node:child_process";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { setTimeout as sleep } from "node:timers/promises";

const mode = process.argv[2];
if (!["mock", "live"].includes(mode)) { console.error("mode: mock|live"); process.exit(2); }
const LIVE = "https://api.github.com";
const MOCK = "http://127.0.0.1:4010";
const base = mode === "live" ? LIVE : MOCK;
const SPEC = "spec/api.github.com.2026-03-10.json";
const API_VERSION = "2026-03-10";
// Filled in at setup (RUNSHEET.md step 1) and recorded in SETUP.md. Not secrets.
const OWNER = "risticveljko-vv", REPO = "api-audit-test", TAG = "v0.0.1";
const ISSUE = "1", PULL = "2";

const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
const outDir = `runs/${mode}-${stamp}`;

// The frame: rows with status "test".
function frameOps(csvText) {
  const [head, ...lines] = csvText.trim().split("\n");
  const cols = head.split(",");
  const parse = line => { // frame.csv has no quoted commas except in first_source, which is never needed here
    const cells = []; let cur = "", q = false;
    for (const ch of line) {
      if (ch === '"') q = !q; else if (ch === "," && !q) { cells.push(cur); cur = ""; } else cur += ch;
    }
    cells.push(cur);
    return Object.fromEntries(cols.map((c, i) => [c, cells[i]]));
  };
  return lines.map(parse).filter(r => r.status === "test");
}

async function get(path, key) {
  await sleep(2100); // stays under 30 a minute
  const r = await fetch(LIVE + path, { headers: {
    Authorization: `Bearer ${key}`, Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": API_VERSION, "User-Agent": "github-api-audit (risticveljko-vv)" } });
  if (!r.ok) throw new Error(`seed ${path}: HTTP ${r.status}`);
  return r.json();
}

// Reads the IDs that GitHub assigns (run, job, artifact, deployment ...) from the test repo. GET only.
async function seed() {
  const fixed = { AUDIT_OWNER: OWNER, AUDIT_REPO: REPO, AUDIT_TAG: TAG, AUDIT_ISSUE_NUMBER: ISSUE, AUDIT_PULL_NUMBER: PULL };
  if (mode === "mock") {
    const z = "0000000000000000000000000000000000000000";
    return { ...fixed, AUDIT_FIRST_SHA: z, AUDIT_HEAD_SHA: z, AUDIT_TREE_SHA: z, AUDIT_FILE_SHA: z, AUDIT_TAG_SHA: z,
      AUDIT_COMMENT_ID: "1", AUDIT_REVIEW_COMMENT_ID: "777", AUDIT_REVIEW_ID: "1", AUDIT_RELEASE_ID: "1", AUDIT_RUN_ID: "1", AUDIT_JOB_ID: "1",
      AUDIT_WORKFLOW_ID: "1", AUDIT_ARTIFACT_ID: "1", AUDIT_DEPLOYMENT_ID: "1", AUDIT_RULESET_ID: "1",
      AUDIT_GIST_ID: "aa5a315d61ae9438b18d", AUDIT_GHSA_ID: "GHSA-xxxx-xxxx-xxxx" };
  }
  const k = process.env.GITHUB_AUDIT_TOKEN;
  if (!k) throw new Error("GITHUB_AUDIT_TOKEN missing from .env");
  const R = `/repos/${OWNER}/${REPO}`;
  const runs = await get(`${R}/actions/runs?per_page=1&status=success`, k);
  const run = runs.workflow_runs?.[0];
  const jobs = await get(`${R}/actions/runs/${run?.id}/jobs`, k);
  const arts = await get(`${R}/actions/runs/${run?.id}/artifacts`, k);
  const deps = await get(`${R}/deployments?per_page=1`, k);
  const head = await get(`${R}/commits/main`, k);
  const first = await get(`${R}/commits?per_page=1&sha=${head.parents?.[0]?.sha ?? "main"}`, k);
  const file = await get(`${R}/contents/README.md`, k);
  const tagRef = await get(`${R}/git/ref/tags/${TAG}`, k);
  const rel = await get(`${R}/releases/tags/${TAG}`, k);
  const comments = await get(`${R}/issues/comments?per_page=1`, k);
  const reviews = await get(`${R}/pulls/${PULL}/reviews?per_page=1`, k);
  const reviewComments = await get(`${R}/pulls/comments?per_page=1`, k);
  const rulesets = await get(`${R}/rulesets`, k);
  const gists = await get(`/users/${OWNER}/gists?per_page=1`, k);
  const advisories = await get(`/advisories?per_page=1`, k);
  const ids = { ...fixed,
    AUDIT_RUN_ID: run?.id, AUDIT_WORKFLOW_ID: run?.workflow_id, AUDIT_JOB_ID: jobs.jobs?.[0]?.id,
    AUDIT_ARTIFACT_ID: arts.artifacts?.[0]?.id, AUDIT_DEPLOYMENT_ID: deps?.[0]?.id,
    AUDIT_HEAD_SHA: head.sha, AUDIT_TREE_SHA: head.commit?.tree?.sha, AUDIT_FIRST_SHA: first?.[0]?.sha,
    AUDIT_FILE_SHA: file.sha, AUDIT_TAG_SHA: tagRef.object?.type === "tag" ? tagRef.object.sha : undefined,
    AUDIT_RELEASE_ID: rel.id, AUDIT_COMMENT_ID: comments?.[0]?.id, AUDIT_REVIEW_ID: reviews?.[0]?.id,
    AUDIT_REVIEW_COMMENT_ID: reviewComments?.[0]?.id,
    AUDIT_RULESET_ID: rulesets?.[0]?.id, AUDIT_GIST_ID: gists?.[0]?.id, AUDIT_GHSA_ID: advisories?.[0]?.ghsa_id,
  };
  for (const [name, v] of Object.entries(ids)) if (v === undefined || v === null) throw new Error(`seed: no value for ${name}`);
  return Object.fromEntries(Object.entries(ids).map(([name, v]) => [name, String(v)]));
}

async function waitForMock() {
  for (let i = 0; i < 240; i++) { try { await fetch(MOCK + "/zen"); return; } catch { await sleep(500); } }
  throw new Error("mock did not start");
}

const ops = frameOps(readFileSync("frame.csv", "utf8"));
if (ops.length === 0) throw new Error("frame.csv has no 'test' rows");
mkdirSync(outDir, { recursive: true });
let mock;
try {
  if (mode === "mock") {
    mock = spawn("node_modules/.bin/prism", ["mock", SPEC, "--port", "4010", "--errors"], { stdio: "ignore" });
    await waitForMock();
  }
  const ids = await seed();
  writeFileSync(`${outDir}/seed.json`, JSON.stringify(ids, null, 2) + "\n");
  const args = ["--from", "schemathesis==4.32.7", "st", "--config-file", "harness/schemathesis.toml", "run", SPEC,
    "--url", base, "--exclude-method-regex", "^(?!GET$)", "--exclude-deprecated", "--mode", "positive", "--phases", "examples,fuzzing",
    "--checks", "status_code_conformance,content_type_conformance,response_schema_conformance", "--max-examples", "1",
    // One anchored regex over the frame's operation IDs (repeating --include-operation-id did not narrow the
    // selection in the first dry run; the frame guard in hooks.py refused the rest before sending).
    "--include-operation-id-regex", `^(${ops.map(o => o.operation_id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})$`,
    "-H", `Accept: ${mode === "live" ? "application/vnd.github+json" : "application/json"}`,
    // The mock needs no rate limit; the live run keeps the config's 30 a minute.
    ...(mode === "mock" ? ["--rate-limit", "6000/m"] : []),
    // Do not follow redirects: logs and archives answer 302 (documented) to a download host outside api.github.com.
    "--max-redirects", "0",
    "--report", "junit,har", "--report-dir", outDir];
  console.log(`=== ${mode}: ${ops.length} operations from frame.csv ===`);
  const r = spawnSync("uvx", args, { stdio: "inherit", env: {
    ...process.env, ...ids,
    AUDIT_KEY: mode === "live" ? process.env.GITHUB_AUDIT_TOKEN : "mock",
    AUDIT_ALLOWED_OPS: ops.map(o => `GET ${o.path}`).join("\n") } });
  writeFileSync(`${outDir}/exit-code.json`, JSON.stringify({ schemathesis: r.status, operations: ops.length }) + "\n");
  console.log(`\nReports in ${outDir}. Exit code: ${r.status}`);
} finally {
  if (mock) mock.kill();
}
