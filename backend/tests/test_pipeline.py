import io
import json
import os
import sys
import types
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from backend.app import app
from backend.detect import backend_routes, frontend_calls
from backend.github_source import SourceError, SourceFile, parse_repo_url
from backend.main import demo_scan

REPO = {"url": "https://github.com/example/repo", "commit": "abcdef", "demo": False}


class DetectionTests(unittest.TestCase):
    def test_demo_ignores_deployment_bytecode_and_binary_files(self):
        fixture = Path(__file__).parents[1] / "demo_repo"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(fixture, root / "demo_repo", ignore=shutil.ignore_patterns("__pycache__"))
            cache = root / "demo_repo" / "backend" / "__pycache__"
            cache.mkdir()
            (cache / "main.cpython-312.pyc").write_bytes(b"\xff\xfe\x00\x81")
            (root / "demo_repo" / "asset.bin").write_bytes(b"\xff\xfe")
            with patch("backend.main.__file__", str(root / "main.py")):
                result = demo_scan()
            self.assertEqual(result["stats"]["files"], 4)
            self.assertEqual(result["stats"]["calls"], 6)

    def test_demo_has_real_missing_mismatch_and_matches(self):
        scan = demo_scan()
        self.assertEqual(scan["stats"], {"files": 4, "calls": 6, "routes": 4, "matched": 3, "review": 3})
        by_path = {(item["method"], item["path"]): item for item in scan["endpoints"]}
        self.assertEqual(by_path[("POST", "/api/tasks")]["status"], "mismatch")
        first = scan["endpoints"][0]
        self.assertEqual(first["callers"][0]["line"], 10)
        self.assertEqual(first["frontend_owner"], "@alex-demo")
        self.assertTrue(first["response_is_array"])

    def test_nested_imported_router_prefixes_and_aliases(self):
        files = [
            SourceFile("backend/main.py", 'from fastapi import FastAPI as API\nfrom .routes import router as users\napp = API()\napp.include_router(users, prefix="/api/v1")\n'),
            SourceFile("backend/routes.py", 'from fastapi import APIRouter\nfrom .details import detail\nrouter = APIRouter(prefix="/users")\nrouter.include_router(detail, prefix="/{user_id}")\n@router.get("")\ndef users(): pass\n'),
            SourceFile("backend/details.py", 'from fastapi import APIRouter\ndetail = APIRouter()\n@detail.get("/tasks")\ndef tasks(): pass\n'),
        ]
        warnings = []
        routes = backend_routes(files, REPO, warnings)
        self.assertEqual({route["path"] for route in routes}, {"/api/v1/users", "/api/v1/users/{user_id}/tasks"})
        self.assertFalse(warnings)

    def test_comments_strings_dynamic_methods_and_external_urls_do_not_make_findings(self):
        source = '''// fetch('/api/comment')
const example = "fetch('/api/string')";
/* axios.post('/api/comment-two') */
fetch('/api/real?limit=10');
axios.patch(`/api/tasks/${taskId}`, { completed: true });
fetch('/api/dynamic', {method: METHOD});
fetch('https://external.example/api/users');
fetch(url);
'''
        warnings = []
        calls = frontend_calls([SourceFile("ui.ts", source)], REPO, warnings)
        self.assertEqual([(call["method"], call["path"]) for call in calls], [("GET", "/api/real"), ("PATCH", "/api/tasks/{taskId}")])
        self.assertEqual(len(warnings), 3)

    def test_parameter_names_match_across_languages(self):
        from backend.main import scan_files
        files = [SourceFile("ui.ts", 'fetch(`/api/users/${userId}`);'), SourceFile("app.py", 'from fastapi import FastAPI\napp=FastAPI()\n@app.get("/api/users/{user_id}")\ndef user(): pass')]
        scan = scan_files({**REPO, "full_name": "example/repo"}, files)
        self.assertEqual(scan["endpoints"][0]["status"], "matched")

    def test_nested_method_fields_are_not_http_methods(self):
        warnings = []
        calls = frontend_calls([SourceFile("ui.ts", '''fetch('/api/a', { body: JSON.stringify({method: 'DELETE'}), method: 'POST' });
fetch('/api/b', OPTIONS);
fetch('/api/c', {method});
fetch('/api/d', {headers: {'method': 'DELETE'}});''')], REPO, warnings)
        self.assertEqual([(call["method"], call["path"]) for call in calls], [("POST", "/api/a"), ("GET", "/api/d")])
        self.assertEqual(len(warnings), 2)

    def test_url_validation_restricts_to_public_github_repository_paths(self):
        self.assertEqual(parse_repo_url("https://github.com/Lawson-Dong/MLH-Hacktoberfest.git/"), ("Lawson-Dong", "MLH-Hacktoberfest"))
        for url in ["http://github.com/a/b", "https://evil.example/a/b", "https://github.com/a/b/tree/main", "https://github.com@evil.example/a/b", "https://github.com/a/.."]:
            with self.assertRaises(SourceError): parse_repo_url(url)


class ApiFlowTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.env = patch.dict(os.environ, {"MODEL_BASE_URL": "", "MODEL_NAME": "", "OPENROUTER_API_KEY": ""})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def draft(self, method="GET"):
        scan = self.client.get("/api/demo").json()
        endpoint = next(item for item in scan["endpoints"] if item["method"] == method and item["status"] != "matched")
        response = self.client.post("/api/contract", json={"endpoint": endpoint})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["contract"]

    def test_detect_review_approve_live_mock_verify_and_download(self):
        contract = self.draft()
        blocked = self.client.post("/api/mock", json={"contract": contract, "approved": False})
        self.assertEqual(blocked.status_code, 409)
        generated = self.client.post("/api/mock", json={"contract": contract, "approved": True})
        self.assertEqual(generated.status_code, 200, generated.text)
        mock = generated.json()
        response = self.client.get(mock["url"])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), contract["response_example"])
        self.assertEqual(response.headers["x-tritonteam-mock"], "true")
        self.assertEqual(self.client.post(mock["url"]).status_code, 405)
        valid = self.client.post("/api/verify", json={"contract": contract, "response": response.json()}).json()
        self.assertTrue(valid["valid"])
        invalid = self.client.post("/api/verify", json={"contract": contract, "response": [{"id": 123}]}).json()
        self.assertFalse(invalid["valid"])
        bundle = self.client.post("/api/export", json={"contract": contract, "approved": True})
        self.assertEqual(bundle.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
            self.assertIn("backend_skeleton.py", archive.namelist())
            openapi = json.loads(archive.read("openapi.json"))
            self.assertIn(contract["path"], openapi["paths"])
            module = types.ModuleType("test_mock")
            with patch.dict(sys.modules, {"test_mock": module}):
                exec(compile(archive.read("mock_server.py"), "mock_server.py", "exec"), module.__dict__)
            live = TestClient(module.app).get("/api/projects/test/tasks")
            self.assertEqual(live.status_code, 200, live.text)
            self.assertEqual(live.json(), contract["response_example"])
            skeleton = types.ModuleType("test_skeleton")
            with patch.dict(sys.modules, {"test_skeleton": skeleton}):
                exec(compile(archive.read("backend_skeleton.py"), "backend_skeleton.py", "exec"), skeleton.__dict__)

    def test_post_mock_validates_request_fields(self):
        contract = self.draft("POST")
        mock = self.client.post("/api/mock", json={"contract": contract, "approved": True}).json()
        self.assertEqual(self.client.post(mock["url"], json={}).status_code, 422)
        response = self.client.post(mock["url"], json=mock["request_example"])
        self.assertEqual(response.status_code, 200, response.text)

    def test_invalid_contract_data_returns_validation_error(self):
        contract = self.draft()
        contract["response_example"] = "wrong type"
        self.assertEqual(self.client.post("/api/mock", json={"contract": contract, "approved": True}).status_code, 422)
        contract["response_schema"] = {"$ref": "https://external.example/schema"}
        self.assertEqual(self.client.post("/api/mock", json={"contract": contract, "approved": True}).status_code, 422)

    def test_scan_errors_and_invalid_mock_url_are_actionable(self):
        self.assertEqual(self.client.post("/api/scan", json={"repo_url": "https://evil.example/a/b"}).status_code, 400)
        self.assertEqual(self.client.get("/api/playground/garbage/api/tasks").status_code, 404)



class ModelProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_groq_selected_over_old_provider_credentials(self):
        from backend.contract import active_model
        with patch.dict(os.environ, {
            "MODEL_PROVIDER": "groq", "GROQ_API_KEY": "groq-test",
            "OPENROUTER_API_KEY": "openrouter-old",
            "MODEL_BASE_URL": "https://router.huggingface.co/v1",
            "MODEL_NAME": "google/gemma-3-27b-it",
            "MODEL_API_KEY": "huggingface-old",
        }):
            self.assertEqual(active_model(), (
                "https://api.groq.com/openai/v1", "qwen/qwen3.8-27b", "groq-test"
            ))

    async def test_selected_groq_without_key_never_calls_provider(self):
        from backend.contract import propose
        from backend.schema import Endpoint
        endpoint = Endpoint(id="groq-missing", method="GET", path="/api/tasks",
                            status="missing", callers=[], response_fields={"id": "string"})
        with patch.dict(os.environ, {
            "MODEL_PROVIDER": "groq", "GROQ_API_KEY": "",
            "OPENROUTER_API_KEY": "old-invalid-key",
        }), patch("backend.contract.httpx.AsyncClient", side_effect=AssertionError("must not call Groq without a key")):
            draft, warnings = await propose(endpoint)
        self.assertEqual(draft.engine, "Schema inference")
        self.assertIn("GROQ_API_KEY", " ".join(warnings))

    async def test_groq_json_mode_returns_validated_contract(self):
        from backend.contract import propose
        from backend.schema import Endpoint
        endpoint = Endpoint(id="groq-test", method="GET", path="/api/tasks",
                            status="missing", callers=[], response_fields={"id": "string"})
        with patch.dict(os.environ, {"MODEL_PROVIDER": "", "GROQ_API_KEY": "", "OPENROUTER_API_KEY": "", "MODEL_BASE_URL": "", "MODEL_NAME": ""}):
            template, _ = await propose(endpoint)
        original = httpx.AsyncClient
        def factory(**kwargs):
            def respond(request):
                self.assertEqual(request.url.host, "api.groq.com")
                self.assertEqual(request.headers.get("authorization"), "Bearer groq-test")
                payload = json.loads(request.content)
                self.assertEqual(payload["model"], "qwen/qwen3.8-27b")
                self.assertEqual(payload["response_format"], {"type": "json_object"})
                self.assertEqual(payload["reasoning_effort"], "none")
                self.assertEqual(payload["max_completion_tokens"], 2400)
                return httpx.Response(200, json={
                    "choices": [{"message": {"content": template.model_dump_json()}}]
                })
            return original(**kwargs, transport=httpx.MockTransport(respond))
        with patch.dict(os.environ, {
            "MODEL_PROVIDER": "groq", "GROQ_API_KEY": "groq-test",
            "OPENROUTER_API_KEY": "old-invalid-key",
        }), patch("backend.contract.httpx.AsyncClient", side_effect=factory):
            draft, warnings = await propose(endpoint)
        self.assertEqual(warnings, [])
        self.assertEqual(draft.engine, "Model: qwen/qwen3.8-27b")

    async def test_free_gemma_key_takes_precedence(self):
        from backend.contract import active_model
        with patch.dict(os.environ, {
            "OPENROUTER_API_KEY": "test-free-token",
            "MODEL_BASE_URL": "https://router.huggingface.co/v1",
            "MODEL_NAME": "google/gemma-3-27b-it",
            "MODEL_API_KEY": "test-hf-token",
        }):
            self.assertEqual(active_model(), (
                "https://openrouter.ai/api/v1",
                "google/gemma-3-27b-it:free",
                "test-free-token",
            ))

    async def test_huggingface_402_reports_billing_issue_without_key_leak(self):
        from backend.contract import propose
        from backend.schema import Endpoint
        endpoint = Endpoint(id="billing-test", method="GET", path="/api/tasks",
                            status="missing", callers=[], response_fields={"id": "string"})
        original = httpx.AsyncClient
        def factory(**kwargs):
            def respond(request):
                self.assertEqual(request.url.host, "router.huggingface.co")
                self.assertEqual(request.headers.get("authorization"), "Bearer test-hf-token")
                return httpx.Response(402, json={"error": "payment required"})
            return original(**kwargs, transport=httpx.MockTransport(respond))
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "", "MODEL_BASE_URL": "https://router.huggingface.co/v1",
                                    "MODEL_NAME": "google/gemma-3-27b-it", "MODEL_API_KEY": "test-hf-token"}):
            with patch("backend.contract.httpx.AsyncClient", side_effect=factory):
                result, warnings = await propose(endpoint)
        self.assertEqual(result.engine, "Schema inference")
        self.assertIn("HTTP 402", " ".join(warnings))
        self.assertNotIn("test-hf-token", " ".join(warnings))

    async def test_free_gemma_valid_response_identified_as_model(self):
        from backend.contract import propose
        from backend.schema import Endpoint
        endpoint = Endpoint(id="free-test", method="GET", path="/api/tasks",
                            status="missing", callers=[], response_fields={"id": "string"})
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "", "MODEL_BASE_URL": "", "MODEL_NAME": ""}):
            template, _ = await propose(endpoint)
        original = httpx.AsyncClient
        def factory(**kwargs):
            def respond(request):
                self.assertEqual(request.url.host, "openrouter.ai")
                self.assertEqual(request.headers.get("authorization"), "Bearer test-free-token")
                return httpx.Response(200, json={"choices": [{"message": {
                    "content": template.model_dump_json()
                }}]})
            return original(**kwargs, transport=httpx.MockTransport(respond))
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-free-token"}):
            with patch("backend.contract.httpx.AsyncClient", side_effect=factory):
                result, warnings = await propose(endpoint)
        self.assertFalse(warnings)
        self.assertEqual(result.engine, "Model: google/gemma-3-27b-it:free")


class GitHubBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_source_reads_are_pinned_and_never_send_token_to_raw_host(self):
        from backend.github_source import fetch_repository
        requests = []
        def handler(request):
            requests.append(request)
            path = request.url.path
            if request.url.host == "raw.githubusercontent.com":
                self.assertNotIn("authorization", request.headers)
                self.assertIn("/abc123/", path)
                return httpx.Response(200, text="fetch('/api/tasks');")
            self.assertEqual(request.headers.get("authorization"), "Bearer test-fixture-token")
            if path.endswith("/commits/main"):
                return httpx.Response(200, json={"sha": "abc123"})
            if path.endswith("/git/trees/abc123"):
                return httpx.Response(200, json={"tree": [{"type": "blob", "path": "src/ui.ts", "size": 30}, {"type": "blob", "path": "node_modules/vendor.js", "size": 30}], "truncated": False})
            return httpx.Response(200, json={"default_branch": "main", "private": False})
        original = httpx.AsyncClient
        def client_factory(**kwargs):
            return original(**kwargs, transport=httpx.MockTransport(handler), trust_env=False)
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-fixture-token"}), patch("backend.github_source.httpx.AsyncClient", side_effect=client_factory):
            repo, files, warnings = await fetch_repository("https://github.com/example/repo")
        self.assertEqual(repo["commit"], "abc123")
        self.assertEqual([file.path for file in files], ["src/ui.ts"])
        self.assertEqual(len(requests), 4)
        self.assertFalse(warnings)

    async def test_rate_limit_and_private_repository_errors(self):
        from backend.github_source import fetch_repository
        original = httpx.AsyncClient
        for status, payload, expected in [(403, {}, 429), (200, {"private": True}, 403)]:
            def factory(**kwargs):
                return original(**kwargs, transport=httpx.MockTransport(lambda request: httpx.Response(status, json=payload)), trust_env=False)
            with patch("backend.github_source.httpx.AsyncClient", side_effect=factory):
                with self.assertRaises(SourceError) as raised:
                    await fetch_repository("https://github.com/example/repo")
                self.assertEqual(raised.exception.status, expected)


if __name__ == "__main__":
    unittest.main()
