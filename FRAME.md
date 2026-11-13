# Frame: which GitHub read operations this audit tests

Status: **DRAFT, computed 2026-11-13.** Not frozen. Nothing here has touched api.github.com.

The frame is **145 GET operations**. Each one is called by at least one named, real-world client. **102 of them are testable** with one read-only token on one public test repo. Every testable operation gets tested. There is no sampling.

| Use case | In the frame | Testable |
| --- | --- | --- |
| A. Workflow automation | 53 | 41 |
| B. Agentic usage | 108 | 78 |
| C. Dev and QA environments | 11 | 10 |
| Any use case (union) | 145 | 102 |

An operation can serve more than one use case, so the rows add up to more than the union. Overlap: 34 operations are A only, 87 are B only, 3 are C only, 13 are A and B, 2 are B and C, and 6 are in all three.

## Why a client-anchored frame and not a random sample

A random draw from 666 GET operations would test endpoints nobody in this audience calls, such as enterprise billing. The question here is narrower and more useful: does the spec hold for the calls that real tools make? So the frame is defined by clients, not by the spec.

The risk of this design is cherry-picking. Three rules guard against it:

1. **The client list was fixed first.** `clients.csv` was committed (local commit `a004505`, 2026-11-13 18:12 CET) before the script that maps clients to operations existed. Each client is pinned to a release commit or an npm integrity hash.
2. **The mapping is mechanical.** `scripts/frame.py` reads each client's source code and maps every API call it finds to a spec operation. Nobody chooses operations by hand. Every call site is listed in `calls.csv` with a link to the exact line, so anyone can check any row.
3. **The eligibility rule is fixed in advance** (below), and every skip has a reason.

## The three use cases

- **A. Workflow automation.** What GitHub Actions workflows and CI scripts call: runs, jobs, logs, artifacts, caches, secrets and variables (listing only), releases, tags.
- **B. Agentic usage.** What coding agents call when they work on a repository: contents, commits, branches, issues, pull requests and reviews, search, releases.
- **C. Dev and QA environments.** What sets up and tracks dev, preview and QA environments: deployments and deployment statuses, branch rules, the tool manager that installs a project's toolchain.

## The clients

All pins are in `clients.csv`. `scripts/fetch-clients.sh` downloads each one and checks its pin.

| Client | Use case | Version | Why it is in | GET operations it adds | Testable |
| --- | --- | --- | --- | --- | --- |
| github/github-mcp-server | B | v2.1.0 | GitHub's official MCP server: the tools coding agents call | 99 | 72 |
| gh (pr, issue, repo, search, label) | B | v2.104.0 | What an agent runs in a terminal; Veljko's Claude Code sessions use gh | 12 | 9 |
| gh (run, workflow, cache, release, secret, variable) | A | v2.104.0 | Drives Actions and releases from CI and by hand | 43 | 31 |
| gh (ruleset, pr checks) | C | v2.104.0 | Branch rules and PR checks | 1 | 1 |
| actions/checkout | A | v7.0.1 | First step of almost every workflow, including Veljko's CI | 4 | 4 |
| actions/github-script (README examples) | A | v9.0.0 | The examples people copy into workflows | 2 | 2 |
| actions/download-artifact | A | v8.0.2 | Passing build output between jobs | 0 | 0 |
| actions/upload-artifact | A | v7.0.2 | Same | 0 | 0 |
| @actions/artifact (library) | A | 6.3.1 | What both artifact actions call | 1 | 1 |
| actions/cache | A | v6.1.0 | Dependency caching in CI | 0 | 0 |
| @actions/cache (library) | A | 6.1.0 | What actions/cache calls | 0 | 0 |
| googleapis/release-please | A | v17.11.2 | Release automation behind release-please-action | 8 | 8 |
| jdx/mise-action | C | v5.2.8 | Sets up the toolchain in Veljko's CI (his env contract) | 0 | 0 |
| jdx/mise (GitHub module) | C | v2026.11.8 | The tool manager behind that env contract; reads releases and tags | 7 | 7 |
| bobheadxi/deployments | C | v1.5.0 | Deployment and deployment-status bookkeeping for preview environments | 2 | 2 |
| actions/deploy-pages | C | v5.0.1 | Official Pages deploy (preview and docs sites) | 1 | 0 |

**Clients that add nothing, and why.** The cache and artifact actions talk to GitHub's internal Actions results service (a Twirp RPC API), not to the REST API, except for one artifact download path. mise-action downloads mise from github.com release URLs, not through the API. They stay in the list because the rule is mechanical: a client is in or out before its calls are counted.

## How a call becomes an operation

`scripts/frame.py` has five extractors. Each maps a call to a spec operation ID:

| Extractor | Clients | What it reads |
| --- | --- | --- |
| `octokit` | JavaScript and TypeScript clients | `octokit.rest.repos.getContent(...)` becomes `repos/get-content`. Octokit's method names come from the spec's operation IDs. |
| `route` | JavaScript and TypeScript clients | Route strings such as `'GET /repos/{owner}/{repo}/pages/deployments/{id}'` |
| `go-github` | github-mcp-server | Calls such as `client.Repositories.GetContents(...)`. go-github v92.0.0 (the version the server's `go.mod` requires) marks each method with its route (`//meta:operation GET /repos/...`). |
| `go-path` | gh, github-mcp-server | Paths built as strings: `safeurl.JoinPath("repos", owner, repo, "actions", "runs", id)`, `fmt.Sprintf("repos/%s/%s/issues/%d", ...)` |
| `rust-format` | mise | `format!("{api_url}/repos/{repo}/releases/latest")`. In mise, `{repo}` holds `owner/name`. |

Rules that apply to every client:

- **Test code is left out.** Files in test folders, `*_test.go`, `*.test.ts`, type declarations and source maps are skipped.
- **The HTTP method must be known.** For a path built as a string, the method is the first one named on that line or later in the same function. If the function names none (gh often hands the path to a helper), the method is the spec's only method on that path. If the spec has more than one, the call is **unresolved** and stays out of the frame.
- **Matching a built path to the spec** prefers exact literals. A client variable on a spec literal costs 1 point (gh builds `/repos/{o}/{r}/<app>/secrets` for actions, agents, codespaces and dependabot secrets). A client literal in a spec parameter costs 2 points. Only the cheapest matches count, up to 2 points.

**Result:** 430 call sites. 395 map to a spec operation. 27 are unresolved because the method is unknown, and 8 map to nothing in the spec. All 35 are in `calls.csv` with status `no-method` or `unmapped`. Notable ones:

- gh's `variable list`, `ruleset view` and `run view --log` (full-run logs) build paths that have both GET and another method in the spec, and send them through a helper. They are unresolved, so `actions/list-repo-variables`, `repos/get-repo-ruleset` (for gh; the MCP server still brings it in) and `actions/download-workflow-run-logs` (for gh) do not count for gh.
- gh's `repo sync` reads `GET /repos/{owner}/{repo}/git/refs/heads/{branch}`. The spec documents only `/git/ref/{ref}` for GET. GitHub's README says some operations have alias paths that the description does not list, so this is not counted.

## Eligibility: which frame operations are testable

Reasons are checked in this order. The first that applies is the one recorded in `frame.csv`.

| Reason | Rule | In the frame |
| --- | --- | --- |
| `deprecated` | The spec marks the operation deprecated. Excluded, not skipped. | 0 |
| `plan` | Enterprise path, or `githubCloudOnly` in the spec | 0 |
| `auth` | GitHub's own token data (github/docs, `fine-grained-pat.json` for API version 2026-03-10) does not list it for fine-grained tokens | 11 |
| `write` | GitHub's token data says this GET needs a write permission, and the audit token is read-only | 7 |
| `org` | It needs an organization: an `{org}` path, or an organization permission | 17 |
| `id` | A path ID that the setup cannot provide (a code scanning, Dependabot or secret scanning alert, a code quality finding, a Pages deployment, an autolink, a rule suite, an issue artifact) | 8 |
| `test` | None of the above | **102** |

What each skip group would need:

- **`auth` (11):** 2 check-run operations (`checks/list-for-ref`, `checks/list-annotations`), 3 notification operations and 6 user-project operations. Fine-grained tokens cannot call them. A classic token could, but a classic token cannot be limited to one repository.
- **`org` (17):** org secrets and their public keys (8, all from gh), one org variable, org projects (6), org issue types and one team lookup. A free organization, a second fine-grained token (its resource owner is the organization) and a few objects (an org variable, a project, a team) would make most of them testable. I have not checked whether issue types exist on a free organization.
- **`write` (7):** codespaces repo secrets (2), org rulesets (4) and org repository advisories (1).

Testable operations by API area: actions 23, repos 17, issues 10, pulls 7, git 5, search 5, commits 4, other 31.

## Context: the whole spec

The same rule applied to all 666 GET operations, for comparison only: 303 testable, 169 `org`, 84 `auth`, 48 `id`, 27 `write`, 16 `plan`, 19 deprecated. The frame is not a sample of these; it is the subset real clients call.

## Rate budget

A run sends about 128 requests: 15 lookups to read the test repo's IDs, and about 113 test requests (102 operations, a few with more than one example). At 30 a minute, that is about 5 minutes. Two runs plus reproductions stay under 400 requests. This is far below GitHub's 5,000 an hour for a token, so the whole frame fits and no priority order is needed.

## Reproduce

```
mise run frame     # fetches the spec, the token data and the pinned clients (github.com and npm, not the API),
                   # recomputes, and fails if frame.csv or calls.csv would change
```

## Changes after the client list was committed

- **deploy-pages scope:** `src/**/*.ts` became `src/**/*.js`. Its source is JavaScript, so the first scope matched no file at all. This fixes a glob, not a selection. It adds 1 GET (`repos/get-pages-deployment`), which is skipped as `id`.
