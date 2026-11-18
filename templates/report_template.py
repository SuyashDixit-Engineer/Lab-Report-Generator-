"""Academic report layout + department intelligence."""
import os
from utils import df_to_rows, to_bullets

DEPARTMENTS = ["Mechanical", "Electrical", "Civil", "Electronics", "Chemical"]

DEPARTMENT_FOCUS = {
    "Mechanical": (
        "Use Mechanical Engineering terminology: thermodynamics (energy balance, first/second law, "
        "irreversibility), heat transfer (conduction, convection, thermal resistance), fluid mechanics "
        "(Bernoulli's equation, head loss, Reynolds number, cavitation, BEP), and mechanics of "
        "materials (stress, strain, elastic modulus, factor of safety)."
    ),
    "Electrical": (
        "Use Electrical Engineering terminology: circuit theory (KVL, KCL, Ohm's law, impedance, "
        "phasor relationships, power factor), machine performance (copper/core losses, voltage "
        "regulation, efficiency), and instrumentation (meter burden, calibration, linearity)."
    ),
    "Civil": (
        "Use Civil Engineering terminology: structural mechanics (bending moment, shear force, "
        "deflection, load-bearing capacity), geotechnical/material properties (compressive strength, "
        "workability, compaction, permeability), and IS/ASTM standard compliance."
    ),
    "Electronics": (
        "Use Electronics Engineering terminology: semiconductor device physics (Q-point biasing, "
        "forward/reverse characteristics, cut-off/saturation), signal processing (gain, bandwidth, "
        "frequency response, SNR), and component tolerances."
    ),
    "Chemical": (
        "Use Chemical Engineering terminology: mass and energy balances, reaction kinetics (rate "
        "constant, conversion, yield, selectivity), transport phenomena (heat/mass transfer "
        "coefficients, dimensionless numbers), and process control."
    ),
}


def build_blocks(report):
    m, s = report["meta"], report["sections"]
    out = []

    def add(heading, blocks):
        cleaned = [b for b in blocks if b and (b[0] != "text" or str(b[1]).strip())]
        if cleaned:
            out.append((heading, cleaned))

    # 1. Aim
    add("Aim", [("text", m.get("aim", ""))])

    # 2. Apparatus / Equipment / Setup (+ Setup Image)
    app_blocks = [("text", to_bullets(m.get("apparatus", "")))]
    setup_img = m.get("setup_image_path")
    if setup_img and os.path.exists(setup_img):
        app_blocks.append(("image", setup_img, "Figure 1: Experimental Apparatus / Setup"))
    add("Apparatus / Equipment / Setup", app_blocks)

    # 3. Objectives
    add("Objectives", [("text", s.get("objectives") or m.get("objectives", ""))])

    # 4. Problem Statement / Description
    add("Problem Statement / Description", [("text", s.get("problem_statement") or m.get("problem_statement", ""))])

    # 5. Introduction
    add("Introduction", [("text", s.get("introduction") or m.get("introduction", ""))])

    # 6. Assumptions & Specifications
    add("Assumptions & Specifications", [("text", s.get("assumptions") or m.get("assumptions", ""))])

    # 7. Theory
    add("Theory", [("text", s.get("theory") or m.get("theory", ""))])

    # 8. Mathematical Modeling (Rendered as clean mathematical equations)
    math_content = s.get("mathematical_modeling") or m.get("math_modeling", "")
    if math_content.strip():
        add("Mathematical Modeling", [("latex", math_content)])

    # 9. Procedure
    add("Procedure", [("text", s.get("procedure") or m.get("procedure", ""))])

    # 10. Observations, Readings & Graphical Analysis (No Observations Notes)
    obs_blocks = []
    df = report.get("df")
    if df is not None and len(df):
        header, rows = df_to_rows(df, max_rows=40)
        obs_blocks.append(("sub", "Observation Table"))
        obs_blocks.append(("table", header, rows))

    st_ = report.get("stats") or {}
    if st_.get("columns"):
        header = ["Parameter", "Mean", "Max", "Min", "Std Dev"]
        rows = [
            [c, f"{v['mean']:.4g}", f"{v['max']:.4g}", f"{v['min']:.4g}", f"{v['std']:.4g}"]
            for c, v in st_["columns"].items()
        ]
        obs_blocks.append(("sub", "Statistical Summary"))
        obs_blocks.append(("table", header, rows))
        eff = st_.get("efficiency")
        if eff:
            obs_blocks.append((
                "text",
                f"Computed Efficiency ({eff['method']}): mean = {eff['mean']:.2f} %, "
                f"maximum = {eff['max']:.2f} %, minimum = {eff['min']:.2f} %.",
            ))

    graphs = report.get("graphs") or []
    fig_offset = 2 if (setup_img and os.path.exists(setup_img)) else 1
    for i, g in enumerate(graphs, fig_offset):
        obs_blocks.append(("image", g["path"], f"Figure {i}: {g['title']}"))

    add("Observations & Graphical Analysis", obs_blocks)

    # 11. Calculations (AI using user's exact formulas)
    add("Calculations", [("text", s.get("calculations", ""))])

    # 12. Error Analysis (Optional, AI)
    if s.get("error_analysis", "").strip():
        add("Error Analysis", [("text", s["error_analysis"])])

    # 13. Results (AI)
    add("Results", [("text", s.get("results", ""))])

    # 14. Conclusion (AI)
    add("Conclusion", [("text", s.get("conclusion", ""))])

    return out