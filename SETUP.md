# Setup log

Everything here is done by hand in the GitHub web UI (or a local git command for the tag), not by the harness. Times are UTC. Nothing has been set up yet.

| When | What | Value |
| --- | --- | --- |
| 2026-11-13 | Spec fetched at the pinned commit | SHA-256 `fc75cec7…e79611` (matches on a second download) |
| | Test repo | `risticveljko-vv/api-audit-test`, public |
| | Seed commit (workflow added) | |
| | Issue #1, one comment | |
| | Pull request #2, one review with one line comment | |
| | Annotated tag `v0.0.1`, release `v0.0.1` | |
| | Repo variable `AUDIT_VAR`, repo secret `AUDIT_DUMMY` | |
| | Environment `audit`, its variable and secret | |
| | Ruleset `audit-main` | |
| | Seed workflow run | run ID read by the harness |
| | Public gist | |
| | Fine-grained token `github-api-audit` | 30 days, `api-audit-test` only, read-only. Value never shown to Claude |
