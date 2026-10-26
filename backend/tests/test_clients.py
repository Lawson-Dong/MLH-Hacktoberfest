"""Regression cases from realistic HTTP clients, rather than only literal demo calls."""
import unittest

from backend.detect import frontend_calls
from backend.github_source import MAX_FILES, MAX_TOTAL_BYTES, SourceFile, is_source, select_sources
from backend.main import scan_files

REPO = {"full_name": "example/app", "url": "https://github.com/example/app", "commit": "abc123", "demo": False}


class CommonClientTests(unittest.TestCase):
    def calls(self, *files):
        warnings = []
        calls = frontend_calls(list(files), REPO, warnings)
        return calls, warnings

    def test_imported_typed_wrapper_detects_get_post_and_route_matches(self):
        files = [
            SourceFile("src/http.ts", '''export async function api<T>(path: string, body?: unknown,) {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return response.json();
}'''),
            SourceFile("src/pages/Tasks.tsx", '''import { api as request } from '../http';
request<{ tasks: Task[]; total: number }>('/api/tasks');
request('/api/tasks', { title: 'Ship it', completed: false });
request(`/api/tasks/${task.id}`);
'''),
            SourceFile("backend/app.py", '''from fastapi import FastAPI
app = FastAPI()
@app.get('/api/tasks')
def tasks(): pass
@app.post('/api/tasks')
def create(): pass
'''),
        ]
        result = scan_files(REPO, files)
        self.assertEqual(result["stats"], {"files": 3, "calls": 3, "routes": 2, "matched": 2, "review": 1})
        by_key = {(e["method"], e["path"]): e for e in result["endpoints"]}
        self.assertEqual(by_key[("POST", "/api/tasks")]["request_fields"], {"title": "string", "completed": "boolean"})
        self.assertEqual(by_key[("GET", "/api/tasks")]["callers"][0]["line"], 2)
        self.assertEqual(by_key[("GET", "/api/tasks")]["callers"][0]["file"], "src/pages/Tasks.tsx")
        self.assertEqual(result["warnings"], [])

    def test_axios_instances_aliases_base_urls_and_generics(self):
        calls, warnings = self.calls(SourceFile("src/ui.ts", '''import http from 'axios';
const API = '/api/v1';
const client = http.create({baseURL: API});
client.get<Task[]>('/tasks');
client.patch(`/tasks/${taskId}`, { completed: true });
http.get<Health>('/health');
'''))
        self.assertEqual([(c["method"], c["path"]) for c in calls], [("GET", "/api/v1/tasks"), ("PATCH", "/api/v1/tasks/{taskId}"), ("GET", "/health")])
        self.assertEqual(calls[1]["request_fields"], {"completed": "boolean"})
        self.assertEqual(warnings, [])

    def test_named_imported_axios_instance(self):
        calls, warnings = self.calls(
            SourceFile("lib/http.ts", "export const client = axios.create({baseURL: '/api'});"),
            SourceFile("src/ui.ts", "import {client as http} from '../lib/http';\nhttp.get('/tasks');"),
        )
        self.assertEqual([(c["method"], c["path"]) for c in calls], [("GET", "/api/tasks")])
        self.assertEqual(warnings, [])

    def test_static_urls_and_simple_parameters(self):
        calls, warnings = self.calls(SourceFile("src/ui.mjs", '''const BASE = '/api';
const TASKS = BASE + '/tasks';
fetch(TASKS);
fetch(`${BASE}/tasks/${task.id}?limit=10`);
fetch(BASE + '/members/' + memberId);
'''))
        self.assertEqual([c["path"] for c in calls], ["/api/tasks", "/api/tasks/{task_id}", "/api/members/{memberId}"])
        self.assertEqual(warnings, [])

    def test_passthrough_options_and_fixed_method_wrappers(self):
        calls, warnings = self.calls(SourceFile("src/ui.ts", '''function request(url: string, options?: RequestInit) {
return fetch(url, options);
}
function remove(url: string) { return fetch(url, {method: 'DELETE'}); }
request('/api/tasks', {method: 'PATCH', body: JSON.stringify({completed: true})});
remove('/api/tasks/1');
'''))
        self.assertEqual([(c["method"], c["path"]) for c in calls], [("PATCH", "/api/tasks"), ("DELETE", "/api/tasks/1")])
        self.assertEqual(warnings, [])

    def test_arrow_wrappers_with_expression_and_block_bodies(self):
        calls, warnings = self.calls(SourceFile("src/ui.ts", '''const request = (url, options) => fetch(url, options);
const remove = async (url: string) => { return fetch(url, {method: 'DELETE'}); };
request('/api/tasks');
remove('/api/tasks/1');
'''))
        self.assertEqual([(c["method"], c["path"]) for c in calls], [("GET", "/api/tasks"), ("DELETE", "/api/tasks/1")])
        self.assertEqual(warnings, [])

    def test_unproven_clients_and_unsupported_methods_do_not_create_findings(self):
        calls, warnings = self.calls(SourceFile("src/ui.ts", '''api('/api/not-http');
function maybe(path) { if (enabled) return fetch(path); }
maybe('/api/conditional');
fetch('/api/dynamic', {method: METHOD});
const external = axios.create({baseURL: 'https://external.example'});
external.get('/api/users');
const dynamic = axios.create({baseURL: BASE_URL});
dynamic.get('/api/users');
fetch(`${process.env.BASE_URL}/api/users`);
fetch(`/api/${choose()}`);
'''))
        self.assertEqual(calls, [])
        self.assertGreaterEqual(len(warnings), 5)

    def test_wrapper_is_not_imported_from_unrelated_module(self):
        calls, _ = self.calls(
            SourceFile("lib/http.ts", "export function api(path) { return fetch(path); }"),
            SourceFile("src/ui.ts", "import {api} from 'other-package'; api('/api/fiction');"),
        )
        self.assertEqual(calls, [])

    def test_shadowed_url_constants_are_not_substituted(self):
        calls, warnings = self.calls(SourceFile("src/ui.ts", '''const URL = '/api/wrong';
function load(URL) { return fetch(URL); }
const OTHER = '/api/one';
function second() { const OTHER = '/api/two'; return fetch(OTHER); }
'''))
        self.assertEqual(calls, [])
        self.assertTrue(warnings)

    def test_empty_scan_has_explicit_coverage_warning(self):
        result = scan_files(REPO, [SourceFile("src/ui.ts", "unknownClient('/api/tasks');")])
        self.assertEqual(result["stats"]["calls"], 0)
        self.assertTrue(any("No supported" in warning for warning in result["warnings"]))

    def test_file_budget_preserves_frontend_and_backend_coverage(self):
        candidates = [{"path": f"backend/route_{i:03}.py", "size": 100} for i in range(90)]
        candidates += [{"path": "frontend/src/api.mjs", "size": 100}]
        selected = select_sources(candidates)
        self.assertEqual(len(selected), MAX_FILES)
        self.assertIn("frontend/src/api.mjs", [item["path"] for item in selected])
        self.assertTrue(any(item["path"].endswith(".py") for item in selected))
        self.assertLessEqual(sum(item["size"] for item in selected), MAX_TOTAL_BYTES)
        self.assertTrue(is_source("src/api.mjs"))
        self.assertTrue(is_source("src/api.cjs"))
        self.assertFalse(is_source("src/api.test.mjs"))
        self.assertFalse(is_source("tests/api.ts"))


if __name__ == "__main__":
    unittest.main()
