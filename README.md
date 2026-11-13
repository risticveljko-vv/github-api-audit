# github-api-audit

Does GitHub's REST API do what its OpenAPI description says, for the read calls that real tools make?

Second audit in "A content engineer's stack, checked". GitHub is where my repos, READMEs, releases and CI live. My CI starts with actions/checkout and sets up its toolchain with mise. My coding-agent sessions read and write GitHub through gh. So the question is practical: when an agent or a workflow reads GitHub's API description literally, does the API behave as described?

- Method and rules, fixed before any result: [PREREGISTRATION.md](PREREGISTRATION.md) (**frozen 2026-11-13**)
- Which operations, and why: [FRAME.md](FRAME.md), [frame.csv](frame.csv) (145 GET operations, 102 testable), [calls.csv](calls.csv) (every client call site, linked to its line), [clients.csv](clients.csv) (the pinned clients)
- Frozen spec: `api.github.com.2026-03-10.json` from [github/rest-api-description](https://github.com/github/rest-api-description) at commit `bd6df26`, MIT licence. `sh scripts/fetch-spec.sh` downloads it and checks the SHA-256.
- Setup log (test repo, token; no secrets): [SETUP.md](SETUP.md)
- Deviations from the pre-registration: [DEVIATIONS.md](DEVIATIONS.md)
- Harness (Schemathesis config, GET-only and frame guards, runner): [harness/](harness/)
- Run sheet: [RUNSHEET.md](RUNSHEET.md)

Status: method frozen 2026-11-13. Nothing has been sent to api.github.com yet.

## Commands

| Command | What it does |
| --- | --- |
| `mise run setup` | Installs the pinned Node tools |
| `mise run check` | Syntax checks; no network |
| `mise run test` | Offline tests: the client-to-operation mapping, the eligibility rule, the Run 0 rules on a fixture |
| `mise run frame` | Fetches the spec, GitHub's token data and the pinned clients (github.com and npm, not the API), recomputes the frame and fails if it changed |
| `mise run dry-run` | The harness against a local Prism mock; sends nothing to GitHub |
| `mise run test:live` | Run 1 against api.github.com. Only after the freeze |

Tools (pinned): Spectral 6.17.0, Redocly CLI 2.72.0, Prism 5.16.0 (`npm ci`), Schemathesis 4.32.7 (`uvx --from schemathesis==4.32.7 st`), Node 22, Python 3.13. Every step runs in the foreground. Nothing is scheduled or left running.

## Licence notes

The GitHub REST API description is © GitHub, MIT licence. GitHub's token-permission data comes from [github/docs](https://github.com/github/docs) (code under MIT). Neither is committed here; the scripts download them from commit-pinned URLs.
