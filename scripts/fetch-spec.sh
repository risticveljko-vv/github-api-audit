#!/bin/sh
# Fetch the frozen inputs and check each one against its SHA-256.
#   1. GitHub's REST description for api.github.com, API version 2026-03-10, bundled JSON,
#      from github/rest-api-description at a fixed commit (MIT licence).
#   2. GitHub's fine-grained token data for the same API version, from github/docs at a fixed
#      commit. It says which operations a fine-grained token can call and with which permission.
#      The frame uses it for eligibility only (code in github/docs is MIT).
# A raw.githubusercontent.com URL at a commit SHA does not change, so a re-fetch must give the
# same bytes. This makes no call to api.github.com.
# Usage: sh scripts/fetch-spec.sh
set -eu
SPEC_COMMIT=bd6df26d2a0104874fe5025a25ebcde356413364
SPEC_FILE=descriptions/api.github.com/api.github.com.2026-03-10.json
SPEC_SHA=fc75cec70017bf6c0a4e29dfd7121df42321290ef29bd65f288875e823e79611
DOCS_COMMIT=66f5790db61fc9d07eb9b7d3525f2994cd2910b9
DOCS_DIR=src/github-apps/data/fpt-2026-03-10
FGPAT_SHA=74646a724c14d1eb56ada0fca41e68e384f97b63552ec9e165c2a7a833316c6e
FGPAT_PERM_SHA=0c6820918c4d630d7c3b3c3e316164c6338db2fecc7e270096db603bb472f74e

mkdir -p spec
get() { # url, out, sha
  if [ -f "$2" ] && [ "$(shasum -a 256 "$2" | cut -d' ' -f1)" = "$3" ]; then echo "$2: present, SHA matches"; return; fi
  curl -fsSL -o "$2" "$1"
  got=$(shasum -a 256 "$2" | cut -d' ' -f1)
  if [ "$got" != "$3" ]; then echo "SHA mismatch for $2: got $got, want $3" >&2; exit 1; fi
  echo "$2: downloaded, SHA matches"
}
get "https://raw.githubusercontent.com/github/rest-api-description/$SPEC_COMMIT/$SPEC_FILE" spec/api.github.com.2026-03-10.json "$SPEC_SHA"
get "https://raw.githubusercontent.com/github/docs/$DOCS_COMMIT/$DOCS_DIR/fine-grained-pat.json" spec/fine-grained-pat.json "$FGPAT_SHA"
get "https://raw.githubusercontent.com/github/docs/$DOCS_COMMIT/$DOCS_DIR/fine-grained-pat-permissions.json" spec/fine-grained-pat-permissions.json "$FGPAT_PERM_SHA"
