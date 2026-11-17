import altair as alt
import pandas as pd
import streamlit as st

from calculations import (
    NumericalError,
    linear_regression,
    prepare_relationship_data,
    summarize_data,
)


st.title("EvidenceLab")
st.write("Upload experimental data to explore your results.")

uploaded_file = st.file_uploader("Upload CSV file", type="csv")
if uploaded_file is None:
    st.info("Upload a CSV file to begin")
    st.stop()

try:
    df = pd.read_csv(uploaded_file)
    # Extra fields can otherwise be silently interpreted as an index by pandas.
    if not isinstance(df.index, pd.RangeIndex):
        raise ValueError("Some rows contain more fields than the header.")
except (ValueError, OSError):
    st.error(
        "Could not read this CSV. Use a UTF-8, comma-separated file "
        "with a header and consistent columns."
    )
    st.stop()

if df.empty:
    st.warning("The CSV has a header but no measurements. Add data rows and upload it again.")
    st.stop()

st.dataframe(df)
numeric_columns = df.select_dtypes(include="number").columns.tolist()
if len(numeric_columns) < 2:
    st.warning(
        "Upload data with at least two numeric columns. "
        "Check for text or units inside measurement cells."
    )
    st.stop()

x_column = st.selectbox("X variable", numeric_columns)
y_column = st.selectbox("Y variable", numeric_columns, index=1)

try:
    analysis_data = prepare_relationship_data(df, x_column, y_column)
except ValueError as error:
    st.warning(str(error))
    st.stop()

st.write(f"Measurements used: {len(analysis_data)}")
st.write(f"Excluded rows due to missing or nonfinite data: {len(df) - len(analysis_data)}")
for column, count in df.isna().sum().items():
    if count > 0:
        st.write(f"Warning: {column} has {count} missing value(s).")

if analysis_data.empty:
    st.warning("No rows contain finite values for both selected variables.")
    st.stop()

result = None
try:
    result = linear_regression(analysis_data, x_column, y_column)
except NumericalError as error:
    st.warning(str(error))
    st.stop()
except ValueError as error:
    st.info(str(error))

if result is not None:
    slope_metric, intercept_metric, r_squared_metric = st.columns(3)
    slope_metric.metric("Slope", f"{result.slope:.6g}")
    intercept_metric.metric("Intercept", f"{result.intercept:.6g}")
    r_squared_metric.metric(
        "R²", "Undefined" if result.r_squared is None else f"{result.r_squared:.6g}"
    )
    st.write(f"Fitted equation: Y = ({result.slope:.6g}) × X + ({result.intercept:.6g})")
    st.caption(
        f"X: {x_column}; Y: {y_column}. "
        "Ordinary least squares uses all individual finite trials."
    )

    if result.r_squared is None:
        st.info("Y is constant: the fitted line is horizontal; Pearson r and R² are undefined.")
    elif result.r is None:
        st.info(
            "At least three complete measurements are required here for correlation. "
            "A two-point fit alone is weak evidence."
        )
    else:
        st.write(f"Pearson correlation (r): {result.r:.3f}")
    st.caption("Correlation and R² describe linear fit; they do not establish cause and effect.")

show_groups = st.checkbox("Show grouped means with standard-deviation error bars", value=False)
summary = None
if show_groups:
    try:
        summary = summarize_data(analysis_data, x_column, y_column)
    except NumericalError as error:
        st.warning(str(error))
    if summary is not None:
        st.dataframe(
            summary.rename(columns={"mean": "Mean", "std": "Sample SD", "count": "Trials"})
        )
        st.caption(
            "Trials are grouped by exact X value. Error bars show mean ± one sample SD, "
            "not confidence intervals. SD is undefined for one trial; "
            "its mean is shown without an error bar."
        )

# Fixed plotting field names also support uploaded headers containing dots or colons.
plot_data = pd.DataFrame({"x": analysis_data[x_column], "y": analysis_data[y_column]})
x_axis = alt.X("x:Q", title=x_column, scale=alt.Scale(zero=False))
y_axis = alt.Y("y:Q", title=y_column, scale=alt.Scale(zero=False))
points = alt.Chart(plot_data).mark_circle(color="#2878b5", opacity=0.7).encode(
    x=x_axis,
    y=y_axis,
    tooltip=[alt.Tooltip("x:Q", title=x_column), alt.Tooltip("y:Q", title=y_column)],
)
layers = [points]
if result is not None:
    # Sorting X keeps the fitted line from zigzagging through uploaded row order.
    trendline = pd.DataFrame({
        "x": analysis_data[x_column], "y": result.fitted_values,
    }).sort_values("x")
    layers.append(alt.Chart(trendline).mark_line(color="#e67e22").encode(x=x_axis, y=y_axis))
if summary is not None:
    groups = pd.DataFrame({
        "x": summary.index,
        "mean": summary["mean"],
        "std": summary["std"],
        "count": summary["count"],
    })
    group_y = alt.Y("mean:Q", title=y_column, scale=alt.Scale(zero=False))
    repeated = groups[groups["count"] > 1]
    if not repeated.empty:
        layers.append(
            alt.Chart(repeated).mark_errorbar(color="#238b45", ticks=True).encode(
                x=x_axis, y=group_y, yError="std:Q",
            )
        )
    layers.append(
        alt.Chart(groups).mark_point(
            color="#238b45", shape="diamond", filled=True, size=90,
        ).encode(
            x=x_axis,
            y=group_y,
            tooltip=[
                alt.Tooltip("x:Q", title=x_column),
                alt.Tooltip("mean:Q", title="Mean"),
                alt.Tooltip("std:Q", title="Sample SD"),
                alt.Tooltip("count:Q", title="Trials"),
            ],
        )
    )
st.altair_chart(alt.layer(*layers).interactive(), width="stretch")
st.caption(
    "Blue circles: individual trials. Orange line: linear fit. "
    "Green diamonds and bars (when enabled): grouped means ± sample SD."
)
