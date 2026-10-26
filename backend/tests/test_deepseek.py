"""DeepSeek transport, credential isolation and safe fallback regression tests."""
import json
import os
import unittest
from unittest.mock import patch

import httpx

from backend.contract import DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, active_model, propose
from backend.schema import Endpoint


class DeepSeekTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.endpoint = Endpoint(id="deepseek-test", method="GET", path="/api/tasks", status="missing", callers=[])
        with patch.dict(os.environ, {}, clear=True):
            self.template, _ = await propose(self.endpoint)

    async def invoke(self, handler):
        original = httpx.AsyncClient
        def factory(**kwargs):
            return original(**kwargs, transport=httpx.MockTransport(handler), trust_env=False)
        with patch.dict(os.environ, {"MODEL_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "sk-test-secret"}, clear=True), patch("backend.contract.httpx.AsyncClient", side_effect=factory):
            return await propose(self.endpoint)

    def test_default_and_override(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "deepseek-only", "XAI_API_KEY": "xai-other"}, clear=True):
            self.assertEqual(active_model(), (DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, "deepseek-only"))
        with patch.dict(os.environ, {"MODEL_PROVIDER": "deepseek", "DEEPSEEK_MODEL": "deepseek-v4-pro"}, clear=True):
            self.assertEqual(active_model(), (DEEPSEEK_BASE_URL, "deepseek-v4-pro", ""))

    async def test_missing_key_never_uses_other_credentials(self):
        with patch.dict(os.environ, {"MODEL_PROVIDER": "deepseek", "XAI_API_KEY": "xai-other", "MODEL_API_KEY": "generic-other"}, clear=True), patch("backend.contract.httpx.AsyncClient", side_effect=AssertionError("no request allowed")):
            draft, warnings = await propose(self.endpoint)
        self.assertEqual(draft.engine, "Schema inference")
        self.assertIn("DEEPSEEK_API_KEY", warnings[0])

    async def test_json_payload_and_success(self):
        def handler(request):
            self.assertEqual(str(request.url), DEEPSEEK_BASE_URL + "/responses")
            self.assertEqual(request.headers["authorization"], "Bearer sk-test-secret")
            payload = json.loads(request.content)
            self.assertEqual(payload["model"], DEEPSEEK_MODEL)
            self.assertEqual(payload["reasoning"], {"effort": "none"})
            self.assertEqual(payload["text"]["format"]["type"], "json_schema")
            self.assertTrue(payload["text"]["format"]["strict"])
            self.assertNotIn("reasoning_effort", payload)
            return httpx.Response(200, json={"status": "completed", "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": json.dumps(self.template.model_dump())}]}]})
        draft, warnings = await self.invoke(handler)
        self.assertEqual(draft.engine, "Model: " + DEEPSEEK_MODEL)
        self.assertEqual(warnings, [])

    async def test_truncation_repairs_once_then_falls_back(self):
        requests = []
        def handler(request):
            requests.append(request)
            return httpx.Response(200, json={"status": "incomplete", "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": json.dumps(self.template.model_dump())}]}]})
        with self.assertLogs("backend.contract", level="WARNING"):
            draft, warnings = await self.invoke(handler)
        self.assertEqual(len(requests), 2)
        self.assertEqual(draft.engine, "Schema inference")
        self.assertTrue(warnings)

    async def test_credit_error_is_actionable_and_redacted(self):
        def handler(request):
            return httpx.Response(402, json={"error": {"message": "Insufficient Balance for sk-test-secret"}})
        draft, warnings = await self.invoke(handler)
        self.assertEqual(draft.engine, "Schema inference")
        self.assertIn("Insufficient Balance", warnings[0])
        self.assertNotIn("sk-test-secret", warnings[0])
