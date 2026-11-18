"""Local EvidenceLab website. Each request carries its dataset; no shared upload store."""
import io
import os
from pathlib import Path
import tomllib

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, ValidationError
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from calculations import linear_regression, prepare_relationship_data, summarize_data
from evidence import build_evidence
from interpretation import DEFAULT_MODEL, InterpretationError, ask_question

ROOT = Path(__file__).resolve().parent
SAMPLES = {"growth": "synthetic_exponential_growth.csv", "spring": "sample.csv"}
MAX_CSV = 1_000_000


class Inputs(BaseModel):
    csv: str = Field(min_length=1, max_length=MAX_CSV)
    x: str = ""
    y: str = ""
    first_trials: int | None = Field(default=None, ge=1, le=5000)
    excluded: list[int] = Field(default_factory=list, max_length=5000)
    research: str = Field(default="", max_length=500)
    question: str = Field(default="", max_length=1000)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=8)


def configuration():
    path = ROOT / ".streamlit/secrets.toml"
    settings = {}
    if path.exists():
        try:
            with path.open("rb") as file:
                settings = tomllib.load(file)
        except (OSError, ValueError):
            pass
    def get(name):
        return os.getenv(name) or settings.get("openai", {}).get(name) or settings.get(name, "")
    return get("OPENAI_API_KEY"), get("OPENAI_MODEL") or DEFAULT_MODEL


def read_csv(source):
    try:
        df = pd.read_csv(io.StringIO(source), nrows=5001)
    except (ValueError, OSError):
        raise ValueError("Use a UTF-8, comma-separated CSV with a header and consistent columns.") from None
    if not isinstance(df.index, pd.RangeIndex):
        raise ValueError("A row contains more fields than the header.")
    if df.empty:
        raise ValueError("The CSV has no data rows.")
    if len(df) > 5000 or len(df.columns) > 100:
        raise ValueError("For this workspace, choose at most 5,000 rows and 100 columns.")
    return df


def dataset(df):
    numeric = set(df.select_dtypes(include="number"))
    columns = []
    for name in df.columns:
        col = df[name]
        finite = col.replace([np.inf, -np.inf], np.nan).dropna() if name in numeric else None
        mean = finite.mean() if finite is not None and len(finite) else None
        columns.append({
            "name": name, "numeric": name in numeric, "type": "Numeric" if name in numeric else (
                "Boolean" if pd.api.types.is_bool_dtype(col) else "Text"), "missing": int(col.isna().sum()),
            "infinite": int(col.count() - len(finite)) if finite is not None else 0,
            "mean": float(mean) if mean is not None and np.isfinite(mean) else None,
            "min": float(finite.min()) if finite is not None and len(finite) else None,
            "max": float(finite.max()) if finite is not None and len(finite) else None,
        })
    # Preserve strings and distinguish infinity from an empty cell in the explorer.
    rows = df.astype(object).replace({np.inf: "∞", -np.inf: "−∞"}).where(df.notna(), None)
    return {"columns": columns, "rows": rows.values.tolist()}


def relationship(df, inputs, for_chat=False):
    pairs = prepare_relationship_data(df, inputs.x, inputs.y)
    missing = len(df) - len(pairs)
    omitted = set(inputs.excluded)
    if not omitted.issubset(set(pairs.index + 1)):
        raise ValueError("An excluded trial is outside the current selection.")
    x, y = inputs.x, inputs.y
    # Screen once on all finite Y values so exclusions do not move the goalposts.
    flags = []
    if len(pairs) >= 4:
        q1, q3 = pairs[y].quantile([0.25, 0.75])
        spread = q3 - q1
        flags = (pairs.index[(pairs[y] < q1 - 1.5 * spread) | (pairs[y] > q3 + 1.5 * spread)] + 1).tolist()
    kept = pairs.loc[~(pairs.index + 1).isin(omitted)]
    if inputs.first_trials is not None and not for_chat:
        kept = kept.iloc[:inputs.first_trials]
    fit = None
    warnings = []
    try:
        fit = linear_regression(kept, x, y)
    except ValueError as error:
        warnings.append(str(error))
    if missing:
        warnings.append(f"{missing} row(s) lack a finite value for both selected variables and were skipped.")
    if len(kept) < 5:
        warnings.append("Fewer than five pairs remain. A trend can depend heavily on a single observation.")
    if fit and fit.r is None:
        warnings.append("Pearson r is undefined for constant Y or fewer than three pairs.")
    if for_chat:
        context = {"variables": {"x": x, "y": y}, "research_question": inputs.research,
                   "rows": len(df), "finite_pairs_used": len(kept), "missing_pairs": missing,
                   "user_excluded_count": len(omitted), "iqr_flagged_y_count_before_exclusion": len(flags),
                   "warnings": warnings}
        if fit:
            try:
                context["relationship"] = build_evidence(kept, x, y, len(df), fit, inputs.research, "", "")
            except ValueError as error:
                context["warnings"].append(str(error))
                context["regression"] = {"slope": fit.slope, "intercept": fit.intercept,
                                         "r": fit.r, "r_squared": fit.r_squared}
        elif len(kept):
            context["selected_ranges"] = {col: [float(kept[col].min()), float(kept[col].max())] for col in (x, y)}
        return context
    try:
        summary = summarize_data(kept, x, y)
        groups = [{"x": xv, "mean": avg, "sd": sd if n > 1 else None, "count": n}
                  for xv, avg, sd, n in summary.itertuples()]
    except ValueError as error:
        warnings.append(str(error))
        groups = []
    points = [{"row": int(i + 1), "x": xv, "y": yv} for i, xv, yv in kept.itertuples()]
    histogram = []
    if len(kept):
        try:
            counts, edges = np.histogram(kept[y], bins=min(15, max(1, int(np.sqrt(len(kept))))))
            histogram = [{"low": float(a), "high": float(b), "count": int(c)}
                         for a, b, c in zip(edges[:-1], edges[1:], counts)]
        except (ValueError, OverflowError, IndexError):
            warnings.append("Rescale the values to show distribution bins.")
    regression = None
    if fit:
        ends = [kept[x].argmin(), kept[x].argmax()]
        regression = {"r": fit.r, "r2": fit.r_squared, "slope": fit.slope, "intercept": fit.intercept,
                      "line": [{"x": float(kept[x].iloc[i]), "y": float(fit.fitted_values[i])} for i in ends]}
    original_slope = fit.slope if fit else None
    if omitted:
        try:
            original_slope = linear_regression(pairs, x, y).slope
        except ValueError:
            original_slope = None
    return {"original_slope": original_slope, "points": points, "groups": groups, "histogram": histogram, "fit": regression,
            "flags": flags, "missing": missing, "warnings": warnings}


def process(action, inputs):
    df = read_csv(inputs.csv)
    if action == "dataset":
        return dataset(df)
    if action == "analysis":
        return relationship(df, inputs)
    if not inputs.question.strip():
        raise ValueError("Enter a question first.")
    if any(set(m) != {"role", "content"} or m["role"] not in {"user", "assistant"}
           or len(m["content"]) > 12000 for m in inputs.history):
        raise ValueError("Invalid conversation history.")
    if inputs.x and inputs.y:
        context = relationship(df, inputs, for_chat=True)
    else:
        context = {"rows": len(df), "columns": len(df.columns), "research_question": inputs.research,
                   "limitation": "No numeric pair selected. No relationship has been calculated."}
    return {"answer": ask_question(context, inputs.history, inputs.question, *configuration())}


async def api(request):
    action = request.path_params["action"]
    if action not in {"dataset", "analysis", "chat"}:
        return JSONResponse({"error": "Unknown action."}, status_code=404)
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        return JSONResponse({"error": "Send JSON."}, status_code=415)
    try:
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 2_500_000:
                raise ValueError("Choose a smaller CSV (up to 1 MB).")
        inputs = Inputs.model_validate_json(bytes(body))
        return JSONResponse(await run_in_threadpool(process, action, inputs))
    except ValidationError:
        return JSONResponse({"error": "Check the CSV size and input lengths."}, status_code=400)
    except InterpretationError as error:
        return JSONResponse({"error": str(error)}, status_code=503)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)


async def sample(request):
    name = request.path_params["name"]
    if name == "influence":
        return PlainTextResponse("X,Y\n1,4\n2,3\n3,2\n4,1\n8,12\n")
    if name not in SAMPLES:
        return PlainTextResponse("Unknown sample", status_code=404)
    return PlainTextResponse((ROOT / SAMPLES[name]).read_text())


app = Starlette(routes=[
    Route("/api/sample/{name}", sample),
    Route("/api/{action}", api, methods=["POST"]),
    Mount("/", app=StaticFiles(directory=ROOT / "web/dist", html=True, check_dir=False)),
])
