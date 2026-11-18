"""Data loading, statistics, text helpers and sample experiments."""
import io
import json
import os
import re

import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
SAMPLE_DIR = os.path.join(BASE_DIR, "assets", "sample_data")


# ----------------------------------------------------------------- data ----
def load_dataframe(uploaded_file=None, pasted_text=""):
    """Return a DataFrame from an uploaded CSV/Excel file or pasted CSV text."""
    try:
        if uploaded_file is not None:
            name = uploaded_file.name.lower()
            if name.endswith((".xlsx", ".xls")):
                return pd.read_excel(uploaded_file)
            return pd.read_csv(uploaded_file, sep=None, engine="python")
        if pasted_text and pasted_text.strip():
            return pd.read_csv(io.StringIO(pasted_text.strip()), sep=None, engine="python")
    except Exception as exc:  # surfaced to the UI
        raise ValueError(f"Could not read the readings: {exc}") from exc
    return None


def numeric_frame(df):
    """Keep columns that are (mostly) numeric, coerced to float."""
    if df is None:
        return pd.DataFrame()
    cols = {}
    for c in df.columns:
        s = pd.to_numeric(df[c], errors="coerce")
        if s.notna().mean() >= 0.6:
            cols[str(c)] = s
    return pd.DataFrame(cols)


def compute_stats(df):
    """Average / max / min / std-dev per numeric column + efficiency if found."""
    num = numeric_frame(df)
    result = {"columns": {}, "efficiency": None, "n_rows": int(len(num))}
    if num.empty:
        return result
    for c in num.columns:
        s = num[c].dropna()
        if len(s):
            result["columns"][c] = {
                "mean": float(s.mean()), "max": float(s.max()), "min": float(s.min()),
                "std": float(s.std(ddof=1)) if len(s) > 1 else 0.0, "count": int(len(s)),
            }
    result["efficiency"] = _efficiency(num)
    return result


def _efficiency(num):
    low = {c: c.lower() for c in num.columns}
    # 1) an explicit efficiency column
    for c, l in low.items():
        if "efficiency" in l or l in ("eta", "eff", "eff_%"):
            s = num[c].dropna()
            if len(s):
                s = s * 100 if s.max() <= 1.0 else s
                return {"mean": float(s.mean()), "max": float(s.max()), "min": float(s.min()),
                        "method": f"column '{c}'"}
    # 2) output / input
    ins = [c for c, l in low.items() if "input" in l or l.startswith(("pin", "p_in"))]
    outs = [c for c, l in low.items() if "output" in l or l.startswith(("pout", "p_out"))]
    if ins and outs:
        eff = (num[outs[0]] / num[ins[0]] * 100).replace([np.inf, -np.inf], np.nan).dropna()
        if len(eff):
            return {"mean": float(eff.mean()), "max": float(eff.max()), "min": float(eff.min()),
                    "method": f"{outs[0]} / {ins[0]}"}
    return None


def stats_to_text(stats):
    if not stats or not stats.get("columns"):
        return "No numerical readings were provided."
    lines = [f"Number of readings: {stats['n_rows']}"]
    for c, v in stats["columns"].items():
        lines.append(f"- {c}: mean={v['mean']:.4g}, max={v['max']:.4g}, "
                     f"min={v['min']:.4g}, std dev={v['std']:.4g}")
    e = stats.get("efficiency")
    if e:
        lines.append(f"- Efficiency ({e['method']}): mean={e['mean']:.2f}%, "
                     f"max={e['max']:.2f}%, min={e['min']:.2f}%")
    return "\n".join(lines)


def df_to_rows(df, max_rows=40):
    d = df.head(max_rows)
    header = [str(c) for c in d.columns]
    rows = []
    for _, r in d.iterrows():
        row = []
        for v in r.values:
            row.append(f"{v:.4g}" if isinstance(v, (int, float, np.number)) and not pd.isna(v) else str(v))
        rows.append(row)
    return header, rows


# ----------------------------------------------------------------- text ----
def clean_text(text):
    """Strip markdown the model may emit so reports stay plain academic prose."""
    if not text:
        return ""
    t = text.replace("\r", "")
    t = re.sub(r"```.*?```", "", t, flags=re.S)
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)
    t = re.sub(r"\*\*(.*?)\*\*", r"\1", t)
    t = re.sub(r"(?<!\*)\*(?!\s)(.*?)(?<!\s)\*(?!\*)", r"\1", t)
    t = re.sub(r"^\s*[\*•]\s+", "- ", t, flags=re.M)
    t = t.replace("`", "")
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def to_bullets(text):
    if not text or not text.strip():
        return ""
    lines = [l.strip(" -•\t") for l in text.splitlines() if l.strip()]
    if len(lines) == 1 and "," in lines[0]:
        lines = [p.strip() for p in lines[0].split(",") if p.strip()]
    return "\n".join(f"- {l}" for l in lines)


_UNI = {"–": "-", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"', "•": "-", "…": "...",
        "σ": "sigma", "η": "eta", "Ω": "Ohm", "μ": "u", "µ": "u", "ε": "epsilon", "Δ": "Delta",
        "ρ": "rho", "α": "alpha", "β": "beta", "θ": "theta", "λ": "lambda", "π": "pi",
        "≈": "~", "≤": "<=", "≥": ">=", "→": "->", "∝": "~", "²": "^2", "³": "^3",
        "⁻": "-", "¹": "^1", "√": "sqrt", "∞": "inf", "\u00a0": " "}


def latin1(text):
    """fpdf2 core fonts are Latin-1 only; transliterate common symbols."""
    for k, v in _UNI.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


def extract_json(raw):
    """Parse JSON even if the model wrapped it in fences or prose."""
    if not raw:
        raise ValueError("Empty model response")
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            return json.loads(raw[start:end + 1])
        raise


def safe_filename(name):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip())[:60] or "lab_report"


# -------------------------------------------------------------- samples ----
def _read(fn):
    with open(os.path.join(SAMPLE_DIR, fn), encoding="utf-8") as f:
        return f.read()


SAMPLES = {
    "Verification of Ohm's Law (Electrical)": {
        "department": "Electrical",
        "experiment": "Verification of Ohm's Law",
        "aim": "To verify Ohm's law by plotting the V-I characteristic of a fixed carbon resistor and to determine its resistance.",
        "theory": "Ohm's law states that the current through a conductor is directly proportional to the potential difference across it at constant temperature, V = IR. The slope of the V-I graph gives the resistance R.",
        "apparatus": "Variable DC power supply (0-30 V)\nDigital multimeter (voltmeter)\nDigital milliammeter\n220 ohm carbon resistor\nBreadboard and connecting wires",
        "procedure": "Connected the resistor in series with the milliammeter and the supply. Connected the voltmeter across the resistor. Increased the supply voltage from 1 V to 10 V in steps of 1 V and recorded the current at each step. Switched off the supply between readings to limit heating.",
        "observations": "Resistor colour code red-red-brown (220 ohm, 5 % tolerance). Room temperature 27 C. Readings were steady at every step and the resistor stayed cool to touch.",
        "csv": "ohms_law.csv",
    },
    "Centrifugal Pump Performance Test (Mechanical)": {
        "department": "Mechanical",
        "experiment": "Performance Test on a Centrifugal Pump",
        "aim": "To determine the head-flow and efficiency-flow characteristics of a single-stage centrifugal pump at constant speed.",
        "theory": "Hydraulic output power is P_out = rho g Q H. Overall efficiency is eta = P_out / P_in. For a centrifugal pump at constant speed, head falls as flow rate rises and efficiency peaks near the best efficiency point (BEP).",
        "apparatus": "Single-stage centrifugal pump with motor\nSump tank and collecting tank\nPressure gauge and vacuum gauge\nWattmeter\nStopwatch\nDelivery valve",
        "procedure": "Primed the pump and started it with the delivery valve closed. Opened the valve in steps to vary flow from 5 to 40 LPM. At each setting recorded delivery pressure, head, flow (collecting tank method) and electrical input power. Output power was calculated from rho g Q H.",
        "observations": "Pump speed constant at 2900 rpm. Water temperature 28 C. Slight vibration observed at the highest flow settings. No leakage at the glands.",
        "csv": "pump_test.csv",
    },
}


def sample_csv(name):
    return _read(SAMPLES[name]["csv"])
