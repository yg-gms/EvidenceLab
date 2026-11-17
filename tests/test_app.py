from io import BytesIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import pyarrow as pa
from streamlit.testing.v1 import AppTest


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


if __name__ == '__main__':
    unittest.main()
