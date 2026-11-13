# Pre-registration: GitHub REST API, docs versus behaviour

Status: **DRAFT, not frozen.** Veljko has not approved it. The freeze is the first public commit of this repo, made before any check runs (Run 0 included). After the freeze, any change to this file is a deviation and goes in `DEVIATIONS.md` with its reason.

Second audit in the series "A content engineer's stack, checked". GitHub is where Veljko's repos, READMEs, releases and CI live.

## Question

For the read operations that real GitHub clients call, what share have at least one confirmed disagreement between GitHub's published OpenAPI description and what the API returns?

The answer is given per use case:

- **A. Workflow automation:** what GitHub Actions workflows and CI scripts call.
- **B. Agentic usage:** what coding agents call when they work on a repository.
- **C. Dev and QA environments:** what sets up and tracks dev, preview and QA environments.

## Target, frozen

| Item | Value |
| --- | --- |
| Spec | `descriptions/api.github.com/api.github.com.2026-03-10.json` (bundled) in [github/rest-api-description](https://github.com/github/rest-api-description) |
| Commit | `bd6df26d2a0104874fe5025a25ebcde356413364` (2026-11-12 20:26 UTC, main at fetch time) |
| SHA-256 | `fc75cec70017bf6c0a4e29dfd7121df42321290ef29bd65f288875e823e79611` |
| Licence | MIT. Copying and quoting are allowed with the copyright notice. |
| API version | `X-GitHub-Api-Version: 2026-03-10` on every request |
| Operations | 1,280 in total, 666 GET, 19 of them deprecated |
| Base URL | `https://api.github.com` |
| Token data | [github/docs](https://github.com/github/docs) commit `66f5790db61fc9d07eb9b7d3525f2994cd2910b9`, `src/github-apps/data/fpt-2026-03-10/fine-grained-pat.json` (SHA-256 `74646a72…6c6e`) and `fine-grained-pat-permissions.json` (`0c682091…f74e`). Used for eligibility only. |
| Copy | `sh scripts/fetch-spec.sh` downloads all three files from commit-pinned URLs and checks each SHA-256. The spec is 14 MB, so it is not committed. |

**Why this file.** GitHub publishes three bundled descriptions. The undated `api.github.com.json` is the 2022-11-28 description plus `x-github-breaking-changes` annotations (I diffed them: all 86 differences are those annotations). 2026-03-10 is the newest API version, and it is what a new integration or agent would target. Requests without the version header get 2022-11-28 ([GitHub docs](https://docs.github.com/en/rest/about-the-rest-api/api-versions)), so the header is always sent. The bundled file is GitHub's ["preferred"](https://github.com/github/rest-api-description#description-formats) format. The dereferenced one is 76 MB and adds nothing for these tools.

If GitHub changes the description during the audit, the frozen file still counts. Changes go in the report as a note, made with oasdiff.

## Frame: real clients, then a census

Details and counts: [FRAME.md](FRAME.md).

1. **Clients, fixed first.** `clients.csv` names 16 client entries across the three use cases: GitHub's official MCP server, gh (by command group), actions/checkout, the artifact and cache actions and their libraries, actions/github-script's examples, release-please, mise-action and mise, bobheadxi/deployments and actions/deploy-pages. Each is pinned to a release commit or an npm integrity hash.
2. **Operations, derived mechanically.** `scripts/frame.py` maps every API call in each client's source to a spec operation. Every call site is in `calls.csv` with a link to its line. Calls whose HTTP method the script cannot determine stay out, and are listed.
3. **The frame** is every GET operation that at least one client calls: **145**.
4. **Eligibility, fixed in advance.** Reasons in order: `deprecated` (excluded), `plan` (enterprise only), `auth` (a fine-grained token cannot call it, per GitHub's token data), `write` (GitHub's token data asks for a write permission), `org` (needs an organization), `id` (a path ID the setup cannot provide).
5. **Census of the testable frame: 102 operations**, all tested. A 41, B 78, C 10.

`mise run frame` recomputes the frame from the pinned inputs and fails if `frame.csv` or `calls.csv` would change.

## Account and token

- **Account:** Veljko's personal GitHub account `risticveljko-vv`. No company account or repo is touched.
- **Test repo:** one new public repo, `api-audit-test`, with only seed content (see `RUNSHEET.md`). Setup is done by hand in the GitHub web UI, plus one workflow run Veljko starts by hand. The harness never creates anything.
- **One token:** a fine-grained personal access token. Resource owner `risticveljko-vv`. Repository access: only `api-audit-test`. Expiry: 30 days. Revoked after day 2. Read access only:
  - Repository: Actions, Administration, Agent secrets, Code scanning alerts, Commit statuses, Contents, Dependabot alerts, Dependabot secrets, Deployments, Environments, Issues, Metadata, Pull requests, Repository security advisories, Secret scanning alerts, Secrets, Variables.
  - Account: Codespaces user secrets, Starring.
  - These are exactly the permissions GitHub's token data lists for the 102 testable operations.
- **No classic token.** It would unlock 11 operations (2 check-run reads, 3 notification reads, 6 user-project reads), but a classic token cannot be limited to one repository. Those 11 are reported as skipped `auth`.
- **No organization.** 17 operations need one. They are reported as skipped `org`.
- The token lives in `.env`, which git ignores, and loads with `node --env-file`. It is never printed or logged. Schemathesis filters it from saved requests, and the curl script passes it on stdin.
- Operations at the account level (`/user`, `/user/starred`, `/gists`, `/user/orgs`, `/users/{username}`) return Veljko's own profile data. Saved responses are scrubbed before anything is published.

## Rate limits

- GitHub allows 5,000 requests an hour for a personal token. Secondary limits include no more than 100 concurrent requests and 900 points a minute for REST, and search endpoints have lower limits ([GitHub docs](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)).
- This audit sends **one request at a time, at most 30 a minute**, as in the Neon audit. A run is about 128 requests (15 lookups for seed IDs, about 113 tests), so about 5 minutes. The whole audit stays under 400 requests.
- On any 429, or a 403 with a rate-limit message, the run stops and waits. That response is logged and not counted.

## What counts as an error

| Code | Category | Counts when |
| --- | --- | --- |
| E1 | Wrong status code | A valid request returns a status that the spec does not list for that operation, on two runs. |
| E2 | Missing field | A field that the schema marks required is absent. |
| E3 | Wrong type | A value breaks the documented type, enum, format or nullability. |
| E4 | Valid request rejected | A request that is valid per the spec is rejected with a 4xx, and the response names an input or condition that the spec does not require. |
| E5 | Stale example | A documented example fails its own schema (Run 0), or fails when it is sent as written. |
| E6 | Wrong content type | The response media type differs from the documented one. |
| E8 | Documented behaviour contradicted | A sentence in the spec states a specific behaviour of this operation (a default, a fallback, a filter, what comes back when an input is left out), and the responses show different behaviour, on two runs. The report quotes the sentence. |

- **One discrepancy counts once,** under the first code in the order E1, E2, E3, E4, E5, E6, E8.
- **E8 leads come only from responses the runs already produced.** There is no extra probing to look for them.
- **E7, dead reference, is reported beside the metric, not in it.** A hand-written guide in `github/docs` `content/rest` (CC-BY 4.0, read from a local clone) cites an endpoint or parameter that is not in the frozen spec. GitHub generates its reference pages from this spec, so only hand-written guides are checked; comparing the reference pages would be circular.

**Not counted, logged separately:** undocumented extra fields (unless the schema forbids them), undocumented headers (GitHub's README says ["Not all headers are described"](https://github.com/github/rest-api-description#limitations)), alias paths the description does not list (same README), missing descriptions or examples, lint and style issues, 5xx, 429, timeouts, and 401, 403 or 404 caused by permission, plan or visibility limits.

**Severity:** S1 breaks a client, S2 misleads, S3 is cosmetic. The headline counts all confirmed errors, and the S1 count is reported beside it.

## Confirmation rule

A tool failure is a lead, not a finding. A lead counts only when:

1. it is reproduced with a plain request (curl, token removed in the saved copy);
2. it is repeated at least 24 hours later with the same result;
3. a second reader checks it against the frozen spec, given only the evidence and these definitions.

Anything unconfirmed stays out of the count and is listed as unconfirmed.

## Runs

- **Run 0, static. No calls to GitHub.** Spectral 6.17.0 (`oas3-valid-media-example`, `oas3-valid-schema-example`) and Redocly CLI 2.72.0 as a second opinion. E5 is counted for the examples of the 102 testable operations; the whole-spec count is reported as context. The claim from Run 0 is "examples that fail their own schema", never "docs that disagree with the API". E7 from a local clone of `github/docs`.
- **Dry run against a local Prism 5.16.0 mock.** Sends nothing to GitHub. Confirms the selection, the guards, the seeding and the reports.
- **Run 1, live, GET only.** Schemathesis 4.32.7, through `harness/run.mjs`:
  `--include-operation-id-regex ^(<the 102 operation IDs>)$ --exclude-method-regex ^(?!GET$) --exclude-deprecated --mode positive --phases examples,fuzzing --checks status_code_conformance,content_type_conformance,response_schema_conformance --max-examples 1 --max-redirects 0`, one worker, `rate-limit = 30/m`.
  - Headers: `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2026-03-10`, a `User-Agent` naming this audit.
  - A hook refuses any non-GET request and any operation outside the frame before it is sent.
  - Redirects are not followed. Logs and archives answer 302 (documented); the audit checks that answer and never calls the download host.
  - Path IDs come from the test repo (`harness/schemathesis.toml`). Generated values fill only optional query parameters.
- **Second pass at least 24 hours later,** unchanged, for the confirmation rule.

## Reporting

- **Metric, per use case:** operations with ≥1 confirmed error ÷ operations tested, with a Wilson 95% interval. The tested count and the skip count by reason are given with it. The union of all three is given too. Use case C has only 10 testable operations, so its interval will be wide; the report says so.
- **GitHub is told first, through its own channel:** the [Schema Inaccuracy template](https://github.com/github/rest-api-description/issues/new?template=schema-inaccuracy.md) on github/rest-api-description. It asks for the operation or schema, what was "Expected", and "Reproduction Steps" (for example, a curl line). One issue per confirmed finding, filed in one batch, only on Veljko's go. **Wait 14 days after filing** before any post that cites a finding.
- Anything that looks like a security flaw is reported privately through [GitHub's bug bounty program](https://bounty.github.com/), left out of every post, and gets 90 days.
- **Wording:** "at spec commit X on date Y", never "their docs are bad". First person, present run only.
- **Terms:** GitHub's [Acceptable Use Policies](https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies) allow research on public, non-personal information if the publications are open access. This repo, its method and its results are public. The low request rate follows the [Terms of Service](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service) clause on excessive API requests.

## Poll (fixed before any result)

> Guess: I took the read calls a coding agent makes through GitHub's own MCP server and checked each answer against GitHub's own API description. What share disagreed?

Options: Under 5% / 5% to 15% / 15% to 40% / Over 40%

The poll is about use case B, the largest group (78 testable operations). The bands match the Neon poll, so the series can be compared.

## What this is not

- It is not a sample of the whole API. It speaks only for the GET operations the named clients call.
- It is not a ranking against other APIs.
- It is not a security test.
- It is not a write test: no POST, PUT, PATCH or DELETE comes from the harness.
- It does not cover GraphQL. Several gh commands (for example `gh pr checks`) use GraphQL and add no REST operations.
- It is not a judgment on GitHub's docs as a whole. It measures one description, on one date, from one personal account and one read-only token.

## What changed from the Neon audit, and why

| Change | Why |
| --- | --- |
| Frame is the set of GETs that named clients call, not every GET | GitHub has 666 GETs, most unused by this audience. The question is about the calls real tools make. |
| E4 no longer needs "an undocumented input that fixes it" | In the Neon audit, the API rejected a valid request ("org_id is required") for a parameter the spec marks optional. Adding it led to a plan-limit 403, so nothing "fixed" it and the old E4 could not count it. |
| New E8, documented behaviour contradicted | Same case: the spec said what happens without the parameter, and the API did something else. E8 makes that countable, with the spec sentence quoted. |
| E7 is reported beside the metric | A guide error is not an operation's error. In the Neon audit, the one confirmed error (E7) was about a PATCH outside the GET census. |
| Fuzzing phase from the start | Neon deviation D1: the examples phase alone tested 4 of 68 operations. |
| Selection by operation-ID regex, plus method exclusion and a frame guard | In Schemathesis 4.32.7, include filters of different kinds widen the selection (found in this audit's first dry run: 647 operations selected instead of 102; the hook refused the other 545 before sending). |
| Redirects not followed | 302 answers point to download hosts outside api.github.com. |
| Token permissions taken from GitHub's own token data | Neon has no read-only key. GitHub does, and its data says exactly which permission each operation needs. |
| The spec is MIT, so it can be quoted with attribution | Neon's spec said "Proprietary". |
| Results per use case | The use case is the real-world anchor of each number. |
