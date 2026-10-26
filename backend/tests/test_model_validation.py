import json
import os
import unittest
from unittest.mock import patch

import httpx

from backend.contract import DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, active_model, propose
from backend.schema import Endpoint


class ModelValidationTests(unittest.IsolatedAsyncioTestCase):
    def test_deployed_secret_alias_and_canonical_key_precedence(self):
        with patch.dict(os.environ, {"MODEL_PROVIDER": "xai", "XAI_API_KEY": "", "GROK_API_KEY": "", "Grok_API_Key": "existing-secret"}):
            self.assertEqual(active_model()[2], "existing-secret")
        with patch.dict(os.environ, {"MODEL_PROVIDER": "xai", "XAI_API_KEY": "canonical-secret", "Grok_API_Key": "existing-secret"}):
            self.assertEqual(active_model()[2], "canonical-secret")

    async def asyncSetUp(self):
        self.endpoint = Endpoint(id="retry-test", method="GET", path="/api/tasks", status="missing", callers=[])
        with patch.dict(os.environ, {"MODEL_PROVIDER": "", "GROQ_API_KEY": "", "OPENROUTER_API_KEY": "", "MODEL_BASE_URL": "", "MODEL_NAME": ""}):
            self.template, _ = await propose(self.endpoint)

    async def invoke(self, handler):
        original = httpx.AsyncClient
        def factory(**kwargs):
            return original(**kwargs, transport=httpx.MockTransport(handler), trust_env=False)
        with patch.dict(os.environ, {"MODEL_PROVIDER": "groq", "GROQ_API_KEY": "private-test-key"}), patch("backend.contract.httpx.AsyncClient", side_effect=factory):
            return await propose(self.endpoint)

    async def test_invalid_output_is_corrected_once_and_validated(self):
        requests = []
        invalid = {**self.template.model_dump(), "questions": ["Question?"] * 9}
        def handler(request):
            requests.append(json.loads(request.content))
            value = invalid if len(requests) == 1 else self.template.model_dump()
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(value)}}]})
        with self.assertLogs("backend.contract", level="WARNING") as logs:
            draft, warnings = await self.invoke(handler)
        self.assertEqual(len(requests), 2)
        self.assertEqual(len(requests[1]["messages"]), 4)
        self.assertIn("questions:too_long", requests[1]["messages"][-1]["content"])
        self.assertEqual(draft.engine, "Model: qwen/qwen3.8-27b")
        self.assertEqual(warnings, [])
        self.assertNotIn("private-test-key", " ".join(logs.output))

    async def test_repeated_identity_changes_never_become_model_success(self):
        requests = []
        def handler(request):
            requests.append(request)
            value = {**self.template.model_dump(), "path": "/api/other"}
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(value)}}]})
        with self.assertLogs("backend.contract", level="WARNING"):
            draft, warnings = await self.invoke(handler)
        self.assertEqual(len(requests), 2)
        self.assertEqual(draft.path, "/api/tasks")
        self.assertEqual(draft.engine, "Schema inference")
        self.assertTrue(warnings)

    async def test_timeout_has_distinct_diagnostic_without_retry_or_key(self):
        requests = []
        def handler(request):
            requests.append(request)
            raise httpx.ReadTimeout("private-test-key", request=request)
        draft, warnings = await self.invoke(handler)
        self.assertEqual(len(requests), 1)
        self.assertEqual(draft.engine, "Schema inference")
        self.assertIn("timed out", warnings[0])
        self.assertNotIn("private-test-key", warnings[0])

class DeepSeekProviderTests(unittest.IsolatedAsyncioTestCase):
    def test_deepseek_provider_selection_and_model_override(self):
        with patch.dict(os.environ, {"MODEL_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "ds-key"}):
            self.assertEqual(active_model(), (DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, "ds-key"))
        with patch.dict(os.environ, {"MODEL_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "ds-key", "DEEPSEEK_MODEL": "deepseek-reasoner"}):
            self.assertEqual(active_model(), (DEEPSEEK_BASE_URL, "deepseek-reasoner", "ds-key"))

    def test_deepseek_key_never_reuses_grok_or_groq_credentials(self):
        with patch.dict(os.environ, {"MODEL_PROVIDER": "deepseek", "XAI_API_KEY": "xai-secret", "GROQ_API_KEY": "groq-secret"}):
            self.assertEqual(active_model(), (DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, ""))

    async def asyncSetUp(self):
        self.endpoint = Endpoint(id="deepseek-test", method="GET", path="/api/tasks", status="missing", callers=[])
        with patch.dict(os.environ, {"MODEL_PROVIDER": "", "DEEPSEEK_API_KEY": "", "GROQ_API_KEY": "", "OPENROUTER_API_KEY": "", "MODEL_BASE_URL": "", "MODEL_NAME": ""}):
            self.template, _ = await propose(self.endpoint)

    async def invoke(self, handler):
        original = httpx.AsyncClient
        def factory(**kwargs):
            return original(**kwargs, transport=httpx.MockTransport(handler), trust_env=False)
        with patch.dict(os.environ, {"MODEL_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "deepseek-test-key"}), patch("backend.contract.httpx.AsyncClient", side_effect=factory):
            return await propose(self.endpoint)

    async def test_deepseek_json_mode_request_and_successful_engine_label(self):
        requests = []
        def handler(request):
            requests.append(request)
            self.assertEqual(str(request.url), DEEPSEEK_BASE_URL + "/chat/completions")
            self.assertEqual(request.headers["authorization"], "Bearer deepseek-test-key")
            payload = json.loads(request.content)
            self.assertEqual(payload["model"], DEEPSEEK_MODEL)
            self.assertEqual(payload["response_format"], {"type": "json_object"})
            self.assertIn("max_tokens", payload)
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(self.template.model_dump())}}]})
        draft, warnings = await self.invoke(handler)
        self.assertEqual(len(requests), 1)
        self.assertEqual(draft.engine, "Model: " + DEEPSEEK_MODEL)
        self.assertEqual(warnings, [])

    async def test_missing_deepseek_key_uses_schema_inference(self):
        with patch.dict(os.environ, {"MODEL_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": ""}), patch("backend.contract.httpx.AsyncClient", side_effect=AssertionError("must not call provider without key")):
            draft, warnings = await propose(self.endpoint)
        self.assertEqual(draft.engine, "Schema inference")
        self.assertIn("DEEPSEEK_API_KEY", warnings[0])
