from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import unittest

import pandas as pd

from calculations import linear_regression, prepare_relationship_data
from evidence import build_evidence, fingerprint


def build(data, question="How does X relate to Y?"):
    x, y = data.columns[:2]
    pairs = prepare_relationship_data(data, x, y)
    result = linear_regression(pairs, x, y)
    return build_evidence(pairs, x, y, len(data), result, question, "", "")


class EvidenceTests(unittest.TestCase):
    def test_summary_preserves_only_selected_evidence(self):
        data = pd.read_csv(StringIO(
            "mass.g,extension:cm,other\n1,3,PRIVATE\n2,5,PRIVATE\n3,7,PRIVATE\n"
            "inf,9,PRIVATE\n5,,PRIVATE\n"
        ))
        payload = build(data)
        serialized = json.dumps(payload, allow_nan=False)
        facts = payload["evidence"]
        self.assertEqual(payload["variables"], {"x": "mass.g", "y": "extension:cm"})
        self.assertEqual(payload["student_context"]["question"], "How does X relate to Y?")
        self.assertEqual(facts["counts.uploaded"]["value"], 5)
        self.assertEqual(facts["counts.valid"]["value"], 3)
        self.assertEqual(facts["counts.excluded"]["value"], 2)
        self.assertEqual(facts["counts.unique_x"]["value"], 3)
        self.assertEqual(facts["ranges.x"]["value"], [1.0, 3.0])
        self.assertEqual(facts["ranges.y"]["value"], [3.0, 7.0])
        self.assertEqual(facts["regression.slope"]["value"], 2)
        self.assertEqual(facts["regression.intercept"]["value"], 1)
        self.assertAlmostEqual(facts["regression.r"]["value"], 1)
        self.assertEqual(facts["regression.r_squared"]["value"], 1)
        self.assertTrue(facts["facts.fewer_than_five_pairs"]["value"])
        self.assertEqual(facts["counts.single_trial_groups"]["value"], 3)
        self.assertIsNone(facts["groups.1"]["value"]["sample_sd"])
        self.assertEqual(facts["groups.1"]["sample_sd_status"], "undefined")
        self.assertNotIn("PRIVATE", serialized)
        self.assertNotIn('"other"', serialized)
        self.assertNotIn("fitted_values", serialized)
        self.assertFalse(payload["group_summary"]["groups_omitted"])

    def test_sample_uses_all_finite_trials(self):
        sample = pd.read_csv(Path(__file__).resolve().parents[1] / "sample.csv")
        facts = build(sample)["evidence"]
        self.assertEqual(facts["counts.valid"]["value"], 8)
        self.assertEqual(facts["counts.excluded"]["value"], 1)
        self.assertAlmostEqual(facts["groups.1"]["value"]["sample_sd"], 0.1)
        self.assertAlmostEqual(facts["groups.3"]["value"]["mean"], 3.2)
        self.assertEqual(facts["groups.3"]["value"]["count"], 2)

    def test_constant_y_and_two_pair_statuses(self):
        facts = build(pd.DataFrame({"x": [1, 2, 3], "y": [7, 7, 7]}))["evidence"]
        self.assertTrue(facts["facts.constant_y"]["value"])
        self.assertEqual(facts["regression.slope"]["value"], 0)
        for metric in ("r", "r_squared"):
            self.assertEqual(facts[f"regression.{metric}"]["status"], "undefined")
            self.assertIsNone(facts[f"regression.{metric}"]["value"])
            self.assertIn("constant", facts[f"regression.{metric}"]["reason"])
        facts = build(pd.DataFrame({"x": [1, 2], "y": [7, 9]}))["evidence"]
        self.assertEqual(facts["regression.r"]["status"], "unavailable")
        self.assertIsNone(facts["regression.r"]["value"])

    def test_variation_below_regression_precision_keeps_exact_observed_range(self):
        y_min = 2 ** 54
        facts = build(pd.DataFrame({"x": [1, 2, 3], "y": [y_min, y_min + 1, y_min + 2]}))["evidence"]
        self.assertEqual(facts["ranges.y"]["value"], [y_min, y_min + 2])
        self.assertFalse(facts["facts.constant_y"]["value"])
        self.assertEqual(facts["regression.r_squared"]["status"], "undefined")
        self.assertEqual(facts["regression.r_squared"]["reason"], "Y has no variation at regression precision")

    def test_group_cap_covers_the_sorted_range(self):
        data = pd.DataFrame({"x": list(reversed(range(100))) + [49], "y": range(101)})
        payload = build(data)
        groups = [entry["value"]["x"] for key, entry in payload["evidence"].items()
                  if key.startswith("groups.")]
        self.assertEqual(payload["group_summary"], {"total_groups": 100, "groups_omitted": True})
        self.assertEqual(payload["evidence"]["counts.single_trial_groups"]["value"], 99)
        self.assertEqual(len(groups), 30)
        self.assertEqual((groups[0], groups[-1]), (0, 99))
        self.assertTrue(all(3 <= b - a <= 4 for a, b in zip(groups, groups[1:])))

    def test_fingerprint_covers_pairs_even_if_summary_is_unchanged(self):
        pairs = pd.DataFrame({"x": [1, 2, 3], "y": [7, 7, 7]})
        metadata = {"question": "What happened?", "model": "test", "uploaded": 4}
        original = fingerprint(pairs, "x", "y", metadata)
        self.assertEqual(len(original), sha256().digest_size * 2)
        self.assertEqual(original, fingerprint(pairs.copy(), "x", "y", metadata))
        self.assertNotEqual(original, fingerprint(pairs.iloc[::-1], "x", "y", metadata))
        self.assertNotEqual(original, fingerprint(pairs, "x", "y", {**metadata, "uploaded": 5}))
        self.assertNotEqual(original, fingerprint(pairs, "y", "x", metadata))
