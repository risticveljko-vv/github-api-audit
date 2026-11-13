# Deviations from the pre-registration

Each change to the frozen method, with when and why.

## D1: test repo seeded with the `gh` CLI, not by hand (2026-11-13)

`PREREGISTRATION.md` says the test repo is set up by hand in the GitHub web UI and that Veljko starts the seed run by hand. On Veljko's go, Claude did the same ten steps of `RUNSHEET.md` with the `gh` CLI and a local git clone, and started the seed run with `gh workflow run`. The reason is time: about 3 minutes instead of about 25.

The objects, names, values and their order are the ones in the run sheet. Issue #1 and pull request #2 have the planned numbers. Setup used Veljko's normal `gh` login, which has write access. The audit token is still separate, fine-grained and read-only, and the harness still creates nothing. Nothing in the frame, the checks or the error codes changes. The values are in `SETUP.md`.

## Harness notes from the pre-freeze dry runs (not deviations)

All against a local Prism 5.16.0 mock of the frozen spec on 2026-11-13. Nothing was sent to GitHub.

- **Include filters widen the selection in Schemathesis 4.32.7.** The first dry run used `--include-method GET` plus one `--include-operation-id` per frame row. It selected 647 operations instead of 102. The frame guard in `harness/hooks.py` refused the other 545 before any request was sent. The harness now selects with one anchored `--include-operation-id-regex` and excludes non-GET methods with `--exclude-method-regex ^(?!GET$)`. The last dry run selected exactly 102 operations and sent 113 requests, all GET, all to 127.0.0.1.
- **Accept header per mode.** Prism answers 406 to `application/vnd.github+json`, so the mock run sends `application/json`. The live run sends GitHub's recommended `application/vnd.github+json`.
- **Redirects are not followed** (`--max-redirects 0`), so a 302 to a download host is checked as documented and never followed.
- **`comment_id` means two things.** It is an issue comment in `issues/get-comment` and a review comment in `pulls/get-review-comment`. The Schemathesis config sets it per operation; the dry run confirmed each operation got its own value.
- The mock's own failures (undocumented status codes, schema mismatches) say nothing about GitHub and are not leads.

## D2: repo private during the runs (2026-11-13 23:17 UTC until the runs end)

`PREREGISTRATION.md` freezes the method by making this repo public before any check runs. That happened: the freeze commit `dc466ee` was public from 2026-11-13. At 23:17 UTC the same day, before Run 0 or any call to GitHub, Veljko made the repo private for the duration of the runs. It becomes public again when the runs end, and this entry gets the date.

What this changes: while the repo is private, nobody outside can watch the method stay unchanged. What it does not change: the freeze commit and its hash stay in the history, and any later change to the method still has to appear in this file with its reason. Results were never going to be pushed during the runs (`runs/` is git-ignored), so the public record loses no results. Nothing in the frame, the checks or the error codes changes.
