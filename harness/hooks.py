# Second guard: refuse anything but GET before a request leaves the harness.
# Third guard: refuse any operation that is not a 'test' row of frame.csv. run.mjs passes the allowed
# operations as labels ("GET /repos/{owner}/{repo}") in AUDIT_ALLOWED_OPS, one per line.
import os

import schemathesis

ALLOWED = set(filter(None, os.environ.get("AUDIT_ALLOWED_OPS", "").split("\n")))


@schemathesis.hook
def before_call(ctx, case, **kwargs):
    if case.method.upper() != "GET":
        raise RuntimeError(f"GET-only guard: refused {case.method} {case.path}")
    if case.operation.label not in ALLOWED:
        raise RuntimeError(f"frame guard: refused {case.operation.label} (not a 'test' row of frame.csv)")
