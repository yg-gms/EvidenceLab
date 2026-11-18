import json
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient
from workspace_api import app


class WorkspaceTests(unittest.TestCase):
    client = TestClient(app)
    csv = "X,Y,note\n1,4,private note\n2,3,b\n3,2,c\n4,1,d\n8,12,e\n9,,f\n"
    inputs = {"csv": csv, "x": "X", "y": "Y"}

    def post(self, action, **extra):
        result = self.client.post("/api/" + action, json={**self.inputs, **extra})
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    @patch("workspace_api.ask_question")
    def test_exclusion_restore_replay_and_source_integrity(self, provider):
        raw = self.post("dataset")
        self.assertEqual(raw["columns"][1]["missing"], 1)
        initial = self.post("analysis")
        self.assertEqual(initial["flags"], [5])
        self.assertGreater(initial["fit"]["slope"], 1)
        changed = self.post("analysis", excluded=[5])
        self.assertEqual(changed["missing"], 1)
        self.assertEqual(changed["fit"]["slope"], -1)
        self.assertEqual(changed["original_slope"], initial["fit"]["slope"])
        self.assertEqual(sum(b["count"] for b in changed["histogram"]), 4)
        self.assertEqual(self.post("analysis", first_trials=4)["fit"]["slope"], -1)
        self.assertEqual(self.post("analysis"), initial)
        self.assertEqual(self.post("dataset"), raw)
        provider.assert_not_called()

    def test_degenerate_and_invalid_data(self):
        self.assertIsNone(self.post("analysis", csv="X,Y\n1,2\n1,4")["fit"])
        self.assertIsNone(self.post("analysis", csv="X,Y\n1,4\n2,4")["fit"]["r"])
        empty = self.post("analysis", excluded=[1,2,3,4,5])
        self.assertEqual(empty["points"], [])
        self.assertEqual(empty["histogram"], [])
        for bad in [{"csv": "X,Y\n"}, {"excluded": [6]}, {"y": "X"}]:
            self.assertEqual(self.client.post("/api/analysis", json={**self.inputs, **bad}).status_code, 400)
        data = self.post("dataset", csv="X,Y\n1,inf\n2,-inf")
        self.assertEqual(data["columns"][1]["infinite"], 2)
        self.assertEqual(data["rows"][0][1], "∞")

    @patch("workspace_api.configuration", return_value=("sk-or-v1-test", "acme/test:free"))
    @patch("workspace_api.ask_question", return_value="The four included trials slope downward.")
    def test_chat_receives_updated_evidence_and_history(self, provider, _):
        history = [{"role": "user", "content": "What changed?"}]
        reply = self.post("chat", excluded=[5], research="How does X relate to Y?",
                          history=history, question="Explain the slope.")
        self.assertIn("downward", reply["answer"])
        context, actual_history, question, *_ = provider.call_args.args
        self.assertEqual(actual_history, history)
        self.assertEqual(question, "Explain the slope.")
        self.assertEqual(context["relationship"]["evidence"]["regression.slope"]["value"], -1)
        self.assertEqual(context["user_excluded_count"], 1)
        self.assertNotIn("private note", json.dumps(context))
        self.assertNotIn(self.csv, json.dumps(context))

    @patch("workspace_api.configuration", return_value=("", "acme/test:free"))
    def test_missing_key_is_recoverable(self, _):
        response = self.client.post("/api/chat", json={**self.inputs, "question": "Explain."})
        self.assertEqual(response.status_code, 503)
        self.assertIn("OPENAI_API_KEY", response.json()["error"])
        self.assertIsNotNone(self.post("analysis")["fit"])
