"""Check one saved response body against the frozen description (used for deviation D5).

Usage:  uv run --with jsonschema==4.25.1 --with rfc3986-validator==0.1.1 python -I scripts/check-body.py \
            <path template> <status> <body.json>
Example: ... scripts/check-body.py /user/codespaces/secrets 200 runs/day2-.../NT-1.body.json

Reads spec/api.github.com.2026-03-10.json, takes the GET response schema for the path and status, inlines
every $ref, and validates the body with jsonschema (formats checked). Sends nothing anywhere. Exit code 1
when the status is not documented or the body breaks the schema.
"""
import json, sys
from jsonschema import Draft202012Validator, FormatChecker

SPEC = "spec/api.github.com.2026-03-10.json"

def inline(node, root, seen=()):
    if isinstance(node, dict):
        if "$ref" in node:
            ref = node["$ref"]
            if ref in seen:
                return {}
            target = root
            for part in ref.lstrip("#/").split("/"):
                target = target[part.replace("~1", "/").replace("~0", "~")]
            return inline(target, root, seen + (ref,))
        out = {k: inline(v, root, seen) for k, v in node.items()}
        if out.get("nullable") is True and "type" in out:  # OpenAPI 3.0 nullable
            out = {"anyOf": [{k: v for k, v in out.items() if k != "nullable"}, {"type": "null"}]}
        return out
    if isinstance(node, list):
        return [inline(v, root, seen) for v in node]
    return node

def main():
    path, status, body_file = sys.argv[1:4]
    spec = json.load(open(SPEC))
    responses = spec["paths"][path]["get"]["responses"]
    print(f"GET {path}: documented statuses {sorted(responses)}; got {status}")
    if status not in responses:
        print("RESULT: status not documented")
        return 1
    content = inline(responses[status], spec).get("content", {})
    if "application/json" not in content:
        print("RESULT: no JSON schema documented for this status")
        return 0
    schema = content["application/json"]["schema"]
    body = json.load(open(body_file))
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(body), key=lambda e: list(e.path))
    for e in errors[:20]:
        print(f"  at /{'/'.join(map(str, e.path))}: {e.message[:200]}")
    print(f"RESULT: {'matches the schema' if not errors else str(len(errors)) + ' schema error(s)'}")
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
