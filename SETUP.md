# Setup log

Nothing here was done by the harness. The plan was the GitHub web UI by hand. On Veljko's go, Claude did steps 1 to 10 of `RUNSHEET.md` with the `gh` CLI and a local git clone instead (deviation D1 in `DEVIATIONS.md`). Times are UTC, all on 2026-11-13.

| When | What | Value |
| --- | --- | --- |
| 2026-11-13 | Spec fetched at the pinned commit | SHA-256 `fc75cec7…e79611` (matches on a second download) |
| 22:58 | Test repo | `risticveljko-vv/api-audit-test`, public, default branch `main`. First commit `6d2347d` (README) |
| 22:59 | Seed commit (workflow added) | `b0b0c55`, `.github/workflows/seed.yml` identical to `setup/seed.yml` |
| 22:59 | Issue #1, one comment | comment ID 6867043779 |
| 22:59 | Pull request #2, one review with one line comment | branch `seed-pr`, not merged; review 5899245138 (Comment); line comment 4569627058 on README.md line 4 |
| 22:59 | Annotated tag `v0.0.1`, release `v0.0.1` | tag object `1b0cf50` on `b0b0c55`; release ID 444824765 |
| 22:59 | Repo variable `AUDIT_VAR`, repo secret `AUDIT_DUMMY` | `1`, `not-a-secret` |
| 22:59 | Environment `audit`, its variable and secret | same values |
| 22:59 | Ruleset `audit-main` | ID 27238729, Active, default branch, restrict deletions |
| 23:00 | Seed workflow run | run 43523720398, success; job, logs, cache, artifact `audit-seed` and a deployment to `audit` (status success) all present |
| 23:00 | Public gist | `cf6fa7b72426d2afa32b46ec15f16794` (the account had none) |
| | Fine-grained token `github-api-audit` | 30 days, `api-audit-test` only, read-only. Value never shown to Claude |

All 15 seed lookups of `harness/run.mjs` were replayed afterwards with GET requests through `gh` (not the audit token) and every one returned a value.
