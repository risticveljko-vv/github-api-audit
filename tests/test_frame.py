"""Offline tests for scripts/frame.py: the client-to-operation mapping and the eligibility rule.
They use small inline fixtures, so they need neither the downloaded spec nor the client sources."""
import csv
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import frame  # noqa: E402

W = frame.WILD


def op(oid, deprecated=False, cloud=False, params=()):
    o = {"operationId": oid, "x-github": {"githubCloudOnly": cloud, "category": oid.split("/")[0]},
         "parameters": [{"name": p, "in": "path", "required": True, "schema": {"type": "string"}} for p in params]}
    if deprecated:
        o["deprecated"] = True
    return o


SPEC = frame.Spec({
    "openapi": "3.0.3",
    "paths": {
        "/repos/{owner}/{repo}": {"get": op("repos/get", params=("owner", "repo"))},
        "/repos/{owner}/{repo}/contents/{path}": {
            "get": op("repos/get-content", params=("owner", "repo")) | {"parameters": [
                {"name": "owner", "in": "path"}, {"name": "repo", "in": "path"},
                {"name": "path", "in": "path", "x-multi-segment": True}]}},
        "/repos/{owner}/{repo}/releases/latest": {"get": op("repos/get-latest-release", params=("owner", "repo"))},
        "/repos/{owner}/{repo}/releases/{release_id}": {
            "get": op("repos/get-release", params=("owner", "repo", "release_id")),
            "delete": op("repos/delete-release", params=("owner", "repo", "release_id"))},
        "/repos/{owner}/{repo}/actions/secrets": {"get": op("actions/list-repo-secrets", params=("owner", "repo"))},
        "/repos/{owner}/{repo}/dependabot/secrets": {"get": op("dependabot/list-repo-secrets", params=("owner", "repo"))},
        "/repos/{owner}/{repo}/collaborators/{username}": {
            "put": op("repos/add-collaborator", params=("owner", "repo", "username"))},
        "/repos/{owner}/{repo}/actions/runs/{run_id}": {"get": op("actions/get-workflow-run", params=("owner", "repo", "run_id"))},
        "/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts": {
            "get": op("actions/list-workflow-run-artifacts", params=("owner", "repo", "run_id"))},
        "/repos/{owner}/{repo}/issues/{issue_number}": {
            "get": op("issues/get", params=("owner", "repo", "issue_number")),
            "patch": op("issues/update", params=("owner", "repo", "issue_number"))},
        "/repos/{owner}/{repo}/check-runs/{check_run_id}": {"get": op("checks/get", params=("owner", "repo", "check_run_id"))},
        "/repos/{owner}/{repo}/secret-scanning/alerts/{alert_number}": {
            "get": op("secret-scanning/get-alert", params=("owner", "repo", "alert_number"))},
        "/orgs/{org}/actions/secrets": {"get": op("actions/list-org-secrets", params=("org",))},
        "/orgs/{org}/{security_product}/{enablement}": {
            "post": op("orgs/enable-or-disable-security-product-on-all-org-repos", params=("org", "security_product", "enablement"))},
        "/orgs/{org}/rulesets": {"get": op("repos/get-org-rulesets", params=("org",))},
        "/enterprises/{enterprise}/teams": {"get": op("enterprise-teams/list", params=("enterprise",))},
        "/user/legacy": {"get": op("users/legacy", deprecated=True)},
    },
})

ALLOWED = {(o["method"], o["path"]) for oid, o in SPEC.ops.items() if oid != "checks/get"}
NEEDS = {
    ("GET", "/repos/{owner}/{repo}"): ["repository:metadata:read"],
    ("GET", "/orgs/{org}/actions/secrets"): ["organization:organization_secrets:read"],
    ("GET", "/repos/{owner}/{repo}/actions/secrets"): ["repository:secrets:read"],
    ("GET", "/repos/{owner}/{repo}/dependabot/secrets"): ["repository:dependabot_secrets:write"],
}


class Helpers(unittest.TestCase):
    def test_kebab(self):
        self.assertEqual(frame.kebab("getContent"), "get-content")
        self.assertEqual(frame.kebab("listForRepo"), "list-for-repo")
        self.assertEqual(frame.kebab("get"), "get")

    def test_norm(self):
        self.assertEqual(frame.norm("/repos/{owner}/{repo}/pages/deployments/{deploymentId}"),
                         "/repos/{}/{}/pages/deployments/{}")


class Match(unittest.TestCase):
    def test_literal_beats_parameter(self):
        # 'latest' is a literal in the spec; it must not also match {release_id}.
        self.assertEqual(SPEC.match(["repos", W, W, "releases", "latest"]), ["/repos/{owner}/{repo}/releases/latest"])

    def test_variable_on_literal_expands(self):
        # gh: JoinPath("repos", owner, repo, string(app), "secrets"), app = actions | dependabot | ...
        self.assertEqual(SPEC.match(["repos", W, W, W, "secrets"]),
                         ["/repos/{owner}/{repo}/actions/secrets", "/repos/{owner}/{repo}/dependabot/secrets"])

    def test_literal_in_parameter_loses(self):
        # 'secrets' landing in {enablement} of an all-parameter template is a different endpoint.
        self.assertEqual(SPEC.match(["orgs", W, W, "secrets"]), ["/orgs/{org}/actions/secrets"])

    def test_multi_segment_parameter(self):
        self.assertEqual(SPEC.match(["repos", W, W, "contents", ".github", "workflows", "ci.yml"]),
                         ["/repos/{owner}/{repo}/contents/{path}"])

    def test_no_match(self):
        self.assertEqual(SPEC.match(["repos", W, W, "nothing", "here"]), [])


class Octokit(unittest.TestCase):
    def run_on(self, text):
        return list(frame.extract_octokit(text, SPEC))

    def test_rest_and_bare_forms(self):
        hits = self.run_on("await octokit.rest.repos.getContent({})\nconst r = await this.octokit.repos.get({})")
        self.assertEqual([(h[0], h[4]) for h in hits], [(1, ["repos/get-content"]), (2, ["repos/get"])])

    def test_not_endpoint_methods(self):
        text = ("const {owner} = github.context.repo\n"
                "rpc.request('github.actions.results.api.v1.ArtifactService')\n"
                "await octokit.paginate.iterator(x)")
        self.assertEqual(self.run_on(text), [])

    def test_unknown_method_in_known_scope(self):
        hits = self.run_on("github.rest.repos.renamedLongAgo()")
        self.assertEqual(hits[0][3:], (None, None))


class Route(unittest.TestCase):
    def test_route_with_query_template(self):
        hits = list(frame.extract_route("request('GET /repos/{owner}/{repo}/actions/runs/{run_id}/artifacts{?name}', {", SPEC))
        self.assertEqual(hits[0][3:], ("GET", ["actions/list-workflow-run-artifacts"]))

    def test_route_not_in_spec(self):
        hits = list(frame.extract_route("request('POST /auth')", SPEC))
        self.assertIsNone(hits[0][4])


class GoGithub(unittest.TestCase):
    def test_table_and_calls(self):
        with tempfile.TemporaryDirectory() as d:
            pathlib.Path(d, "repos.go").write_text(
                "// Get fetches a repository.\n"
                "//meta:operation GET /repos/{owner}/{repo}\n"
                "func (s *RepositoriesService) Get(ctx context.Context, owner, repo string) {\n}\n"
                "func (s *RepositoriesService) helper() {\n}\n")
            pathlib.Path(d, "repos_test.go").write_text(
                "//meta:operation DELETE /repos/{owner}/{repo}\nfunc (s *RepositoriesService) Gone() {}\n")
            table = frame.go_github_table(d)
        self.assertEqual(table[("Repositories", "Get")], [("GET", "/repos/{owner}/{repo}")])
        self.assertEqual(table[("Repositories", "helper")], [])
        self.assertNotIn(("Repositories", "Gone"), table)
        hits = list(frame.extract_go_github(
            "repo, _, err := client.Repositories.Get(ctx, owner, name)\nx := strings.Repeat.Foo(1)", SPEC, table))
        self.assertEqual([(h[0], h[4]) for h in hits], [(1, ["repos/get"])])


class GoPath(unittest.TestCase):
    def run_on(self, text):
        return list(frame.extract_go_path(text, SPEC))

    def test_method_named_later_in_function(self):
        text = ('func list() {\n'
                '\tpath, err := safeurl.JoinPath("repos", repo.RepoOwner(), repo.RepoName(), "actions", "runs", runID)\n'
                '\tif err != nil {\n\t\treturn err\n\t}\n'
                '\terr = client.REST(repo.RepoHost(), "GET", path, nil, &result)\n'
                '}\n')
        hits = self.run_on(text)
        self.assertEqual([(h[1], h[3], h[4]) for h in hits], [("go-path", "GET", ["actions/get-workflow-run"])])

    def test_method_not_taken_from_next_function(self):
        text = ('func a() string {\n\tp, _ := safeurl.JoinPath("repos", o, r, "issues", n)\n\treturn p\n}\n'
                'func b() {\n\tclient.REST(h, "PATCH", p, nil, nil)\n}\n')
        hits = self.run_on(text)
        self.assertEqual((hits[0][3], hits[0][4]), (None, None))  # GET and PATCH both exist: unresolved

    def test_only_method_fallback(self):
        text = 'func a() string {\n\tp, _ := safeurl.JoinPath("repos", o, r, "releases", "latest")\n\treturn p\n}\n'
        hits = self.run_on(text)
        self.assertEqual((hits[0][1], hits[0][3], hits[0][4]),
                         ("go-path-only-method", "GET", ["repos/get-latest-release"]))

    def test_sprintf_literal(self):
        text = 'req, _ := client.NewRequest(ctx, http.MethodGet, fmt.Sprintf("repos/%s/%s/issues/%d", o, r, n), nil)\n'
        hits = self.run_on(text)
        self.assertEqual(hits[0][3:], ("GET", ["issues/get"]))

    def test_words_that_are_not_paths(self):
        text = ('cmd.Flags().StringVarP(&opts.Actor, "user", "u", "", "Filter by user")\n'
                'q := fmt.Sprintf("app/%s", name)\nurl := "issues/new"\n')
        self.assertEqual([h[4] for h in self.run_on(text)], [None])  # only "issues/new" reads as a path, and maps to nothing


class RustFormat(unittest.TestCase):
    def test_repo_holds_owner_and_name(self):
        text = ('let url = format!("{api_url}/repos/{repo}/releases/latest");\n'
                'let u = format!("{api_url}/repos/{repo}/contents/{}?ref={commit}", path);\n'
                '#[cfg(test)]\nmod tests { let x = "/repos/{repo}/releases/{id}"; }\n')
        hits = list(frame.extract_rust_format(text, SPEC, "GET"))
        self.assertEqual([h[4] for h in hits], [["repos/get-latest-release"], ["repos/get-content"]])


class Eligibility(unittest.TestCase):
    def reason(self, oid):
        status, reason, *_ = frame.eligibility(SPEC, oid, ALLOWED, NEEDS)
        return status, reason

    def test_reasons(self):
        self.assertEqual(self.reason("repos/get"), ("test", ""))
        self.assertEqual(self.reason("users/legacy"), ("excluded", "deprecated"))
        self.assertEqual(self.reason("enterprise-teams/list"), ("skip", "plan"))
        self.assertEqual(self.reason("checks/get"), ("skip", "auth"))
        self.assertEqual(self.reason("dependabot/list-repo-secrets"), ("skip", "write"))
        self.assertEqual(self.reason("actions/list-org-secrets"), ("skip", "org"))
        self.assertEqual(self.reason("repos/get-org-rulesets"), ("skip", "org"))
        self.assertEqual(self.reason("secret-scanning/get-alert"), ("skip", "id"))
        self.assertEqual(self.reason("actions/get-workflow-run"), ("test", ""))


class Build(unittest.TestCase):
    def test_frame_rows_carry_use_case_and_client(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = pathlib.Path(d, "a"), pathlib.Path(d, "b")
            (a / "src").mkdir(parents=True)
            (b / "src" / "__tests__").mkdir(parents=True)
            (a / "src" / "main.ts").write_text("await github.rest.repos.get()\nawait github.rest.issues.update()\n")
            (b / "src" / "x.ts").write_text("await octokit.rest.repos.get()\nawait octokit.rest.issues.get()\n")
            (b / "src" / "__tests__" / "x.test.ts").write_text("await octokit.rest.actions.getWorkflowRun()\n")
            clients = [
                {"client_id": "a", "use_case": "A", "repo": "o/a", "ref": "v1", "pin": "0" * 40,
                 "scope": "src/**/*.ts", "extractors": "octokit;route", "default_method": ""},
                {"client_id": "b", "use_case": "B", "repo": "o/b", "ref": "v1", "pin": "1" * 40,
                 "scope": "src/**/*.ts", "extractors": "octokit", "default_method": ""},
            ]
            rows, calls = frame.build(SPEC, clients, {}, ALLOWED, NEEDS, roots={"a": a, "b": b})
        by = {r["operation_id"]: r for r in rows}
        self.assertEqual(set(by), {"repos/get", "issues/get"})  # PATCH issues/update is not a GET; test file ignored
        self.assertEqual((by["repos/get"]["use_cases"], by["repos/get"]["clients"]), ("A;B", "a;b"))
        self.assertEqual(by["issues/get"]["use_cases"], "B")
        self.assertTrue(by["repos/get"]["first_source"].startswith("https://github.com/o/a/blob/" + "0" * 40))
        self.assertEqual(len(calls), 4)


class ClientList(unittest.TestCase):
    """clients.csv is part of the method: check its shape, not its content."""

    def test_rows(self):
        with open(ROOT / "clients.csv", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len({r["client_id"] for r in rows}), len(rows))
        for r in rows:
            self.assertIn(r["use_case"], {"A", "B", "C"}, r["client_id"])
            self.assertTrue(r["scope"], r["client_id"])
            self.assertTrue(set(r["extractors"].split(";")) <= {"octokit", "route", "go-github", "go-path", "rust-format"})
            if r["repo"].startswith("npm:"):
                self.assertRegex(r["pin"], r"^sha512-[A-Za-z0-9+/=]+$")
            else:
                self.assertRegex(r["pin"], r"^[0-9a-f]{40}$", r["client_id"])
            if "rust-format" in r["extractors"]:
                self.assertIn(r["default_method"], {"GET"})


if __name__ == "__main__":
    unittest.main()
