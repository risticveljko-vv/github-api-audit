# Deviations from the pre-registration

Each change to the frozen method, with when and why.

## D1: test repo seeded with the `gh` CLI, not by hand (2026-11-13)

`PREREGISTRATION.md` says the test repo is set up by hand in the GitHub web UI and that Veljko starts the seed run by hand. On Veljko's go, Claude did the same ten steps of `RUNSHEET.md` with the `gh` CLI and a local git clone, and started the seed run with `gh workflow run`. The reason is time: about 3 minutes instead of about 25.

The objects, names, values and their order are the ones in the run sheet. Issue #1 and pull request #2 have the planned numbers. Setup used Veljko's normal `gh` login, which has write access. The audit token is still separate, fine-grained and read-only, and the harness still creates nothing. Nothing in the frame, the checks or the error codes changes. The values are in `SETUP.md`.

## D3: first live attempt sent without the token; void and rerun (2026-11-13)

The first live attempt ran from 23:40:40 to 23:44:24 UTC. The 15 seed lookups in `harness/run.mjs` used the token. The 111 test requests did not: they went out with no `Authorization` header and no `X-GitHub-Api-Version` header. GitHub answered 15 of them with 401 ("Requires authentication") and 46 with 403 (the rate limit for unauthenticated calls, 60 an hour per IP address).

Cause: `harness/run.mjs` set `Accept` with a `-H` flag. In Schemathesis 4.32.7, a header on the command line replaces the whole `headers` table of the config file, so the token and the API version header were dropped. The dry runs did not show it, because the mock needs no token and nothing checked the headers. The first dry run (17:21 UTC, before the `-H` flag was added) still had both headers.

This attempt is void. None of its responses is used as a lead or a finding, because it did not test the frozen method (no token, and no API version, so GitHub answered with its default version).

Fix, before any rerun: all headers now live in `harness/schemathesis.toml` (`Accept` comes from `AUDIT_ACCEPT`, set per mode); `run.mjs` passes no `-H` flag; and a fourth guard in `harness/hooks.py` refuses any request without a non-empty token or the API version header. The dry run after the fix (23:45 UTC) sent 113 GET requests to 127.0.0.1, each with both headers. Run 1 is the next live run with this harness. The 24-hour repeat counts from Run 1.

Request budget: this attempt sent 126 requests to api.github.com (15 lookups, 111 tests). With Run 1 and the day-2 repeat at about 128 each, the audit stays under its 400-request limit (about 382).

## Harness notes from the pre-freeze dry runs (not deviations)

All against a local Prism 5.16.0 mock of the frozen spec on 2026-11-13. Nothing was sent to GitHub.

- **Include filters widen the selection in Schemathesis 4.32.7.** The first dry run used `--include-method GET` plus one `--include-operation-id` per frame row. It selected 647 operations instead of 102. The frame guard in `harness/hooks.py` refused the other 545 before any request was sent. The harness now selects with one anchored `--include-operation-id-regex` and excludes non-GET methods with `--exclude-method-regex ^(?!GET$)`. The last dry run selected exactly 102 operations and sent 113 requests, all GET, all to 127.0.0.1.
- **Accept header per mode.** Prism answers 406 to `application/vnd.github+json`, so the mock run sends `application/json`. The live run sends GitHub's recommended `application/vnd.github+json`.
- **Redirects are not followed** (`--max-redirects 0`), so a 302 to a download host is checked as documented and never followed.
- **`comment_id` means two things.** It is an issue comment in `issues/get-comment` and a review comment in `pulls/get-review-comment`. The Schemathesis config sets it per operation; the dry run confirmed each operation got its own value.
- **Redocly keeps only 100 problems by default** (found in Run 0, 2026-11-13 23:36 UTC, before any call to GitHub). Its JSON report held 100 of 1,588 problems. `static:redocly` now passes `--max-problems 100000`, and the rerun holds all 1,588. Spectral was not affected. Run 0 counts use the full report.
- The mock's own failures (undocumented status codes, schema mismatches) say nothing about GitHub and are not leads.

## D2: repo private for four minutes before Run 0 (2026-11-13, 23:17 to 23:21 UTC)

`PREREGISTRATION.md` freezes the method by making this repo public before any check runs. The freeze commit `dc466ee` was public from 2026-11-13. At 23:17 UTC Veljko made the repo private, meaning to keep it private during the runs. At 23:21 UTC he reversed that decision, and the repo went public again. The original method stands: the repo stays public for the whole audit.

No check ran and no call went to GitHub while the repo was private. The only commits made in that time are this note and `baecd30` (the setup log and D1), and both are public now. Nothing in the frame, the checks or the error codes changes.
