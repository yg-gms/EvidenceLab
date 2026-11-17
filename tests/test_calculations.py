import unittest

import numpy as np
import pandas as pd

from calculations import linear_regression, prepare_relationship_data, summarize_data


class CalculationTests(unittest.TestCase):
    def test_exact_positive_and_negative_lines(self):
        for y, slope, intercept, r in [
            ([3, 5, 7], 2, 1, 1),
            ([7, 5, 3], -2, 9, -1),
        ]:
            with self.subTest(y=y):
                data = pd.DataFrame({'x': [1, 2, 3], 'y': y})
                result = linear_regression(data, 'x', 'y')
                self.assertAlmostEqual(result.slope, slope)
                self.assertAlmostEqual(result.intercept, intercept)
                self.assertAlmostEqual(result.r_squared, 1)
                self.assertAlmostEqual(result.r, r)
                np.testing.assert_allclose(result.fitted_values, y)

    def test_noisy_line_has_known_r_squared(self):
        # Slope = 1/2, intercept = 5/6, residual SS = 1/6, total SS = 2/3.
        data = pd.DataFrame({'x': [0, 1, 2], 'y': [1, 1, 2]})
        result = linear_regression(data, 'x', 'y')
        self.assertAlmostEqual(result.slope, 0.5)
        self.assertAlmostEqual(result.intercept, 5 / 6)
        self.assertAlmostEqual(result.r_squared, 0.75)
        self.assertAlmostEqual(result.r, np.sqrt(0.75))
        np.testing.assert_allclose(result.fitted_values, [5 / 6, 4 / 3, 11 / 6])

    def test_zero_correlation(self):
        result = linear_regression(
            pd.DataFrame({'x': [-1, 0, 1], 'y': [1, 0, 1]}), 'x', 'y'
        )
        self.assertAlmostEqual(result.slope, 0)
        self.assertAlmostEqual(result.intercept, 2 / 3)
        self.assertAlmostEqual(result.r_squared, 0)
        self.assertAlmostEqual(result.r, 0)

    def test_cleaning_excludes_pairs_with_missing_or_nonfinite_values(self):
        data = pd.DataFrame({
            'x': [1, 2, None, 4, np.inf, 6, 7],
            'y': [3, 5, 7, np.nan, 11, -np.inf, 15],
        })
        original = data.copy(deep=True)
        clean = prepare_relationship_data(data, 'x', 'y')
        self.assertEqual(clean.index.tolist(), [0, 1, 6])
        pd.testing.assert_frame_equal(data, original)
        result = linear_regression(data, 'x', 'y')
        self.assertAlmostEqual(result.slope, 2)
        self.assertAlmostEqual(result.intercept, 1)

    def test_insufficient_data_after_cleaning(self):
        for data in [
            pd.DataFrame({'x': [], 'y': []}),
            pd.DataFrame({'x': [1], 'y': [2]}),
            pd.DataFrame({'x': [1, np.inf], 'y': [2, 3]}),
        ]:
            with self.subTest(data=data):
                with self.assertRaisesRegex(ValueError, 'two'):
                    linear_regression(data, 'x', 'y')

    def test_constant_x_cannot_define_a_slope(self):
        with self.assertRaisesRegex(ValueError, 'X.*constant'):
            linear_regression(pd.DataFrame({'x': [2, 2, 2], 'y': [1, 2, 3]}), 'x', 'y')

    def test_constant_y_has_a_horizontal_fit_but_undefined_r_and_r_squared(self):
        for value in [7, 0.1]:
            with self.subTest(value=value):
                result = linear_regression(
                    pd.DataFrame({'x': [1, 2, 3], 'y': [value] * 3}), 'x', 'y'
                )
                self.assertEqual(result.slope, 0)
                self.assertEqual(result.intercept, value)
                self.assertIsNone(result.r_squared)
                self.assertIsNone(result.r)
                np.testing.assert_allclose(result.fitted_values, [value] * 3)

    def test_two_points_allow_a_fit_but_keep_three_point_correlation_rule(self):
        result = linear_regression(pd.DataFrame({'x': [1, 2], 'y': [3, 5]}), 'x', 'y')
        self.assertAlmostEqual(result.slope, 2)
        self.assertAlmostEqual(result.r_squared, 1)
        self.assertIsNone(result.r)

    def test_grouped_sample_sd_counts_and_single_trial(self):
        data = pd.DataFrame({'x': [2, 1, 1, 1, 2, 3, 3], 'y': [10, 1, 2, 3, 14, 9, np.inf]})
        summary = summarize_data(data, 'x', 'y')
        self.assertEqual(summary.index.tolist(), [1, 2, 3])
        np.testing.assert_allclose(summary['mean'], [2, 12, 9])
        np.testing.assert_allclose(summary['count'], [3, 2, 1])
        self.assertAlmostEqual(summary.loc[1, 'std'], 1)
        self.assertAlmostEqual(summary.loc[2, 'std'], np.sqrt(8))
        self.assertTrue(pd.isna(summary.loc[3, 'std']))

    def test_fit_uses_all_trials_rather_than_equal_weighted_group_means(self):
        data = pd.DataFrame({'x': [0, 0, 0, 1, 2], 'y': [0, 0, 0, 2, 2]})
        result = linear_regression(data, 'x', 'y')
        self.assertAlmostEqual(result.slope, 1.125)
        self.assertAlmostEqual(result.intercept, 0.125)

    def test_invalid_column_selection(self):
        data = pd.DataFrame({'x': [1, 2], 'y': [2, 3], 'text': ['a', 'b']})
        for x, y in [('missing', 'y'), ('x', 'x'), ('x', 'text')]:
            with self.subTest(x=x, y=y):
                with self.assertRaises(ValueError):
                    prepare_relationship_data(data, x, y)

    def test_extreme_values_fail_clearly_instead_of_returning_nonfinite_results(self):
        data = pd.DataFrame({'x': [1e308, -1e308, 0], 'y': [1, 2, 3]})
        with self.assertRaisesRegex(ValueError, 'rescale'):
            linear_regression(data, 'x', 'y')

    def test_grouped_overflow_fails_clearly(self):
        data = pd.DataFrame({'x': [1, 1], 'y': [1e308, 1e308]})
        with self.assertRaisesRegex(ValueError, 'rescale'):
            summarize_data(data, 'x', 'y')


if __name__ == '__main__':
    unittest.main()
