import json
import unittest
from unittest.mock import patch

import httpx2
import openai

from interpretation import Interpretation, InterpretationError, request_interpretation


MODEL = "openai/gpt-oss-120b:free"
KEY = "sk-or-v1-test-key"
PAYLOAD = {
    "student_context": {"question": "How does X relate to Y?", "hypothesis": None},
    "evidence": {"counts.valid": {"value": 3}, "regression.slope": {"value": 2}},
}
ANSWER = {
    "conclusion": "Y increased with X in these observations.",
    "hypothesis_assessment": "not_provided",
    "evidence": [
        {"explanation": "The line slopes upward.", "evidence_ids": ["regression.slope"]},
        {"explanation": "The result comes from a small sample.", "evidence_ids": ["counts.valid"]},
    ],
    "limitations": ["Three pairs give limited evidence.", "The fit alone cannot establish causation."],
    "improvements": ["Measure Y at more values of X."],
    "missing_context": [],
    "context_advice": {
        "research_question": "Specify the observed X range.",
        "hypothesis": "Predict how Y will change as X increases in a future test.",
        "method_notes": "I measured Y using [instrument] at [X settings].",
    },
}


def response(content, status="completed"):
    return {
        "id": "resp_test", "object": "response", "status": status,
        "created_at": 0, "model": MODEL,
        "output": [{
            "id": "msg_test", "type": "message", "role": "assistant",
            "status": status, "content": [content],
        }],
    }


def output_text(value):
    return {"type": "output_text", "text": json.dumps(value), "annotations": []}


class InterpretationTests(unittest.TestCase):
    def mock_transport(self, handler):
        real_client = openai.OpenAI

        def client(**kwargs):
            http_client = httpx2.Client(transport=httpx2.MockTransport(handler))
            return real_client(**kwargs, http_client=http_client)

        return patch("interpretation.openai.OpenAI", side_effect=client)

    def test_one_server_request_with_real_sdk_parsing(self):
        def handler(request):
            self.assertEqual(str(request.url), "https://openrouter.ai/api/v1/responses")
            body = json.loads(request.content)
            self.assertEqual(body["model"], MODEL)
            self.assertEqual(body["provider"], {
                "require_parameters": True,
                "max_price": {"prompt": 0, "completion": 0, "request": 0},
            })
            self.assertNotIn("models", body)
            self.assertIs(body["store"], False)
            self.assertEqual(body["max_output_tokens"], 4000)
            self.assertNotIn("tools", body)
            self.assertNotIn("reasoning", body)
            self.assertEqual(body["input"][0]["role"], "developer")
            self.assertEqual(body["input"][1]["role"], "user")
            self.assertEqual(json.loads(body["input"][1]["content"]), PAYLOAD)
            text_format = body["text"]["format"]
            self.assertTrue(text_format["strict"])
            evidence_statement = text_format["schema"]["$defs"]["EvidenceStatement"]
            ids = evidence_statement["properties"]["evidence_ids"]["items"]["enum"]
            self.assertCountEqual(ids, PAYLOAD["evidence"])
            self.assertIn("context_advice", text_format["schema"]["required"])
            return httpx2.Response(200, json=response(output_text(ANSWER)))

        with self.mock_transport(handler) as constructor:
            interpretation = request_interpretation(PAYLOAD, KEY, MODEL)
        constructor.assert_called_once()
        self.assertEqual(constructor.call_args.kwargs["timeout"], 30.0)
        self.assertEqual(constructor.call_args.kwargs["max_retries"], 0)
        self.assertIsInstance(interpretation, Interpretation)
        self.assertEqual(interpretation.model_dump(), ANSWER)

    def test_particle_free_skips_optional_reasoning(self):
        def handler(request):
            body = json.loads(request.content)
            self.assertEqual(body["reasoning"], {"effort": "none"})
            return httpx2.Response(200, json=response(output_text(ANSWER)))

        with self.mock_transport(handler):
            request_interpretation(PAYLOAD, KEY, "particle-ai/particle-1:free")

    def test_missing_key_never_constructs_sdk_client(self):
        with patch("interpretation.openai.OpenAI") as constructor:
            with self.assertRaisesRegex(InterpretationError, "OPENAI_API_KEY"):
                request_interpretation(PAYLOAD, "", MODEL)
        constructor.assert_not_called()

    def test_nonfree_model_and_wrong_provider_key_never_reach_sdk(self):
        with patch("interpretation.openai.OpenAI") as constructor:
            for model in ("openai/gpt-oss-120b", "openrouter/auto", "openai/model:floor:free"):
                with self.subTest(model=model), self.assertRaisesRegex(InterpretationError, "free model"):
                    request_interpretation(PAYLOAD, KEY, model)
            with self.assertRaisesRegex(InterpretationError, "OpenRouter API key"):
                request_interpretation(PAYLOAD, "sk-proj-test-key", MODEL)
        constructor.assert_not_called()

    def test_transport_errors_are_safe_and_not_retried(self):
        for failure, message in [
            (401, "API key"), (403, "access"), (404, "model"),
            (429, "rate limit or quota"), (500, "provider error"),
            (httpx2.ReadTimeout, "timed out"), (httpx2.ConnectError, "connect"),
        ]:
            calls = []

            def handler(request):
                calls.append(request)
                if isinstance(failure, int):
                    return httpx2.Response(failure, json={"error": {"message": "SECRET"}})
                raise failure("SECRET", request=request)

            with self.subTest(failure=failure), self.mock_transport(handler):
                with self.assertRaisesRegex(InterpretationError, message) as error:
                    request_interpretation(PAYLOAD, KEY, MODEL)
                self.assertNotIn("SECRET", str(error.exception))
                self.assertEqual(len(calls), 1)

    def test_bad_results_are_rejected(self):
        cases = [
            ({}, "incomplete or invalid"),
            (response(output_text({**ANSWER, "context_advice": {}})), "incomplete or invalid"),
            ({"status": "completed", "output": [{"type": "message", "content": [{}]}]}, "incomplete or invalid"),
            (response(output_text({**ANSWER, "evidence": [ANSWER["evidence"][0],
                {"explanation": "Malformed ID", "evidence_ids": [" counts.valid "]}]})), "unknown evidence"),
            (response(output_text({**ANSWER, "evidence": [ANSWER["evidence"][0],
                {"explanation": "Unseen group", "evidence_ids": ["groups.99"]}]})), "unknown evidence"),
            (response(output_text({**ANSWER, "evidence": [ANSWER["evidence"][0],
                {"explanation": "Missing evidence", "evidence_ids": []}]})), "incomplete or invalid"),
            (response(output_text({**ANSWER, "hypothesis_assessment": "supported"})), "hypothesis"),
            (response({"type": "refusal", "refusal": "SECRET"}), "declined"),
            (response(output_text(ANSWER), "incomplete"), "incomplete"),
            (response({"type": "output_text", "text": "{", "annotations": []}, "incomplete"), "incomplete or invalid"),
            (response(output_text({**ANSWER, "conclusion": 123})), "incomplete or invalid"),
        ]
        for body, message in cases:
            with self.subTest(message=message):
                with self.mock_transport(lambda request: httpx2.Response(200, json=body)):
                    with self.assertRaisesRegex(InterpretationError, message) as error:
                        request_interpretation(PAYLOAD, KEY, MODEL)
                    self.assertNotIn("SECRET", str(error.exception))

    def test_nonfinite_payload_is_rejected_before_request(self):
        with patch("interpretation.openai.OpenAI") as constructor:
            with self.assertRaisesRegex(InterpretationError, "nonfinite"):
                request_interpretation({**PAYLOAD, "bad": float("nan")}, KEY, MODEL)
        constructor.assert_not_called()
