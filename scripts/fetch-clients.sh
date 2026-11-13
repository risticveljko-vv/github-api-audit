#!/bin/sh
# Fetch every client in clients.csv at its pinned version into .clients/ (git-ignored), and check the pin.
#   git rows: shallow clone of the release tag; HEAD must equal the pinned commit.
#   npm rows: registry tarball; its sha512 must equal the pinned integrity (from the action's package-lock.json).
# Also fetches the resolver go-github at the version github-mcp-server's go.mod requires.
# Reads source code only. Makes no call to api.github.com.
# Usage: sh scripts/fetch-clients.sh
set -eu
GO_GITHUB_TAG=v92.0.0
GO_GITHUB_COMMIT=5149b4d74590b63154fcc43c4dac05e881f9aea3
mkdir -p .clients
clone() { # repo, tag, commit, dir
  if [ ! -d "$4/.git" ]; then git -c advice.detachedHead=false clone -q --depth 1 --branch "$2" "https://github.com/$1" "$4"; fi
  got=$(git -C "$4" rev-parse HEAD)
  [ "$got" = "$3" ] || { echo "pin mismatch for $1@$2: got $got, want $3" >&2; exit 1; }
  echo "$1@$2: $got ok"
}
tail -n +2 clients.csv | while IFS=, read -r id uc repo ref pin rest; do
  case "$repo" in
    npm:*)
      pkg=${repo#npm:}; name=${pkg#@}; name=$(echo "$name" | tr / -); dir=".clients/npm-$name-$ref"
      if [ ! -d "$dir/package" ]; then
        mkdir -p "$dir"; base=${pkg##*/}
        curl -fsSL -o "$dir.tgz" "https://registry.npmjs.org/$pkg/-/$base-$ref.tgz"
        got="sha512-$(openssl dgst -sha512 -binary "$dir.tgz" | openssl base64 -A)"
        [ "$got" = "$pin" ] || { echo "integrity mismatch for $pkg@$ref" >&2; exit 1; }
        tar xzf "$dir.tgz" -C "$dir"
      fi
      echo "$pkg@$ref: ok";;
    *) clone "$repo" "$ref" "$pin" ".clients/$(echo "$repo" | tr / _)";;
  esac
done
clone google/go-github "$GO_GITHUB_TAG" "$GO_GITHUB_COMMIT" .clients/google_go-github
grep -q "github.com/google/go-github/v92 v92.0.0" .clients/github_github-mcp-server/go.mod || { echo "go-github version in github-mcp-server's go.mod changed" >&2; exit 1; }
