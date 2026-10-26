"""Verify Grok credential isolation and the native xAI Responses wire format."""
import json
import os
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from backend.app import app
from backend.contract import XAI_BASE_URL, XAI_MODEL, active_model, propose
from backend.schema import Endpoint


class XaiProviderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.endpoint = Endpoint(id="grok-test", method="GET", path="/api/tasks", status="missing", callers=[], response_fields={"id": "string"})
        with patch.dict(os.environ, {}, clear=True):
            self.template, _ = await propose(self.endpoint)

    def settings(self, **overrides):
        return {"MODEL_PROVIDER": "xai", "Grok_API_Key": "xai-test-secret", **overrides}

    def response(self, value, status="completed"):
        return {"status": status, "model": XAI_MODEL, "output": [
            {"type": "reasoning", "encrypted_content": "opaque-test-data"},
            {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": json.dumps(value)}]},
        ]}

    async def invoke(self, handler, **settings):
        original = httpx.AsyncClient
        def factory(**kwargs):
            return original(**kwargs, transport=httpx.MockTransport(handler), trust_env=False)
        with patch.dict(os.environ, self.settings(**settings), clear=True), patch("backend.contract.httpx.AsyncClient", side_effect=factory):
            return await propose(self.endpoint)

    def test_grok_provider_alias_and_existing_secret_select_xai(self):
        with patch.dict(os.environ, self.settings(MODEL_PROVIDER="grok", GROQ_API_KEY="groq-other-key", OPENROUTER_API_KEY="router-other-key", MODEL_BASE_URL="https://unrelated.example"), clear=True):
            self.assertEqual(active_model(), (XAI_BASE_URL, XAI_MODEL, "xai-test-secret"))

    def test_xai_key_auto_selection_and_model_override(self):
        with patch.dict(os.environ, self.settings(MODEL_PROVIDER="", XAI_API_KEY="canonical", XAI_MODEL="grok-4.7"), clear=True):
            self.assertEqual(active_model(), (XAI_BASE_URL, "grok-4.7", "canonical"))

    async def test_explicit_groq_never_uses_grok_secret_or_contacts_provider(self):
        with patch.dict(os.environ, self.settings(MODEL_PROVIDER="groq"), clear=True), patch("backend.contract.httpx.AsyncClient", side_effect=AssertionError("must not send Grok key to Groq")):
            draft, warnings = await propose(self.endpoint)
        self.assertEqual(draft.engine, "Schema inference")
        self.assertIn("GROQ_API_KEY", warnings[0])

    async def test_explicit_xai_without_key_never_uses_groq_credentials(self):
        with patch.dict(os.environ, {"MODEL_PROVIDER": "xai", "GROQ_API_KEY": "groq-other-key"}, clear=True), patch("backend.contract.httpx.AsyncClient", side_effect=AssertionError("must not reuse another provider's key")):
            draft, warnings = await propose(self.endpoint)
        self.assertEqual(draft.engine, "Schema inference")
        self.assertIn("XAI_API_KEY", warnings[0])

    async def test_native_responses_schema_and_successful_model_label(self):
        requests = []
        def handler(request):
            requests.append(request)
            self.assertEqual(str(request.url), XAI_BASE_URL + "/responses")
            self.assertEqual(request.headers["authorization"], "Bearer xai-test-secret")
            payload = json.loads(request.content)
            self.assertEqual(payload["model"], XAI_MODEL)
            self.assertEqual(payload["reasoning"], {"effort": "none"})
            self.assertFalse(payload["store"])
            self.assertEqual(payload["max_output_tokens"], 2400)
            self.assertNotIn("messages", payload)
            self.assertNotIn("reasoning_effort", payload)
            schema = payload["text"]["format"]
            self.assertTrue(schema["strict"])
            self.assertEqual(schema["type"], "json_schema")
            self.assertEqual(schema["schema"]["properties"]["path"]["const"], self.endpoint.path)
            self.assertEqual([item["role"] for item in payload["input"]], ["system", "user"])
            return httpx.Response(200, json=self.response(self.template.model_dump()))
        draft, warnings = await self.invoke(handler)
        self.assertEqual(len(requests), 1)
        self.assertEqual(draft.engine, "Model: " + XAI_MODEL)
        self.assertEqual(warnings, [])

    async def test_invalid_result_corrected_once_with_opaque_reasoning_preserved(self):
        requests = []
        invalid = {**self.template.model_dump(), "questions": ["Question?"] * 9}
        def handler(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json=self.response(invalid if len(requests) == 1 else self.template.model_dump()))
        with self.assertLogs("backend.contract", level="WARNING") as logs:
            draft, warnings = await self.invoke(handler)
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[1]["input"][2]["encrypted_content"], "opaque-test-data")
        self.assertEqual(requests[1]["input"][-1]["role"], "user")
        self.assertEqual(draft.engine, "Model: " + XAI_MODEL)
        self.assertFalse(warnings)
        self.assertNotIn("xai-test-secret", " ".join(logs.output))

    async def test_incomplete_or_identity_changed_output_never_claims_success(self):
        for status, value in [("incomplete", self.template.model_dump()), ("completed", {**self.template.model_dump(), "path": "/api/changed"})]:
            with self.subTest(status=status):
                requests = []
                def handler(request):
                    requests.append(request)
                    return httpx.Response(200, json=self.response(value, status))
                with self.assertLogs("backend.contract", level="WARNING"):
                    draft, warnings = await self.invoke(handler)
                self.assertEqual(len(requests), 2)
                self.assertEqual(draft.engine, "Schema inference")
                self.assertEqual(draft.path, self.endpoint.path)
                self.assertTrue(warnings)

    async def test_http_failures_do_not_retry_or_disclose_provider_body(self):
        for status in (401, 402, 403, 429):
            requests = []
            def handler(request):
                requests.append(request)
                return httpx.Response(status, json={"error": "xai-test-secret"})
            draft, warnings = await self.invoke(handler)
            self.assertEqual(len(requests), 1)
            self.assertEqual(draft.engine, "Schema inference")
            self.assertTrue(warnings)
            self.assertNotIn("xai-test-secret", " ".join(warnings))

    async def test_parameter_error_detail_is_visible_and_key_is_redacted(self):
        def handler(request):
            return httpx.Response(400, json={"error": {"message": "Unsupported schema for xai-test-secret"}})
        draft, warnings = await self.invoke(handler)
        self.assertEqual(draft.engine, "Schema inference")
        self.assertIn("Unsupported schema", warnings[0])
        self.assertIn("[redacted]", warnings[0])
        self.assertNotIn("xai-test-secret", warnings[0])

    def test_health_reports_grok_configuration(self):
        with patch.dict(os.environ, self.settings(), clear=True):
            health = TestClient(app).get("/api/health").json()
        self.assertTrue(health["model_configured"])
        self.assertEqual(health["engine"], XAI_MODEL)
