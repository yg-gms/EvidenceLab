from collections.abc import Mapping
import os

import altair as alt
import pandas as pd
import streamlit as st

from calculations import (
    NumericalError,
    linear_regression,
    prepare_relationship_data,
    summarize_data,
)
from trial_views import show_trial_view
from evidence import SCHEMA_VERSION, build_evidence, fingerprint
from interpretation import (
    DEFAULT_MODEL,
    PROMPT_VERSION,
    InterpretationError,
    is_free_model,
    request_interpretation,
)


INTERPRETATION_STATE = "relationship_interpretation"


def openrouter_setting(name):
    value = os.getenv(name, "").strip()
    if value:
        return value
    try:
        nested = st.secrets.get("openai", {})
        value = nested.get(name, "") if isinstance(nested, Mapping) else ""
        value = value or st.secrets.get(name, "")
    except OSError:
        return ""
    return value.strip() if isinstance(value, str) else ""


def evidence_text(entry):
    label, value = entry["label"], entry["value"]
    if entry["status"] != "available":
        return f"{label}: {entry['status']} ({entry['reason']})"
    if isinstance(value, dict):
        sd = value["sample_sd"]
        if sd is None:
            sd = f"{entry['sample_sd_status']} ({entry['sample_sd_reason'].lower()})"
        return f"{label}: {value['count']} trial(s), mean {value['mean']}, sample SD {sd}"
    if isinstance(value, list):
        value = f"{value[0]} to {value[1]}"
    if isinstance(value, bool):
        value = "yes" if value else "no"
    return f"{label}: {value}"


def show_interpretation(pairs, x, y, uploaded_rows, result, saved):
    st.subheader("Explain your results")
    st.caption("Leave any field blank for a suggestion, or add a draft for feedback.")
    question = st.text_input(
        "Research question (optional)", max_chars=500, help="Ask how the selected variables relate.",
    )
    hypothesis = st.text_input("Hypothesis (optional)", max_chars=500)
    notes = st.text_area(
        "Method notes (optional)", max_chars=1500, help="Briefly describe how you collected the data.",
    )
    api_key = openrouter_setting("OPENAI_API_KEY")
    model = openrouter_setting("OPENAI_MODEL") or DEFAULT_MODEL

    has_openrouter_key = api_key.startswith("sk-or-v1-")
    free_model = is_free_model(model)
    if not has_openrouter_key:
        st.info("To enable AI interpretation, set OPENAI_API_KEY to an OpenRouter API key.")
    if not free_model:
        st.info("Set OPENAI_MODEL to an OpenRouter free model ending in :free.")
    if result is None or len(pairs) < 3:
        st.caption("An explanation requires a valid linear fit and at least three finite pairs.")
    st.caption(
        "Your question, any hypothesis and method notes, and the calculated summary "
        "for the selected variables will be sent to OpenRouter. Check the explanation against your experiment."
    )
    ready = bool(has_openrouter_key and free_model and result is not None and len(pairs) >= 3)
    submitted = st.button("Explain my results", disabled=not ready)
    if not ready or (not submitted and saved is None):
        return

    signature = fingerprint(pairs, x, y, {
        "uploaded": uploaded_rows,
        "excluded": uploaded_rows - len(pairs),
        "question": question,
        "hypothesis": hypothesis,
        "notes": notes,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
    })
    if saved is not None and saved[0] == signature:
        _, explanation, facts = saved
        if submitted:
            st.info("Showing the saved explanation for these inputs.")
    elif submitted:
        try:
            with st.spinner("Explaining your results…"):
                payload = build_evidence(
                    pairs, x, y, uploaded_rows, result,
                    question.strip(), hypothesis.strip(), notes.strip(),
                )
                explanation = request_interpretation(payload, api_key, model)
        except (NumericalError, InterpretationError) as error:
            st.error(str(error))
            return
        facts = {
            evidence_id: payload["evidence"][evidence_id]
            for statement in explanation.evidence
            for evidence_id in statement.evidence_ids
        }
    else:
        return
    st.session_state[INTERPRETATION_STATE] = (signature, explanation, facts)

    st.subheader("AI-generated advice")
    for draft, suggestion_title, feedback_title, advice in (
        (question, "Suggested research question", "Improve your research question",
         explanation.context_advice.research_question),
        (hypothesis, "Suggested hypothesis", "Improve your hypothesis",
         explanation.context_advice.hypothesis),
        (notes, "Method notes template", "Improve your method notes",
         explanation.context_advice.method_notes),
    ):
        with st.container(border=True):
            title = feedback_title if draft.strip() else suggestion_title
            st.markdown(f"**{title}**")
            st.text(advice)

    st.subheader("AI-generated interpretation")
    st.markdown("**Conclusion**")
    st.text(explanation.conclusion)
    st.text(f"Hypothesis assessment: {explanation.hypothesis_assessment.replace('_', ' ').capitalize()}")
    st.markdown("**Evidence**")
    for statement in explanation.evidence:
        st.text(statement.explanation)
        for evidence_id in statement.evidence_ids:
            st.text(evidence_text(facts[evidence_id]))
    for label, items in (
        ("Limitations", explanation.limitations),
        ("Improvements", explanation.improvements),
        ("Missing context", explanation.missing_context),
    ):
        if items:
            st.markdown(f"**{label}**")
            for item in items:
                st.text(f"• {item}")


# Clear the previous result even if this run stops before reaching the chart.
saved_interpretation = st.session_state.pop(INTERPRETATION_STATE, None)

st.title("EvidenceLab")
st.write("Upload experimental data to explore your results.")

uploaded_file = st.file_uploader("Upload CSV file", type="csv")
demo = st.toggle("Try the five-trial example", help="Synthetic measurements with a change in trend on trial 5.")
if uploaded_file is None and not demo:
    st.info("Upload a CSV file to begin")
    st.stop()

try:
    df = pd.DataFrame({"X": [1, 2, 3, 4, 8], "Y": [4, 3, 2, 1, 12]}) if demo else pd.read_csv(uploaded_file)
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

with st.expander("Preview data"):
    st.dataframe(df, hide_index=True)
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

view = st.radio("Chart view", ["Overview", "Trial influence", "Experiment replay"], horizontal=True)
if view != "Overview":
    show_trial_view(view, analysis_data, x_column, y_column, result)
else:
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

    if summary is not None and (summary["count"] > 1).any():
        with st.expander("Unpack the average"):
            group = st.selectbox("Choose an X value", summary.index, index=None)
            if group is not None:
                members = analysis_data.loc[analysis_data[x_column] == group, y_column]
                st.write(f"Mean {summary.loc[group, 'mean']:.5g} from {len(members)} trial(s)")
                st.dataframe(pd.DataFrame({"Trial (CSV row)": members.index + 1,
                                           "Measurement": members.to_numpy()}), hide_index=True)

show_interpretation(analysis_data, x_column, y_column, len(df), result, saved_interpretation)
