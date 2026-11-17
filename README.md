# EvidenceLab

A Streamlit app for students to explore relationships in experimental data.

## Run

Use Python 3.11 or later, then:

```sh
python -m pip install -r requirements.txt
python -m streamlit run analysis.py
```

Upload a UTF-8, comma-separated CSV with a header and at least two numeric
columns. Try `sample.csv`, then choose the X and Y variables.

## Relationship analysis checkpoint

- CSV preview, variable selection, missing-value warnings and row counts.
- Interactive scatter plot with a fitted linear trendline, equation, slope,
  intercept, R² and Pearson correlation.
- Optional grouped means, sample standard deviations and trial counts, with
  mean ± one sample SD error bars. A group is one exact X value.

`calculations.py` contains the numerical work without Streamlit or plotting
imports. `analysis.py` handles uploads, messages, controls and the chart.
Regression uses all individual valid trials, even when grouped means are shown.

Rows with a missing or infinite X or Y are excluded and counted. Invalid or
empty CSVs and nonnumeric columns get an explanatory message. Regression needs
at least two finite pairs and a varying X. The existing three-pair minimum for
Pearson correlation is retained. Constant Y gives a horizontal line with
undefined r and R². A group with one trial has no defined sample SD and no
error bar. Values outside safe numerical precision prompt rescaling.

SD describes trial spread; these bars are not confidence intervals. A fit or
correlation does not establish cause and effect.

## Verify

From this directory, using the same Python environment:

```sh
python -m unittest discover -s tests -v
```

The tests check known results, invalid inputs and Streamlit app behavior:

| X | Y | Expected slope | Intercept | R² |
|---|---|---:|---:|---:|
| 1, 2, 3 | 3, 5, 7 | 2 | 1 | 1 |
| 1, 2, 3 | 7, 5, 3 | -2 | 9 | 1 |
| 0, 1, 2 | 1, 1, 2 | 0.5 | 5/6 | 0.75 |

Grouped trials `[1, 2, 3]` must give mean 2, sample SD 1 and count 3.
App tests supply in-memory CSV uploads, exercise controls and inspect the
chart's trial, fit and error-bar data.

AI integration, comparative analysis and time-series analysis remain future
work. This checkpoint stops at the relationship workflow for review.
