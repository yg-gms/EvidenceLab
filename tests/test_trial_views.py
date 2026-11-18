import json
from io import BytesIO
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

from trial_views import slope_changes, trial_fit


APP = Path(__file__).resolve().parents[1] / "analysis.py"


class TrialViewTests(unittest.TestCase):
    def test_point_sizes_match_direct_refits(self):
        for xs, ys in [
            ([1, 2, 3, 4, 8], [4, 3, 2, 1, 12]),
            ([2, 2, 3], [2, 3, 8]),
            ([2, 3], [6, 7]),
            ([1, 2, 3], [2, 2, 2]),
        ]:
            rows = pd.DataFrame({"x": xs, "y": ys})
            full = trial_fit(rows)
            expected = []
            for idx in rows.index:
                fit = trial_fit(rows.drop(idx))
                expected.append(abs(fit.slope - full.slope) if fit else np.nan)
            np.testing.assert_allclose(slope_changes(rows, full), expected, atol=1e-12)

    @patch("interpretation.request_interpretation")
    def test_demo_reversal_and_fixed_axes(self, provider):
        app = AppTest.from_file(str(APP)).run()
        app.toggle[0].set_value(True).run()
        app.radio[0].set_value("Experiment replay").run()
        axes = []
        for count, slope in [(1, None), (4, "-1"), (5, "1.2603")]:
            app.slider[0].set_value(count).run()
            self.assertFalse(app.exception)
            layers = json.loads(app.get("vega_lite_chart")[0].proto.spec)["layer"]
            axes.append([layers[-1]["encoding"][d]["scale"]["domain"] for d in ("x", "y")])
            self.assertEqual(len(layers), 2 if slope else 1)
            if slope:
                self.assertIn(f"Fitted slope: {slope}", [c.value for c in app.caption])
        self.assertEqual(axes, [[[1, 8], [1, 12]]] * 3)
        app.radio[0].set_value("Trial influence").run()
        app.selectbox[2].select(5).run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Trend reversal" in i.value for i in app.info))
        layers = json.loads(app.get("vega_lite_chart")[0].proto.spec)["layer"]
        self.assertIn("strokeDash", layers[1]["mark"])
        provider.assert_not_called()

    @patch("streamlit.file_uploader", side_effect=lambda *a, **k: BytesIO(b"x,y\n2,1\n4,\n2,3\n1,7"))
    def test_upload_row_order_and_group_members(self, uploader):
        app = AppTest.from_file(str(APP)).run()
        app.checkbox[0].check().run()
        app.selectbox[2].select(2).run()
        self.assertEqual(app.dataframe[-1].value.to_dict("list"),
                         {"Trial (CSV row)": [1, 3], "Measurement": [1, 3]})
        app.radio[0].set_value("Experiment replay").run()
        app.slider[0].set_value(2).run()
        self.assertEqual(len(json.loads(app.get("vega_lite_chart")[0].proto.spec)["layer"]), 1)
        self.assertIn("Trial 3 · 2 of 3 shown", [m.value for m in app.markdown])
        app.slider[0].set_value(3).run()
        self.assertIn("Fitted slope: -5", [c.value for c in app.caption])
        app.radio[0].set_value("Trial influence").run()
        app.selectbox[2].select(4).run()
        self.assertTrue(any("do not define" in i.value for i in app.info))
