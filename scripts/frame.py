#!/usr/bin/env python3
"""Compute the audit frame from the frozen spec and the pinned clients.

The frame is every GET operation in the frozen spec that at least one client in clients.csv calls.
The mapping from client source code to spec operations is mechanical (see the extractors below), and
every call site it finds is written to calls.csv, so anyone can check a single line of the frame.
Eligibility (testable on a free personal account with one public test repo) comes from the spec and
from GitHub's own fine-grained token data.

Usage: python3 scripts/frame.py            writes frame.csv and calls.csv, prints the counts
       python3 scripts/frame.py --check    exits 1 if frame.csv or calls.csv would change
Needs: sh scripts/fetch-spec.sh and sh scripts/fetch-clients.sh first. Reads files only; no network.
"""
import collections
import csv
import io
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC = ROOT / "spec" / "api.github.com.2026-03-10.json"
FGPAT = ROOT / "spec" / "fine-grained-pat.json"
FGPAT_PERMS = ROOT / "spec" / "fine-grained-pat-permissions.json"
CLIENTS_CSV = ROOT / "clients.csv"
CLIENT_DIR = ROOT / ".clients"
GO_GITHUB_DIR = CLIENT_DIR / "google_go-github" / "github"

HTTP_METHODS = ("get", "put", "post", "patch", "delete", "head", "options")
WILD = None  # a path segment whose value the client fills in at run time

# Top-level path segments of the REST API. A string is read as a REST path only if it starts with one.
# 'app' is left out: no client here authenticates as a GitHub App, and gh uses "app/%s" as a search qualifier.
ROOTS = {
    "repos", "orgs", "user", "users", "search", "gists", "notifications", "rate_limit", "meta", "markdown",
    "octocat", "emojis", "licenses", "codes_of_conduct", "gitignore", "events", "issues", "installation",
    "applications", "teams", "projects", "networks", "feeds", "zen", "repositories", "organizations",
    "advisories", "enterprises", "marketplace_listing", "versions", "classrooms", "assignments", "credentials",
}

# Test code and generated type files are not calls a user's run makes.
EXCLUDED_DIRS = {"__tests__", "__test__", "test", "tests", "testdata", "mocks", "__mocks__", "__toolsnaps__", "e2e"}
EXCLUDED_SUFFIXES = ("_test.go", ".test.ts", ".spec.ts", ".test.js", ".spec.js", ".d.ts", ".map")


# ---------------------------------------------------------------- spec

def segments(path):
    """'/repos/{owner}/{repo}' -> ['repos', '{}', '{}']; a client-side WILD stays WILD."""
    return [s for s in path.strip("/").split("/") if s != ""]


def norm(path):
    """Replace every {name} with {} so that templates compare by shape."""
    return "/" + "/".join("{}" if s.startswith("{") else s for s in segments(path))


class Spec:
    def __init__(self, doc):
        self.doc = doc
        self.ops = {}       # operationId -> dict
        self.by_route = {}  # (METHOD, normalised path) -> operationId
        self.templates = collections.defaultdict(list)  # number of segments -> [(segments, path)]
        self.multi = set()  # paths whose last path parameter may span several segments
        for path, item in doc["paths"].items():
            for method, op in item.items():
                if method not in HTTP_METHODS:
                    continue
                oid = op["operationId"]
                params = [self.resolve(p) for p in item.get("parameters", []) + op.get("parameters", [])]
                self.ops[oid] = {"method": method.upper(), "path": path, "op": op, "params": params}
                self.by_route[(method.upper(), norm(path))] = oid
                if any(p.get("x-multi-segment") for p in params if p.get("in") == "path"):
                    self.multi.add(path)
            segs = segments(path)
            self.templates[len(segs)].append((segs, path))
        self.scopes = {oid.split("/")[0] for oid in self.ops}

    def resolve(self, p):
        if "$ref" in p:
            return self.doc["components"]["parameters"][p["$ref"].split("/")[-1]]
        return p

    def ops_at(self, path):
        return {m: oid for (m, n), oid in self.by_route.items() if n == norm(path)}

    def match(self, segs):
        """Spec paths that a client path (list of str or WILD) can reach.

        A literal must equal a literal, and anything may fill a {param}. Two kinds of fit cost points,
        and only the cheapest matches are kept (at most 2 points):
          1 point: a client variable on a spec literal (gh builds '/repos/{o}/{r}/<app>/secrets' with
                   app = actions, dependabot or codespaces);
          2 points: a client literal in a spec {param} ('secrets' in '/orgs/{org}/{security_product}/{enablement}'
                   is almost always a different endpoint).
        """
        found = []
        candidates = [(t, p, False) for t, p in self.templates.get(len(segs), [])]
        for path in self.multi:
            # A multi-segment parameter ({path}, {ref}) takes one or more segments of any kind, but only when
            # every spec literal before it is matched by the same client literal (no variable on a literal).
            t = segments(path)
            if len(segs) >= len(t) and t[-1].startswith("{"):
                candidates.append((t[:-1] + ["{*}"] * (len(segs) - len(t) + 1), path, True))
        for tsegs, path, strict in candidates:
            cost = 0
            for c, t in zip(segs, tsegs):
                if t == "{*}":
                    continue
                if t.startswith("{"):
                    cost += 0 if c is WILD else 2
                elif c is WILD:
                    cost += 99 if strict else 1
                elif c != t:
                    cost = 99
                    break
            if cost <= 2:
                found.append((cost, path))
        if not found:
            return []
        best = min(c for c, _ in found)
        return sorted({p for c, p in found if c == best})


# ---------------------------------------------------------------- extractors
# Each extractor yields (line_number, kind, raw_text, method_or_None, [operationId, ...] or None).
# None as the operation list means "this looks like an API call, but it maps to nothing in the spec".

def kebab(name):
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", name).lower()


# The endpoint method must not be followed by another '.', so 'github.actions.results.api' (a service name) is skipped.
OCTOKIT_RX = re.compile(r"\b(?:octokit|github)(?:\.rest)?\.([a-z][A-Za-z]*)\.([a-z][A-Za-z]*)\b(?![.\w])")
ROUTE_RX = re.compile(r"""['"`](GET|POST|PUT|PATCH|DELETE) (/[^'"`\s]*)""")


def extract_octokit(text, spec):
    """octokit.rest.repos.getContent / github.rest.issues.get / octokit.repos.get -> 'repos/get-content'."""
    for n, line in enumerate(text.splitlines(), 1):
        for m in OCTOKIT_RX.finditer(line):
            scope, method = m.groups()
            if scope not in spec.scopes:
                continue  # github.context.repo, octokit.paginate.iterator ... are not endpoint methods
            oid = f"{scope}/{kebab(method)}"
            yield n, "octokit", m.group(0), (spec.ops[oid]["method"] if oid in spec.ops else None), (
                [oid] if oid in spec.ops else None)


def extract_route(text, spec):
    """octokit.request('GET /repos/{owner}/{repo}/pages/deployments/{id}') and the same route strings."""
    for n, line in enumerate(text.splitlines(), 1):
        for m in ROUTE_RX.finditer(line):
            method, path = m.group(1), re.sub(r"\{\?[^}]*\}", "", m.group(2)).split("?")[0]
            oid = spec.by_route.get((method, norm(path)))
            yield n, "route", m.group(0)[1:], method, ([oid] if oid else None)


def go_github_table(src_dir):
    """go-github marks each method with the REST routes it calls: '//meta:operation GET /repos/{owner}/{repo}'."""
    table, pending = {}, []
    for f in sorted(pathlib.Path(src_dir).glob("*.go")):
        if f.name.endswith("_test.go"):
            continue
        for line in f.read_text(errors="ignore").splitlines():
            m = re.match(r"\s*//meta:operation (\w+) (\S+)", line)
            if m:
                pending.append((m.group(1), m.group(2)))
                continue
            if line.strip().startswith("//"):
                continue
            m = re.match(r"func \(\w+ \*(\w+)Service\) (\w+)\(", line)
            if m:
                table[(m.group(1), m.group(2))] = pending
            pending = []
    return table


def extract_go_github(text, spec, table):
    services = {s for s, _ in table}
    for n, line in enumerate(text.splitlines(), 1):
        for m in re.finditer(r"\b\w+\.([A-Z]\w+)\.([A-Z]\w+)\(", line):
            svc, meth = m.groups()
            if svc not in services:
                continue
            routes = table.get((svc, meth))
            if not routes:
                yield n, "go-github", f"{svc}.{meth}", None, None
                continue
            for method, path in routes:
                oid = spec.by_route.get((method, norm(path)))
                yield n, "go-github", f"{svc}.{meth} -> {method} {path}", method, ([oid] if oid else None)


GO_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')
GO_METHOD = re.compile(r'\bhttp\.Method(Get|Post|Put|Patch|Delete)\b|"(GET|POST|PUT|PATCH|DELETE)"')


def go_literal_path(s):
    """'repos/%s/%s/issue-types' -> ['repos', WILD, WILD, 'issue-types'] if it reads as a REST path."""
    s = s.replace("%%2F", "/").split("?")[0]
    s = re.sub(r"^%[sv]/?", "", s)  # a base URL in front
    s = re.sub(r"^https://api\.github\.com", "", s).lstrip("/")
    segs = [x for x in s.split("/") if x]
    # A bare word ("user", "repos") is too often a flag or field name; a path needs at least two segments.
    if len(segs) < 2 or segs[0] not in ROOTS:
        return None
    return [WILD if re.search(r"%(\[\d\])?[sdvq]", seg) else seg for seg in segs]


def split_args(s):
    """Top-level comma split of a Go argument list, up to the closing parenthesis."""
    args, depth, cur, i, inq = [], 0, "", 0, False
    while i < len(s):
        ch = s[i]
        if inq:
            cur += ch
            if ch == "\\":
                cur += s[i + 1]; i += 1
            elif ch == '"':
                inq = False
        elif ch == '"':
            inq = True; cur += ch
        elif ch in "([{":
            depth += 1; cur += ch
        elif ch in ")]}":
            if depth == 0:
                args.append(cur.strip()); return args
            depth -= 1; cur += ch
        elif ch == "," and depth == 0:
            args.append(cur.strip()); cur = ""
        else:
            cur += ch
        i += 1
    return None  # call continues on the next line; not handled


def join_path_segments(args):
    out = []
    for a in args:
        m = re.fullmatch(r'"((?:[^"\\]|\\.)*)"', a)
        if m:
            out += [s for s in m.group(1).split("/") if s]
        else:
            out.append(WILD)
    return out


def method_near(lines, i):
    """The first HTTP method named on the path's line or after it, up to the end of the enclosing function."""
    for line in lines[i:]:
        m = GO_METHOD.search(line)
        if m:
            return (m.group(1) or m.group(2)).upper()
        if line.startswith("}") or line.startswith("func "):
            break
    return None


def only_method(spec, segs):
    """If the function names no method (gh often hands the path to a helper), use the method the spec defines,
    but only when every matching path has exactly one, and it is the same one."""
    methods = {m for p in spec.match(segs) for m in spec.ops_at(p)}
    return methods.pop() if len(methods) == 1 else None


def extract_go_path(text, spec):
    """gh and the MCP server build REST paths as strings: safeurl.JoinPath(...), fmt.Sprintf("repos/%s/...").
    The HTTP method is the first one named on that line or the next 14 lines; if none is named, the call
    site is reported as unresolved and kept out of the frame."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        paths = []
        for m in re.finditer(r"\bJoinPath\(", line):
            args = split_args(line[m.end():])
            if args and args[0].startswith('"') and args[0].strip('"').split("/")[0] in ROOTS:
                paths.append(("JoinPath(" + ", ".join(args) + ")", join_path_segments(args)))
        if not paths:
            for m in GO_STRING.finditer(line):
                segs = go_literal_path(m.group(1))
                if segs:
                    paths.append((m.group(0), segs))
        for raw, segs in paths:
            kind, method = "go-path", method_near(lines, i)
            if method is None:
                kind, method = "go-path-only-method", only_method(spec, segs)
            if method is None:
                yield i + 1, "go-path", raw, None, None
                continue
            hits = [spec.ops_at(p).get(method) for p in spec.match(segs)]
            hits = [h for h in hits if h]
            yield i + 1, kind, raw, method, (hits or None)


def extract_rust_format(text, spec, default_method):
    """mise: format!("{api_url}/repos/{repo}/releases/latest"). In mise, {repo} holds 'owner/name'."""
    text = text.split("#[cfg(test)]")[0]
    for n, line in enumerate(text.splitlines(), 1):
        for m in re.finditer(r'"([^"]*/repos/[^"]*)"', line):
            s = m.group(1)
            s = s[s.index("/repos/"):].split("?")[0]
            s = s.replace("{repo}", "{}/{}")
            segs = [WILD if re.fullmatch(r"\{[^}]*\}", x) else x for x in s.strip("/").split("/") if x]
            hits = [spec.ops_at(p).get(default_method) for p in spec.match(segs)]
            hits = [h for h in hits if h]
            yield n, "rust-format", m.group(0), default_method, (hits or None)


# ---------------------------------------------------------------- clients

def read_clients(path=CLIENTS_CSV):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def client_root(row):
    if row["repo"].startswith("npm:"):
        pkg = row["repo"][4:]
        return CLIENT_DIR / f"npm-{pkg.lstrip('@').replace('/', '-')}-{row['ref']}"
    return CLIENT_DIR / row["repo"].replace("/", "_")


def source_url(row, rel, line):
    if row["repo"].startswith("npm:"):
        return f"https://www.npmjs.com/package/{row['repo'][4:]}/v/{row['ref']} ({rel}:{line})"
    return f"https://github.com/{row['repo']}/blob/{row['pin']}/{rel}#L{line}"


def client_files(row, root):
    seen = set()
    for pattern in row["scope"].split(";"):
        for f in sorted(root.glob(pattern)):
            rel = f.relative_to(root)
            if not f.is_file() or f in seen:
                continue
            if set(rel.parts[:-1]) & EXCLUDED_DIRS or f.name.endswith(EXCLUDED_SUFFIXES):
                continue
            seen.add(f)
            yield f, rel.as_posix()


def extract_calls(row, spec, table, root=None):
    root = root or client_root(row)
    if not root.exists():
        raise SystemExit(f"{root} missing: run sh scripts/fetch-clients.sh")
    kinds = row["extractors"].split(";")
    for f, rel in client_files(row, root):
        text = f.read_text(errors="ignore")
        gens = []
        if "octokit" in kinds:
            gens.append(extract_octokit(text, spec))
        if "route" in kinds:
            gens.append(extract_route(text, spec))
        if "go-github" in kinds:
            gens.append(extract_go_github(text, spec, table))
        if "go-path" in kinds:
            gens.append(extract_go_path(text, spec))
        if "rust-format" in kinds:
            gens.append(extract_rust_format(text, spec, row["default_method"]))
        for gen in gens:
            for line, kind, raw, method, oids in gen:
                yield {"client_id": row["client_id"], "use_case": row["use_case"], "file": rel, "line": line,
                       "kind": kind, "raw": raw, "method": method or "",
                       "operation_ids": ";".join(oids or []),
                       "status": "mapped" if oids else ("no-method" if not method and kind.startswith("go-path") else "unmapped"),
                       "source_url": source_url(row, rel, line)}


# ---------------------------------------------------------------- eligibility

# How each path parameter gets a value on a free personal account with one public test repo,
# filled by hand at setup (see RUNSHEET.md). Anything not listed here cannot be seeded: skip 'id'.
SEED = {
    "owner": "test repo owner (Veljko's account)", "repo": "test repo name", "username": "Veljko's account",
    "ref": "a branch or tag in the test repo", "branch": "default branch", "sha": "a commit in the test repo",
    "commit_sha": "a commit in the test repo", "tree_sha": "a tree in the test repo", "file_sha": "a blob in the test repo",
    "tag": "a tag in the test repo", "basehead": "two commits in the test repo", "path": "a file in the test repo",
    "issue_number": "an issue in the test repo", "pull_number": "a pull request in the test repo",
    "comment_id": "a comment in the test repo", "review_id": "a PR review in the test repo",
    "name": "a label or an Actions variable in the test repo (by operation)", "milestone_number": "a milestone in the test repo",
    "release_id": "a release in the test repo", "asset_id": "a release asset in the test repo",
    "run_id": "the seed workflow run", "job_id": "a job of the seed run", "attempt_number": "attempt 1 of the seed run",
    "workflow_id": "the seed workflow", "artifact_id": "the seed run's artifact", "check_run_id": "a check run of the seed run",
    "check_suite_id": "the seed run's check suite", "deployment_id": "the seed run's deployment",
    "status_id": "a status of that deployment", "environment_name": "the seed workflow's environment",
    "ruleset_id": "a ruleset on the test repo", "secret_name": "a dummy secret in the test repo",
    "gist_id": "a gist on Veljko's account", "label_name": "a label in the test repo",
    "tag_sha": "an annotated tag in the test repo", "archive_format": "zip (the only documented value)",
    "ghsa_id": "a public advisory ID, read from list-global-advisories",
}


def load_fgpat():
    ops = json.loads(FGPAT.read_text())
    perms = json.loads(FGPAT_PERMS.read_text())
    allowed = {(o["verb"].upper(), o["requestPath"]) for v in ops.values() for o in v}
    needs = collections.defaultdict(list)
    for key, v in perms.items():
        level = v["displayTitle"].split(" permissions")[0].split()[0].lower()  # repository / organization / account
        for o in v["permissions"]:
            needs[(o["verb"].upper(), o["requestPath"])].append(f"{level}:{key}:{o['access']}")
    return allowed, needs


def eligibility(spec, oid, allowed, needs):
    """Return (status, reason, token, permissions, path_params). status: test | skip | excluded.

    Reasons, checked in this order: deprecated (excluded); plan (enterprise or Enterprise Cloud only);
    auth (a fine-grained token cannot call it); write (GitHub's token data asks for a write permission);
    org (needs an organization); id (a path ID that the setup cannot provide)."""
    o = spec.ops[oid]
    xg = o["op"].get("x-github", {})
    pparams = [p["name"] for p in o["params"] if p.get("in") == "path"]
    route = (o["method"], o["path"])
    perms = sorted(set(needs.get(route, [])))
    token = "fine-grained" if route in allowed else "classic-or-app"
    if o["op"].get("deprecated"):
        return "excluded", "deprecated", token, perms, pparams
    if o["path"].startswith("/enterprises") or xg.get("githubCloudOnly"):
        return "skip", "plan", token, perms, pparams
    if route not in allowed:
        return "skip", "auth", token, perms, pparams
    if any(p.endswith(":write") for p in perms):
        return "skip", "write", token, perms, pparams
    if any(p.startswith("organization:") for p in perms) or "org" in pparams:
        return "skip", "org", token, perms, pparams
    unseeded = [p for p in pparams if p not in SEED]
    if unseeded:
        return "skip", "id", token, perms, pparams
    return "test", "", token, perms, pparams


# ---------------------------------------------------------------- frame

def build(spec, clients, table, allowed, needs, roots=None):
    calls = []
    for row in clients:
        root = (roots or {}).get(row["client_id"])
        calls.extend(extract_calls(row, spec, table, root))
    by_op = collections.defaultdict(list)
    for c in calls:
        for oid in filter(None, c["operation_ids"].split(";")):
            by_op[oid].append(c)
    frame = []
    for oid in sorted(by_op):
        if spec.ops[oid]["method"] != "GET":
            continue
        cs = by_op[oid]
        status, reason, token, perms, pparams = eligibility(spec, oid, allowed, needs)
        xg = spec.ops[oid]["op"].get("x-github", {})
        frame.append({
            "operation_id": oid, "method": "GET", "path": spec.ops[oid]["path"],
            "category": xg.get("category", ""), "use_cases": ";".join(sorted({c["use_case"] for c in cs})),
            "clients": ";".join(sorted({c["client_id"] for c in cs})), "call_sites": len(cs),
            "first_source": sorted(c["source_url"] for c in cs)[0],
            "token": token, "permissions": ";".join(perms), "path_params": ";".join(pparams),
            "status": status, "reason": reason,
        })
    return frame, calls


def to_csv(rows, fields):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


FRAME_FIELDS = ["operation_id", "method", "path", "category", "use_cases", "clients", "call_sites", "first_source",
                "token", "permissions", "path_params", "status", "reason"]
CALL_FIELDS = ["client_id", "use_case", "file", "line", "kind", "raw", "method", "operation_ids", "status", "source_url"]


def summary(spec, frame, calls, clients, allowed, needs):
    gets = [o for o in spec.ops.values() if o["method"] == "GET"]
    out = [f"spec: {len(spec.ops)} operations, {len(gets)} GET, {sum(1 for o in gets if o['op'].get('deprecated'))} GET deprecated"]
    every = collections.Counter(
        eligibility(spec, o["op"]["operationId"], allowed, needs)[:2] for o in gets)
    out.append(f"  all GETs by eligibility (context only, not the frame): {dict(sorted(every.items()))}")
    out.append(f"call sites: {len(calls)} ({collections.Counter(c['status'] for c in calls)})")
    out.append(f"frame (GET operations a client calls): {len(frame)}")
    out.append(f"  status: {dict(collections.Counter((r['status'], r['reason']) for r in frame))}")
    test = [r for r in frame if r["status"] == "test"]
    out.append(f"  testable: {len(test)}")
    for uc in "ABC":
        rows = [r for r in frame if uc in r["use_cases"].split(";")]
        out.append(f"  use case {uc}: {len(rows)} in frame, {sum(r['status'] == 'test' for r in rows)} testable")
    combos = collections.Counter(r["use_cases"] for r in frame)
    out.append(f"  overlap (use-case sets): {dict(sorted(combos.items()))}")
    for row in clients:
        cid = row["client_id"]
        rows = [r for r in frame if cid in r["clients"].split(";")]
        alln = {o for c in calls if c["client_id"] == cid for o in c["operation_ids"].split(";") if o}
        out.append(f"  client {cid} ({row['use_case']}): {len(alln)} operations (any method), "
                   f"{len(rows)} GET in frame, {sum(r['status'] == 'test' for r in rows)} testable")
    return "\n".join(out)


def main(argv):
    spec = Spec(json.loads(SPEC.read_text()))
    clients = read_clients()
    table = go_github_table(GO_GITHUB_DIR)
    allowed, needs = load_fgpat()
    frame, calls = build(spec, clients, table, allowed, needs)
    outputs = {ROOT / "frame.csv": to_csv(frame, FRAME_FIELDS), ROOT / "calls.csv": to_csv(calls, CALL_FIELDS)}
    if "--check" in argv:
        stale = [p.name for p, s in outputs.items() if not p.exists() or p.read_text() != s]
        if stale:
            print("out of date: " + ", ".join(stale) + " (run python3 scripts/frame.py)")
            return 1
        print("frame.csv and calls.csv match the pinned inputs")
        return 0
    for p, s in outputs.items():
        p.write_text(s)
    print(summary(spec, frame, calls, clients, allowed, needs))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
