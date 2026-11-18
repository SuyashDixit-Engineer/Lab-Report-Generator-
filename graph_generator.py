"""Automatic graph generation (Feature 2)."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from utils import numeric_frame, safe_filename

sns.set_theme(style="whitegrid", context="notebook")

# Pretty axis titles for common engineering quantities
_PRETTY = {
    "v": "Voltage", "voltage": "Voltage", "i": "Current", "current": "Current",
    "t": "Time", "time": "Time", "temp": "Temperature", "temperature": "Temperature",
    "p": "Pressure", "pressure": "Pressure", "flow": "Flow Rate", "stress": "Stress",
    "strain": "Strain", "load": "Load", "head": "Head",
}


def _label(col):
    return col.replace("_", " ").strip()


def generate_graphs(df, outdir, max_graphs=4, prefix="graph"):
    """Plot each numeric column against the first numeric column (the x-axis).

    Returns a list of {"path", "title"} dicts. Also fits a least-squares line
    and reports slope / R^2 in the legend, which is what lab reports need.
    """
    num = numeric_frame(df).dropna(how="all")
    if num.shape[1] < 2 or len(num) < 2:
        return []
    os.makedirs(outdir, exist_ok=True)
    xcol = num.columns[0]
    graphs = []
    for ycol in list(num.columns[1:])[:max_graphs]:
        d = num[[xcol, ycol]].dropna()
        if len(d) < 2:
            continue
        x, y = d[xcol].to_numpy(float), d[ycol].to_numpy(float)
        fig, ax = plt.subplots(figsize=(7, 4.2), dpi=150)
        ax.plot(x, y, "o-", color="#0B5394", lw=1.8, ms=5, label="Experimental data")
        if len(d) >= 3 and np.ptp(x) > 0:
            m, c = np.polyfit(x, y, 1)
            ss_res = float(np.sum((y - (m * x + c)) ** 2))
            ss_tot = float(np.sum((y - y.mean()) ** 2)) or 1.0
            r2 = 1 - ss_res / ss_tot
            ax.plot(x, m * x + c, "--", color="#E69F00", lw=1.4,
                    label=f"Linear fit: y = {m:.4g}x + {c:.4g} (R² = {r2:.3f})")
        title = f"{_label(ycol)} vs {_label(xcol)}"
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlabel(_label(xcol))
        ax.set_ylabel(_label(ycol))
        ax.legend(fontsize=8, loc="best")
        fig.tight_layout()
        path = os.path.join(outdir, f"{prefix}_{safe_filename(ycol)}.png")
        fig.savefig(path)
        plt.close(fig)
        graphs.append({"path": path, "title": title})
    return graphs
