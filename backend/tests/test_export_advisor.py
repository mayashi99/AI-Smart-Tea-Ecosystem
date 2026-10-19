import json
import os
import unittest
from unittest.mock import patch

from app.services.component04 import export_advisor


class ExportAdvisorLLMTests(unittest.TestCase):
    def setUp(self):
        self.context = {
            "question": "How should I plan export volume?",
            "preferences": {},
            "evidence": [
                {
                    "id": "E1",
                    "title": "Export outlook",
                    "source": "forecast.csv",
                    "text": "Forecast exports increase by 8%.",
                }
            ],
        }
        self.response_content = json.dumps({
            "summary": "Use staged shipment commitments.",
            "recommendations": [{
                "title": "Stage shipments",
                "action": "Confirm capacity before each shipment.",
                "reason": "The forecast shows an increase.",
                "evidence_ids": ["E1"],
            }],
        })

    def _response(self):
        class Response:
            def raise_for_status(self):
                pass

            def json(inner_self):
                return {"choices": [{"message": {"content": self.response_content}}]}

        return Response()

    def test_uses_local_ollama_defaults_and_retrieved_evidence(self):
        captured = {}

        def post(url, **kwargs):
            captured["url"] = url
            captured.update(kwargs)
            return self._response()

        with patch.dict(os.environ, {}, clear=True), patch.object(
            export_advisor.requests, "post", side_effect=post
        ):
            result, status = export_advisor._call_llm(self.context)

        self.assertEqual(status, "llm_rag")
        self.assertEqual(result["recommendations"][0]["evidence_ids"], ["E1"])
        self.assertEqual(captured["url"], "http://localhost:11434/v1/chat/completions")
        self.assertEqual(captured["json"]["model"], "llama3.1")
        self.assertEqual(
            json.loads(captured["json"]["messages"][1]["content"])["evidence"],
            self.context["evidence"],
        )

    def test_api_key_defaults_to_openai_endpoint_and_model(self):
        captured = {}
        api_key = "local-test-token"

        def post(url, **kwargs):
            captured["url"] = url
            captured.update(kwargs)
            return self._response()

        with patch.dict(os.environ, {"LLM_API_KEY": api_key}, clear=True), patch.object(
            export_advisor.requests, "post", side_effect=post
        ):
            _, status = export_advisor._call_llm(self.context)

        self.assertEqual(status, "llm_rag")
        self.assertEqual(captured["url"], "https://api.openai.com/v1/chat/completions")
        self.assertEqual(captured["json"]["model"], "gpt-4o-mini")
        self.assertEqual(captured["headers"]["Authorization"], f"Bearer {api_key}")

    def test_sends_configured_api_key(self):
        captured = {}

        def post(url, **kwargs):
            captured["url"] = url
            captured.update(kwargs)
            return self._response()

        with patch.dict(os.environ, {
            "LLM_API_BASE_URL": "https://llm.example/v1",
            "LLM_MODEL": "example-model",
            "LLM_API_KEY": "test-key",
        }), patch.object(export_advisor.requests, "post", side_effect=post):
            _, status = export_advisor._call_llm(self.context)

        self.assertEqual(status, "llm_rag")
        self.assertEqual(captured["url"], "https://llm.example/v1/chat/completions")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer test-key")


if __name__ == "__main__":
    unittest.main()
