#!/bin/sh
# Offline: prove the Run 0 rules fire. tests/fixtures/bad-example.json holds one example that breaks its own
# schema (a string where the schema says integer). Each linter must report exactly that, and nothing else.
set -eu
out=$(mktemp -d)
node_modules/.bin/spectral lint tests/fixtures/bad-example.json --ruleset rules/.spectral.yaml --format json --output "$out/s.json" >/dev/null 2>&1 || true
node_modules/.bin/redocly lint tests/fixtures/bad-example.json --config rules/redocly.yaml --format json > "$out/r.json" 2>/dev/null || true
node -e '
const fs = require("fs");
const s = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
const r = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const sc = s.map(x => x.code), rc = (r.problems || []).map(x => x.ruleId);
const ok = sc.length === 1 && sc[0] === "oas3-valid-media-example" && rc.length === 1 && rc[0] === "no-invalid-media-type-examples";
console.log(`spectral: ${JSON.stringify(sc)}  redocly: ${JSON.stringify(rc)}  ${ok ? "rules fire as expected" : "UNEXPECTED"}`);
process.exit(ok ? 0 : 1);
' "$out/s.json" "$out/r.json"
