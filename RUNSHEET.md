# Run sheet

Every step runs in the foreground. Nothing is scheduled or left running. ⟦V⟧ = Veljko does it. ⟦C⟧ = Claude does it. Nothing calls api.github.com before step 5.

## 0. Decisions first (⟦V⟧, about 10 min) — done 2026-11-13, all as recommended; recorded in PREREGISTRATION.md

The decisions and Claude's recommendations are in the handoff report and repeated here in short:

1. Spec version: 2026-03-10 (recommended) or 2022-11-28 (the default without the version header).
2. Client list: approve `clients.csv` as it is, or add clients before the freeze. Use case C has only 10 testable operations.
3. Account: your own `risticveljko-vv` (recommended) or a separate account.
4. Token: one fine-grained read-only token on the test repo (recommended). No classic token, no organization.
5. Names: test repo `api-audit-test`, audit repo `github-api-audit`.
6. Spec copy: not committed (recommended; the commit-pinned URL and SHA are enough), or committed gzipped (about 1.5 MB).
7. Freeze route: make this repo public on risticveljko-vv (recommended, as for Neon).
8. Poll: use case B, same bands as Neon (recommended).
9. Error codes: the new E4 and E8 (recommended), or Neon's E1 to E7 unchanged.

## 1. Test repo (⟦V⟧ in the GitHub web UI, about 25 min; ⟦C⟧ writes each step into SETUP.md)

Create these in this order, so that the issue is #1 and the pull request is #2.

1. New **public** repo `api-audit-test` on risticveljko-vv, with a README. Default branch `main`.
2. Add `.github/workflows/seed.yml` with the content of `setup/seed.yml` from this repo (web editor, commit to `main`). This is the second commit, so the compare operation has two commits.
3. **Issue #1**, title "Audit seed issue", body "Seed data for an API audit." Add one comment.
4. **Pull request #2**: edit README on a new branch `seed-pr`, open the PR into `main`. Add one review with one line comment (review type "Comment"; you cannot approve your own PR). Do not merge.
5. **Annotated tag and release.** The web UI makes lightweight tags, and `git/get-tag` needs an annotated one, so the tag comes from a local clone of the test repo: `git pull && git tag -a v0.0.1 -m "Audit seed" && git push origin v0.0.1`. Then Releases → Draft a new release → choose the existing tag `v0.0.1` → publish.
6. **Variables and secrets** (Settings → Secrets and variables → Actions): repo variable `AUDIT_VAR` = `1`; repo secret `AUDIT_DUMMY` = `not-a-secret`.
7. **Environment** `audit` (Settings → Environments → New environment): environment variable `AUDIT_VAR` = `1`, environment secret `AUDIT_DUMMY` = `not-a-secret`.
8. **Ruleset** (Settings → Rules → Rulesets → New branch ruleset): name `audit-main`, enforcement Active, target the default branch, rule "Restrict deletions".
9. **Seed run:** Actions → seed → Run workflow. Wait for a green run. It creates a run, a job, logs, a cache, an artifact and a deployment to `audit`.
10. **Gist:** if your account has no public gist, create one (one file, any harmless text).

## 2. Token (⟦V⟧, about 5 min)

Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token.

- Name `github-api-audit`. Expiration 30 days. Resource owner `risticveljko-vv`.
- Repository access: **Only select repositories** → `api-audit-test`.
- Repository permissions, all **Read-only**: Actions, Administration, Agent secrets, Code scanning alerts, Commit statuses, Contents, Dependabot alerts, Dependabot secrets, Deployments, Environments, Issues, Metadata, Pull requests, Repository security advisories, Secret scanning alerts, Secrets, Variables.
- Account permissions, **Read-only**: Codespaces user secrets, Starring.
- Paste it into `.env` as `GITHUB_AUDIT_TOKEN=...` (copy `.env.example`). Claude checks that the variable name exists, never the value.

## 3. Freeze (⟦C⟧, then ⟦V⟧ makes the repo public)

- `mise run frame`: re-downloads the spec and the token data at the pinned commits, checks every SHA-256, re-fetches the pinned clients, and confirms `frame.csv` and `calls.csv` reproduce.
- Note whether github/rest-api-description `main` has moved since `bd6df26`. The pinned commit stays the target either way.
- Set the status in `PREREGISTRATION.md` to FROZEN with the date, fill in decisions from step 0, commit.
- ⟦V⟧ creates the public repo `github-api-audit` and pushes. **No check runs before this push.**

## 4. Run 0: static (⟦C⟧, about 1 h, no calls to GitHub)

- `npm run static:spectral` and `npm run static:redocly`, then triage E5 leads for the 102 testable operations. Whole-spec counts as context.
- E7: compare the hand-written guides in a local, read-only sparse clone of `github/docs` (`content/rest`) with the frozen spec.

## 5. Dry run, then Run 1 live (⟦C⟧ runs it while ⟦V⟧ watches, about 15 min)

- `mise run dry-run`: Prism mock, nothing sent to GitHub. Check 102 operations selected, all GET, all to 127.0.0.1.
- `mise run test:live`: 15 seed lookups, then about 113 test requests, 30 a minute at most, one at a time.
- Reports (JUnit, HAR with the token filtered) go to `runs/`, which git ignores.

## Day 2 (≥24 h later)

- Write the leads into `runs/leads.json`. `node --env-file=.env scripts/day2-repro.mjs runs/leads.json` reproduces each with curl (`--dry` prints the requests first).
- Rerun `mise run test:live` unchanged, at least 24 hours after Run 1.
- A second reader checks each lead against the frozen spec, given only the evidence and the definitions.
- ⟦V⟧ reads the findings. Filing uses the Schema Inaccuracy template on github/rest-api-description, one issue per finding, one batch, only on Veljko's go.
- Before anything is published: scrub saved responses of account data (`/user`, `/gists`, starred repos, orgs).
- Revoke the token. Earliest post that cites a finding: 14 days after filing.
