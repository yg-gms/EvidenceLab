"""Relationship calculations, independent of Streamlit and plotting."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


class NumericalError(ValueError):
    """Values need rescaling before they can be calculated safely."""


@dataclass(frozen=True)
class RegressionResult:
    slope: float
    intercept: float
    r_squared: float | None
    r: float | None
    fitted_values: np.ndarray


def prepare_relationship_data(data, x_column, y_column):
    """Keep finite numeric pairs without changing the uploaded data."""
    if x_column == y_column:
        raise ValueError("Choose two different columns.")
    for column in (x_column, y_column):
        if column not in data.columns:
            raise ValueError(f"Column '{column}' was not found in the dataset.")
        if not pd.api.types.is_numeric_dtype(data[column]):
            raise ValueError(f"Column '{column}' must contain numeric values.")

    pairs = data[[x_column, y_column]]
    return pairs.replace([np.inf, -np.inf], np.nan).dropna().copy()


def summarize_data(data, group_column, measurement_column):
    """Summarize trials at each exact X value; sample SD uses n - 1."""
    pairs = prepare_relationship_data(data, group_column, measurement_column)
    # Pandas leaves SD undefined (NaN) when a group has only one trial.
    with np.errstate(over="ignore", invalid="ignore"):
        summary = pairs.groupby(group_column)[measurement_column].agg(["mean", "std", "count"])
    repeated_sd = summary.loc[summary["count"] > 1, "std"]
    if not np.isfinite(summary["mean"]).all() or not np.isfinite(repeated_sd).all():
        raise NumericalError("Grouped values exceed numerical precision; rescale the selected variables and try again.")
    return summary


def linear_regression(data, x_column, y_column):
    """Fit ordinary least squares to individual finite trials, including an intercept."""
    pairs = prepare_relationship_data(data, x_column, y_column)
    if len(pairs) < 2:
        raise ValueError("At least two finite measurements are required for linear regression.")

    x = pairs[x_column].to_numpy(dtype=float)
    y = pairs[y_column].to_numpy(dtype=float)
    if np.all(x == x[0]):
        raise ValueError("X is constant; a regression slope and correlation are undefined.")

    try:
        with np.errstate(over="raise", invalid="raise", divide="raise", under="raise"):
            # Centering avoids the cancellation in sum(x*y) - sum(x)*sum(y)/n.
            x_mean, y_mean = x.mean(), y.mean()
            dx, dy = x - x_mean, y - y_mean
            if np.all(y == y[0]):
                y_mean, dy = y[0], np.zeros_like(y)
            ss_x, ss_y = np.dot(dx, dx), np.dot(dy, dy)
            cross_product = np.dot(dx, dy)
            # BLAS dot products can overflow without obeying NumPy's error setting.
            if not np.isfinite([ss_x, ss_y, cross_product]).all():
                raise FloatingPointError
            slope = cross_product / ss_x
            intercept = y_mean - slope * x_mean
            fitted = y_mean + slope * dx

            r_squared = None
            r = None
            if not np.all(y == y[0]):
                residual = y - fitted
                r_squared = float(np.clip(1 - np.dot(residual, residual) / ss_y, 0, 1))
                if len(pairs) >= 3:
                    r = float(np.clip(cross_product / np.sqrt(ss_x) / np.sqrt(ss_y), -1, 1))
    except FloatingPointError as error:
        raise NumericalError("Values exceed numerical precision; rescale the selected variables and try again.") from error

    return RegressionResult(float(slope), float(intercept), r_squared, r, fitted)
