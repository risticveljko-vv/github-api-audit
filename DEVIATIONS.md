# Deviations from the pre-registration

Each change to the frozen method, with when and why. The pre-registration is not frozen yet, so there are no deviations.

## Harness notes from the pre-freeze dry runs (not deviations)

All against a local Prism 5.16.0 mock of the frozen spec on 2026-11-13. Nothing was sent to GitHub.

- **Include filters widen the selection in Schemathesis 4.32.7.** The first dry run used `--include-method GET` plus one `--include-operation-id` per frame row. It selected 647 operations instead of 102. The frame guard in `harness/hooks.py` refused the other 545 before any request was sent. The harness now selects with one anchored `--include-operation-id-regex` and excludes non-GET methods with `--exclude-method-regex ^(?!GET$)`. The last dry run selected exactly 102 operations and sent 113 requests, all GET, all to 127.0.0.1.
- **Accept header per mode.** Prism answers 406 to `application/vnd.github+json`, so the mock run sends `application/json`. The live run sends GitHub's recommended `application/vnd.github+json`.
- **Redirects are not followed** (`--max-redirects 0`), so a 302 to a download host is checked as documented and never followed.
- **`comment_id` means two things.** It is an issue comment in `issues/get-comment` and a review comment in `pulls/get-review-comment`. The Schemathesis config sets it per operation; the dry run confirmed each operation got its own value.
- The mock's own failures (undocumented status codes, schema mismatches) say nothing about GitHub and are not leads.
