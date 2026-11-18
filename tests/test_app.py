from io import BytesIO
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import pyarrow as pa
from streamlit.testing.v1 import AppTest

from interpretation import DEFAULT_MODEL, Interpretation, InterpretationError


APP = Path(__file__).resolve().parents[1] / 'analysis.py'


def run_app(contents):
    uploaded = None if contents is None else BytesIO(contents)
    with patch('streamlit.file_uploader', return_value=uploaded):
        app = AppTest.from_file(str(APP)).run(timeout=20)
    return app


class AppTests(unittest.TestCase):
    def test_no_upload_keeps_start_screen(self):
        app = run_app(None)
        self.assertFalse(app.exception)
        self.assertTrue(app.info)

    def test_bad_files_show_messages_without_tracebacks(self):
        for contents in [b'', b'\xff\xfe\x00', b'x,y\n1,2\n3,4,5', b'x,y\n1,2,3', b'x,y\n']:
            with self.subTest(contents=contents):
                app = run_app(contents)
                self.assertFalse(app.exception)
                self.assertTrue(app.error or app.warning)

    def test_regression_and_grouped_view_keep_all_trials(self):
        contents = b'x,y\n0,0\n0,0\n0,0\n1,2\n2,2\n'
        uploaded = BytesIO(contents)
        with patch('streamlit.file_uploader', return_value=uploaded):
            app = AppTest.from_file(str(APP)).run(timeout=20)
            self.assertFalse(app.exception)
            self.assertEqual([m.label for m in app.metric], ['Slope', 'Intercept', 'R\u00b2'])
            self.assertEqual(app.metric[0].value, '1.125')
            self.assertEqual(len(app.dataframe), 1)
            uploaded.seek(0)
            app.checkbox[0].check().run(timeout=20)
            self.assertFalse(app.exception)
            self.assertEqual(len(app.dataframe), 2)
            self.assertEqual(app.metric[0].value, '1.125')
            self.assertEqual(app.dataframe[1].value['Trials'].tolist(), [3, 1, 1])

    def test_invalid_relationships_show_messages_without_tracebacks(self):
        for contents in [
            b'x,y\n1,2',
            b'x,y\n1,2\n1,3\n1,4',
            b'x,y\n1,7\n2,7\n3,7',
            b'x,y\ninf,2\n3,-inf',
            b'x,label\n1,a\n2,b',
            b'x,y\n1e308,1\n-1e308,2\n0,3',
        ]:
            with self.subTest(contents=contents):
                app = run_app(contents)
                self.assertFalse(app.exception)
                self.assertTrue(app.info or app.warning)

    def test_nonfinite_rows_are_excluded_and_counted(self):
        app = run_app(b'x,y\n1,3\n2,5\n3,7\ninf,9\n5,\n')
        self.assertFalse(app.exception)
        self.assertTrue(any('Excluded rows due to missing or nonfinite data: 2' in item.value for item in app.markdown))
        self.assertEqual(app.metric[0].value, '2')

    def test_chart_contains_sorted_fit_and_sd_only_for_repeated_trials(self):
        uploaded = BytesIO(b'mass.g,extension:cm\n3,7\n1,2\n1,4\n2,5')
        with patch('streamlit.file_uploader', return_value=uploaded):
            app = AppTest.from_file(str(APP)).run(timeout=20)
            uploaded.seek(0)
            app.checkbox[0].check().run(timeout=20)
        self.assertFalse(app.exception)
        chart = app.get('vega_lite_chart')[0].proto
        spec = json.loads(chart.spec)
        datasets = {
            dataset.name: pa.ipc.open_stream(dataset.data.data).read_all().to_pandas()
            for dataset in chart.datasets
        }
        points, line, bars, means = spec['layer']
        self.assertEqual(datasets[points['data']['name']]['x'].tolist(), [3, 1, 1, 2])
        self.assertEqual(datasets[line['data']['name']]['x'].tolist(), [1, 1, 2, 3])
        self.assertEqual(datasets[bars['data']['name']]['count'].tolist(), [2])
        self.assertEqual(bars['encoding']['yError']['field'], 'std')
        self.assertEqual(datasets[means['data']['name']]['count'].tolist(), [2, 1, 1])


class InterpretationAppTests(unittest.TestCase):
    def setUp(self):
        self.contents = b"x,y,z\n1,3,4\n2,5,9\n3,7,16\n"
        self.answer = Interpretation(
            conclusion="Y increased as X increased over the observed range.",
            hypothesis_assessment="not_provided",
            evidence=[
                {"explanation": "The fitted line rises.", "evidence_ids": ["regression.slope"]},
                {"explanation": "The fit uses three pairs.", "evidence_ids": ["counts.valid"]},
            ],
            limitations=["Only three pairs were measured.", "Other variables may affect Y."],
            improvements=["Measure at more X values."],
            missing_context=["How Y was measured."],
            context_advice={
                "research_question": "Specify the observed range of X.",
                "hypothesis": "Predict how Y will change when X increases.",
                "method_notes": "Record how you measured Y.",
            },
        )
        provider = patch("interpretation.request_interpretation", return_value=self.answer)
        self.provider = provider.start()
        self.addCleanup(provider.stop)
        uploader = patch("streamlit.file_uploader", side_effect=self.upload)
        uploader.start()
        self.addCleanup(uploader.stop)
        credentials = patch.dict(os.environ, {"OPENAI_API_KEY": "sk-or-v1-test-key", "OPENAI_MODEL": "example/test:free"})
        credentials.start()
        self.addCleanup(credentials.stop)

    def upload(self, *args, **kwargs):
        return None if self.contents is None else BytesIO(self.contents)

    def assert_analysis(self, app):
        self.assertFalse(app.exception)
        self.assertTrue(app.metric)
        self.assertTrue(app.get("vega_lite_chart"))

    def enter_question(self, app):
        app.text_input[0].set_value("How does X relate to Y?").run(timeout=20)

    def submit(self, app):
        app.button[0].click().run(timeout=20)
        self.assertFalse(app.exception)

    def assert_answer(self, app, *, visible):
        self.assertEqual(self.answer.conclusion in [item.value for item in app.text], visible)

    def test_only_explicit_submission_requests_and_chart_reruns_reuse(self):
        app = AppTest.from_file(str(APP)).run(timeout=20)
        self.assertFalse(app.button[0].disabled)
        self.enter_question(app)
        app.run(timeout=20)
        app.checkbox[0].check().run(timeout=20)
        self.provider.assert_not_called()
        self.submit(app)
        self.assert_answer(app, visible=True)
        self.assertIn("Slope: 2.0", [item.value for item in app.text])
        self.assertIn("Valid pairs: 3", [item.value for item in app.text])
        app.checkbox[0].uncheck().run(timeout=20)
        app.run(timeout=20)
        self.assert_answer(app, visible=True)
        self.submit(app)
        self.assertTrue(any("Showing the saved" in item.value for item in app.info))
        self.provider.assert_called_once()

    def test_changed_inputs_clear_response_before_rerender(self):
        def change_data(app):
            # Same rows, ranges, group means, and regression. The cleaned data still changed.
            self.contents = b"x,y,z\n3,7,16\n2,5,9\n1,3,4\n"
            app.run(timeout=20)

        def change_counts(app):
            self.contents += b"4,,20\n"
            app.run(timeout=20)

        def remove_upload(app):
            old_contents = self.contents
            self.contents = None
            app.run(timeout=20)
            self.contents = old_contents
            app.run(timeout=20)

        def change_model(app):
            with patch.dict(os.environ, {"OPENAI_MODEL": "example/different:free"}):
                app.run(timeout=20)

        for edit in (
            lambda app: app.text_input[0].set_value("What does Y do as X changes?").run(timeout=20),
            lambda app: app.text_input[1].set_value("Y increases.").run(timeout=20),
            lambda app: app.text_area[0].set_value("Calibrated the sensor.").run(timeout=20),
            lambda app: app.selectbox[1].select("z").run(timeout=20),
            change_data, change_counts, change_model, remove_upload,
        ):
            with self.subTest(edit=edit):
                self.contents = b"x,y,z\n1,3,4\n2,5,9\n3,7,16\n"
                self.provider.reset_mock()
                app = AppTest.from_file(str(APP)).run(timeout=20)
                self.enter_question(app)
                self.submit(app)
                self.assert_answer(app, visible=True)
                edit(app)
                self.assertFalse(app.exception)
                self.assert_answer(app, visible=False)
                self.provider.assert_called_once()

    def test_missing_key_or_provider_error_keeps_analysis_usable(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}), patch("streamlit.secrets", {}):
            app = AppTest.from_file(str(APP)).run(timeout=20)
            self.enter_question(app)
            self.assertTrue(app.button[0].disabled)
            self.assertTrue(any("OPENAI_API_KEY" in item.value for item in app.info))
            self.assert_analysis(app)
        self.provider.assert_not_called()

        self.provider.side_effect = InterpretationError("OpenRouter timed out. Try again.")
        app = AppTest.from_file(str(APP)).run(timeout=20)
        self.enter_question(app)
        self.submit(app)
        self.assertIn("OpenRouter timed out", app.error[0].value)
        self.assert_analysis(app)
        app.run(timeout=20)
        self.provider.assert_called_once()
        self.provider.side_effect = None
        self.submit(app)
        self.assert_answer(app, visible=True)
        self.assertEqual(self.provider.call_count, 2)

    def test_uses_streamlit_secrets_as_fallback(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "OPENAI_MODEL": ""}), patch(
            "streamlit.secrets", {"openai": {"OPENAI_API_KEY": "sk-or-v1-secrets-key", "OPENAI_MODEL": "example/secrets:free"}},
        ):
            app = AppTest.from_file(str(APP)).run(timeout=20)
            self.enter_question(app)
            self.submit(app)
        self.assertEqual(self.provider.call_args.args[1:], ("sk-or-v1-secrets-key", "example/secrets:free"))
        with patch("streamlit.secrets", {"openai": {"OPENAI_API_KEY": "sk-or-v1-secrets-key"}}):
            app = AppTest.from_file(str(APP)).run(timeout=20)
            self.enter_question(app)
            self.submit(app)
        self.assertEqual(self.provider.call_args.args[1:], ("sk-or-v1-test-key", "example/test:free"))

    def test_suggestions_when_context_is_blank(self):
        app = AppTest.from_file(str(APP)).run(timeout=20)
        app.text_input[0].set_value("   ").run(timeout=20)
        self.assertFalse(app.button[0].disabled)
        self.provider.assert_not_called()
        self.submit(app)
        self.assertEqual(self.provider.call_args.args[0]["student_context"], {
            "question": None, "hypothesis": None, "method_notes": None,
        })
        headings = [item.value for item in app.markdown]
        self.assertIn("**Suggested research question**", headings)
        self.assertIn("**Suggested hypothesis**", headings)
        self.assertIn("**Method notes template**", headings)
        cards = [block for block in app.get("flex_container") if block.proto.flex_container.border]
        self.assertEqual(len(cards), 3)
        self.assert_answer(app, visible=True)

    def test_enhancements_when_context_is_filled_and_notes_are_bounded(self):
        app = AppTest.from_file(str(APP)).run(timeout=20)
        self.enter_question(app)
        app.text_input[1].set_value("Y increases with X.").run(timeout=20)
        app.text_area[0].set_value("x" * 1501).run(timeout=20)
        self.provider.assert_not_called()
        self.submit(app)
        self.assertEqual(len(self.provider.call_args.args[0]["student_context"]["method_notes"]), 1500)
        headings = [item.value for item in app.markdown]
        self.assertIn("**Improve your research question**", headings)
        self.assertIn("**Improve your hypothesis**", headings)
        self.assertIn("**Improve your method notes**", headings)
        self.assertIn(self.answer.context_advice.method_notes, [item.value for item in app.text])

    def test_nonfree_model_disables_only_explanations(self):
        with patch.dict(os.environ, {"OPENAI_MODEL": "openai/gpt-oss-120b"}):
            app = AppTest.from_file(str(APP)).run(timeout=20)
            self.enter_question(app)
            self.assert_analysis(app)
            self.assertTrue(app.button[0].disabled)
            self.assertTrue(any("free model" in item.value for item in app.info))
        self.provider.assert_not_called()

    def test_uses_default_model_without_override(self):
        with patch.dict(os.environ, {"OPENAI_MODEL": ""}), patch("streamlit.secrets", {}):
            app = AppTest.from_file(str(APP)).run(timeout=20)
            self.enter_question(app)
            self.submit(app)
        self.assertEqual(DEFAULT_MODEL, "openai/gpt-oss-120b:free")
        self.assertEqual(self.provider.call_args.args[2], DEFAULT_MODEL)

    def test_gates_invalid_regression_and_allows_constant_y(self):
        for contents in (b"x,y\n1,2\n2,3", b"x,y\n1,2\n1,3\n1,4"):
            self.contents = contents
            app = AppTest.from_file(str(APP)).run(timeout=20)
            self.enter_question(app)
            self.assertTrue(app.button[0].disabled)
        self.provider.assert_not_called()

        self.contents = b"x,y\n1,7\n2,7\n3,7"
        app = AppTest.from_file(str(APP)).run(timeout=20)
        self.enter_question(app)
        self.submit(app)
        payload = self.provider.call_args.args[0]
        self.assertEqual(payload["evidence"]["regression.r_squared"]["status"], "undefined")
        self.assertEqual(app.metric[2].value, "Undefined")


if __name__ == '__main__':
    unittest.main()
