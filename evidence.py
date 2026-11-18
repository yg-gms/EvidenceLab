"""Build the numerical evidence sent for a relationship interpretation."""

from hashlib import sha256
import json

from calculations import RegressionResult, summarize_data


SCHEMA_VERSION = 2
GROUP_CAP = 30


def fingerprint(pairs, x, y, metadata):
    """Hash the selected finite pairs and interpretation inputs in memory."""
    columns = [pairs[column].to_numpy() for column in (x, y)]
    header = json.dumps(
        [metadata, x, y, len(pairs), [values.dtype.str for values in columns]],
        sort_keys=True, allow_nan=False,
    )
    digest = sha256(header.encode("utf-8"))
    for values in columns:
        digest.update(values.tobytes())
    return digest.hexdigest()


def build_evidence(
    pairs, x, y, uploaded_rows, result: RegressionResult, question, hypothesis, notes,
):
    """Describe already-cleaned pairs and the existing regression without raw rows."""
    summary = summarize_data(pairs, x, y)
    valid = len(pairs)
    excluded = uploaded_rows - valid
    total_groups = len(summary)
    constant_y = pairs[y].nunique() == 1
    evidence = {}

    def add(evidence_id, label, value, status="available", **details):
        evidence[evidence_id] = {"label": label, "value": value, "status": status, **details}

    add("counts.uploaded", "Uploaded rows", uploaded_rows)
    add("counts.valid", "Valid pairs", valid)
    add("counts.excluded", "Excluded rows", excluded)
    add("counts.unique_x", "Unique X values", total_groups)
    add("counts.single_trial_groups", "X groups with one trial", int(summary["count"].eq(1).sum()))
    add("ranges.x", f"Observed range of {x}", [pairs[x].min().item(), pairs[x].max().item()])
    add("ranges.y", f"Observed range of {y}", [pairs[y].min().item(), pairs[y].max().item()])
    add("regression.slope", "Slope", float(result.slope))
    add("regression.intercept", "Intercept", float(result.intercept))
    for name, label, value in (
        ("r", "Pearson r", result.r),
        ("r_squared", "R²", result.r_squared),
    ):
        if value is not None:
            add(f"regression.{name}", label, float(value))
        elif result.r_squared is None:
            reason = "Y is constant" if constant_y else "Y has no variation at regression precision"
            add(f"regression.{name}", label, None, "undefined", reason=reason)
        else:
            add(f"regression.{name}", label, None, "unavailable", reason="Fewer than three valid pairs")
    add("facts.constant_y", "Y is constant", constant_y)
    add("facts.fewer_than_five_pairs", "Fewer than five valid pairs", valid < 5)
    add("facts.rows_excluded", "Rows were excluded", excluded > 0)

    # Evenly spaced positions in sorted X include both endpoints.
    positions = range(total_groups)
    if total_groups > GROUP_CAP:
        positions = [i * (total_groups - 1) // (GROUP_CAP - 1) for i in range(GROUP_CAP)]
    for position, (x_value, mean, sd, count) in zip(
        positions, summary.iloc[positions].itertuples(), strict=True,
    ):
        group = {"x": x_value, "count": count, "mean": mean, "sample_sd": sd if count > 1 else None}
        sd_details = {"sample_sd_status": "available"}
        if count == 1:
            sd_details = {"sample_sd_status": "undefined", "sample_sd_reason": "Only one trial"}
        add(f"groups.{position + 1}", f"Group at X = {x_value}", group, **sd_details)

    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_mode": "linear_relationship",
        "variables": {"x": x, "y": y},
        "student_context": {
            "question": question or None, "hypothesis": hypothesis or None, "method_notes": notes or None,
        },
        "group_summary": {"total_groups": total_groups, "groups_omitted": total_groups > GROUP_CAP},
        "metadata": {
            "regression": "Ordinary least squares using all valid individual trials",
            "error_bars": "Mean ± one sample standard deviation",
        },
        "evidence": evidence,
    }
