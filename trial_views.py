"""Interactive views of the individual finite trials."""
from hashlib import blake2b
from time import monotonic

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from calculations import linear_regression


def trial_fit(rows):
    try:
        return linear_regression(rows, "x", "y")
    except ValueError:
        return None


def slope_changes(rows, result):
    """Remove each observation's contribution to centered sums in linear time."""
    if result is None or len(rows) < 3:
        return np.full(len(rows), np.nan)
    x, y = (rows[col].to_numpy(dtype=float) for col in ("x", "y"))
    dx, dy = x - x.mean(), y - y.mean()
    ss = dx @ dx
    factor = len(x) / (len(x) - 1)
    with np.errstate(all="ignore"):
        remaining = ss - dx * (factor * dx)
        changes = np.abs(dx * (factor * (dy - result.slope * dx)) / remaining)
    # Directly refit near-singular deletions where subtraction loses precision.
    for i in np.flatnonzero((remaining <= ss * 1e-8) | ~np.isfinite(changes)):
        fit = trial_fit(rows.drop(index=rows.index[i]))
        changes[i] = abs(result.slope - fit.slope) if fit else np.nan
    return changes


def fit_line(rows, fit, dashed=False):
    ends = [int(rows.x.argmin()), int(rows.x.argmax())]
    data = pd.DataFrame({"x": rows.x.iloc[ends], "y": fit.fitted_values[ends]})
    mark = {"color": "#8e459b", "strokeDash": [7, 4]} if dashed else {"color": "#bc591a"}
    return alt.Chart(data).mark_line(clip=True, strokeWidth=3, **mark)


def show_influence(rows, result, axes, key):
    rows["change"] = slope_changes(rows, result)
    rows["size_change"] = rows.change.fillna(0)
    st.caption("Larger circles mark trials whose removal changes the slope more. Click a circle or choose a trial.")
    pick_key = key + "_pick"
    chart_key = key + "_chart"

    def pick_point():
        selected = st.session_state[chart_key].selection.get("pick", [])
        if selected:
            st.session_state[pick_key] = selected[0]["trial"]

    trial = st.selectbox("Compare without trial", rows.trial.tolist(), index=None, key=pick_key)
    layers = []
    if result:
        layers.append(fit_line(rows, result).encode(**axes))
    remaining = rows[rows.trial != trial]
    without = trial_fit(remaining) if trial is not None else None
    if without:
        layers.append(fit_line(remaining, without, dashed=True).encode(**axes))
    dots = alt.Chart(rows).mark_circle(opacity=0.85, cursor="pointer").encode(
        **axes,
        size=alt.Size("size_change:Q", scale=alt.Scale(domain=[0, rows.size_change.max() or 1], range=[55, 680]), legend=None),
        color=alt.condition(alt.datum.trial == (trial or 0), alt.value("#8e459b"), alt.value("#2878b5")),
        tooltip=["trial:O", "x:Q", "y:Q", alt.Tooltip("change:Q", title="Absolute slope change", format=".5g")],
    ).add_params(alt.selection_point(name="pick", fields=["trial"], toggle=False))
    st.altair_chart(alt.layer(*layers, dots), width="stretch", key=chart_key, on_select=pick_point)
    if trial is None:
        st.caption("The solid line fits all trials." if result else "The available trials do not define a slope.")
    elif without and result:
        delta = without.slope - result.slope
        st.write(f"All trials (solid): **{result.slope:.5g}** · Without trial {trial} (dashed): **{without.slope:.5g}** · Slope change on removal: **{delta:+.5g}**")
        if (without.slope < 0 < result.slope) or (result.slope < 0 < without.slope):
            before, after = ("downward", "upward") if result.slope > 0 else ("upward", "downward")
            st.info(f"Trend reversal: adding trial {trial} turns a {before} trend into an {after} trend.")
    else:
        st.write(f"All trials: {result.slope:.5g}" if result else "All trials: slope unavailable")
        st.info(f"Without trial {trial}, the remaining measurements do not define a usable slope.")


def show_replay(rows, axes, key):
    frame, playing, tick = (key + suffix for suffix in ("_frame", "_playing", "_tick"))
    state = st.session_state
    if frame not in state:
        state[frame] = 1
        state[playing] = False
    total = len(rows)
    st.caption("Replay follows CSV data-row order, starting at 1 and skipping excluded rows.")

    def toggle():
        state[playing] = not state[playing]
        if state[playing] and state[frame] == total:
            state[frame] = 1
        state[tick] = monotonic()

    st.button("Pause" if state[playing] else "Play", key=key + "_toggle", on_click=toggle, disabled=total == 1)

    @st.fragment(run_every=0.8 if state[playing] else None)
    def render():
        if state[playing] and monotonic() - state[tick] >= 0.65:
            state[frame] = min(total, state[frame] + 1)
            state[tick] = monotonic()
            if state[frame] == total:
                state[playing] = False
                st.rerun()
        count = st.slider("Trials shown", 0, total, key=frame)
        visible = rows.iloc[:count]
        fit = trial_fit(visible)
        dots = alt.Chart(visible).mark_circle(size=95, color="#2878b5").encode(
            **axes, tooltip=["trial:O", "x:Q", "y:Q"])
        layers = [dots]
        if fit:
            layers.insert(0, fit_line(visible, fit).encode(**axes))
        st.altair_chart(alt.layer(*layers), width="stretch")
        if count:
            st.write(f"Trial {visible.trial.iloc[-1]} · {count} of {total} shown")
        st.caption(f"Fitted slope: {fit.slope:.5g}" if fit else "A line needs at least two trials with distinct X values and a numerically valid fit.")

    render()


def show_trial_view(view, pairs, x, y, result):
    rows = pd.DataFrame({"trial": pairs.index + 1, "x": pairs[x], "y": pairs[y]})
    digest = blake2b(pd.util.hash_pandas_object(rows).values.tobytes(), digest_size=12).hexdigest()
    key = f"{view}_{x!r}_{y!r}_{digest}"
    axes = {}
    for field, title, channel in (("x", x, alt.X), ("y", y, alt.Y)):
        scale = alt.Scale(zero=False)
        if view == "Experiment replay":
            scale = alt.Scale(domain=[float(rows[field].min()), float(rows[field].max())], zero=False, nice=True)
        axes[field] = channel(f"{field}:Q", title=title, scale=scale)
    if view == "Trial influence":
        show_influence(rows, result, axes, key)
    else:
        show_replay(rows, axes, key)
