"""Lab Report Generator - Institutional & Corporate Streamlit Application."""
import base64
import datetime
import html
import os
import re
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from ai_engine import AIEngine, _normalize_latex_blocks, latex_to_readable
from graph_generator import generate_graphs
from report_generator import build_docx, build_pdf
from templates.report_template import DEPARTMENTS, build_blocks
from utils import OUTPUT_DIR, SAMPLES, compute_stats, load_dataframe, safe_filename, sample_csv

load_dotenv()

st.set_page_config(
    page_title="Lab Report Generator | Institutional Academic Suite",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------- theme state -----
st.session_state.setdefault("ui_theme", "Light")

FIELDS = [
    "aim", "apparatus", "objectives", "problem_statement", "introduction",
    "assumptions", "theory", "math_modeling", "procedure", "readings_text",
    "experiment", "student", "prn", "year", "roll_no", "division", "batch",
]
for k in FIELDS:
    st.session_state.setdefault(k, "")
st.session_state.setdefault("department", DEPARTMENTS[0])
st.session_state.setdefault("exp_date", datetime.date.today())
st.session_state.setdefault("include_error_analysis", True)

_SAMPLE_EXTRAS = {
    "Ohm's Law": {
        "objectives": (
            "- To verify the linear relationship between potential difference (V) and electric current (I) across a fixed carbon resistor.\n"
            "- To determine the experimental resistance of the resistor from V-I readings and compare it with the nominal color-code value."
        ),
        "problem_statement": (
            "In DC electrical circuits, predicting current draw under varying supply voltages requires verifying whether a resistive element obeys Ohm's law within its safe thermal operating range."
        ),
        "introduction": (
            "Ohm's law establishes that the steady-state current flowing through a metallic or carbon conductor is directly proportional to the applied potential difference across its terminals when temperature remains constant."
        ),
        "assumptions": (
            "- Ambient room temperature remains constant at 27 °C with negligible Joule self-heating.\n"
            "- Internal resistance of the DC power supply and connecting leads is negligible.\n"
            "- Digital voltmeter and milliammeter have negligible loading effect on the circuit."
        ),
        "math_modeling": (
            r"$$R = \frac{V}{I}$$" + "\n"
            "- R: Electrical resistance (Ohm)\n"
            "- V: Potential difference across resistor (V)\n"
            "- I: Circuit current (A)\n"
            r"$$\% \text{ Error} = \frac{|R_{exp} - R_{nominal}|}{R_{nominal}} \times 100\%$$" + "\n"
            "- R_exp: Mean experimental resistance (Ohm)\n"
            "- R_nominal: Nominal color-code resistance (220 Ohm)"
        ),
    },
    "Centrifugal Pump": {
        "objectives": (
            "- To evaluate the head-discharge (H-Q) and efficiency-discharge characteristics of a single-stage centrifugal pump at constant speed.\n"
            "- To determine the hydraulic output power, overall pump efficiency, and Best Efficiency Point (BEP)."
        ),
        "problem_statement": (
            "Centrifugal pumps exhibit non-linear trade-offs between flow rate, total dynamic head, and power consumption. Quantifying these performance curves is essential for sizing pumping systems near their Best Efficiency Point."
        ),
        "introduction": (
            "A centrifugal pump converts mechanical shaft energy into fluid pressure and kinetic energy via a rotating impeller. Evaluating input electrical power against hydraulic power reveals internal friction, leakage, and shock losses across varying discharge rates."
        ),
        "assumptions": (
            "- Working fluid is clean water at ambient temperature with constant density rho = 1000 kg/m^3.\n"
            "- Acceleration due to gravity g = 9.81 m/s^2 and impeller rotational speed remains constant.\n"
            "- Steady-state incompressible flow conditions prevail at each valve opening."
        ),
        "math_modeling": (
            r"$$P_{out} = \rho g Q H$$" + "\n"
            "- P_out: Hydraulic output power (W)\n"
            "- rho: Density of water (1000 kg/m^3)\n"
            "- g: Acceleration due to gravity (9.81 m/s^2)\n"
            "- Q: Volumetric flow rate (m^3/s)\n"
            "- H: Total manometric head (m)\n"
            r"$$\eta = \frac{P_{out}}{P_{in}} \times 100\%$$" + "\n"
            "- eta: Overall pump efficiency (%)\n"
            "- P_in: Electrical input power (W)"
        ),
    },
}


# --------------------------------- corporate white glass + motion engine ----
def _apply_corporate_glass_motion(theme: str):
    dark = theme == "Dark"

    if dark:
        app_bg = "#0A1716"
        surface_glass = "rgba(18, 42, 40, 0.72)"
        sidebar_glass = "rgba(14, 34, 32, 0.92)"
        input_bg = "rgba(11, 28, 27, 0.75)"
        border_col = "rgba(164, 214, 208, 0.16)"
        text_main = "#F0F9F8"
        text_muted = "#99BDB8"
        card_shadow = "0 14px 36px rgba(0, 0, 0, 0.35)"
    else:
        app_bg = "#FFFFFF"
        surface_glass = "rgba(255, 255, 255, 0.86)"
        sidebar_glass = "rgba(249, 252, 251, 0.94)"
        input_bg = "rgba(250, 252, 252, 0.94)"
        border_col = "rgba(23, 62, 60, 0.12)"
        text_main = "#143533"
        text_muted = "#5A7673"
        card_shadow = "0 14px 38px rgba(20, 53, 51, 0.06)"

    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

    :root {{
        --forest-dark: #153937;
        --forest-mid: #1D4D4A;
        --teal-accent: #137A73;
        --amber-gold: #F3A825;
        --amber-hover: #E09412;
        --glass-surface: {surface_glass};
        --glass-border: {border_col};
        --text-primary: {text_main};
        --text-secondary: {text_muted};
    }}

    /* ===================== KEYFRAME MOTION LIBRARY ===================== */
    @keyframes fadeSlideUp {{
        0% {{ opacity: 0; transform: translateY(20px); }}
        100% {{ opacity: 1; transform: translateY(0); }}
    }}

    @keyframes fadeSlideRight {{
        0% {{ opacity: 0; transform: translateX(-18px); }}
        100% {{ opacity: 1; transform: translateX(0); }}
    }}

    @keyframes floatCard {{
        0%, 100% {{ transform: rotate(5deg) translateY(0px); }}
        50% {{ transform: rotate(3.5deg) translateY(-10px); }}
    }}

    @keyframes spinOrbitSlow {{
        0% {{ transform: rotate(-24deg) scale(1); }}
        50% {{ transform: rotate(-18deg) scale(1.04); }}
        100% {{ transform: rotate(-24deg) scale(1); }}
    }}

    @keyframes spinOrbitReverse {{
        0% {{ transform: rotate(35deg) scale(1); }}
        50% {{ transform: rotate(42deg) scale(0.97); }}
        100% {{ transform: rotate(35deg) scale(1); }}
    }}

    @keyframes pulseBeacon {{
        0%, 100% {{ box-shadow: 0 0 0 0 rgba(243, 168, 37, 0.55); }}
        50% {{ box-shadow: 0 0 0 7px rgba(243, 168, 37, 0); }}
    }}

    @keyframes twinkleStar {{
        0%, 100% {{ opacity: 0.55; transform: scale(0.92) rotate(0deg); }}
        50% {{ opacity: 1; transform: scale(1.18) rotate(12deg); }}
    }}

    @keyframes shimmerSweep {{
        0% {{ left: -120%; }}
        60%, 100% {{ left: 130%; }}
    }}

    @keyframes equaliserBar {{
        0%, 100% {{ transform: scaleY(1); }}
        50% {{ transform: scaleY(0.74); }}
    }}

    /* ===================== CLEAN CHROME & RESPONSIVE SIDEBAR ===================== */
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    #MainMenu,
    footer {{
        display: none !important;
        visibility: hidden !important;
    }}

    header[data-testid="stHeader"] {{
        background: transparent !important;
    }}

    /* Lock Sidebar Permanently Open ONLY on Desktop (> 768px) */
    @media (min-width: 769px) {{
        [data-testid="stSidebarCollapseButton"],
        [data-testid="collapsedControl"],
        button[kind="header"] {{
            display: none !important;
            visibility: hidden !important;
        }}
        header[data-testid="stHeader"] {{
            height: 0px !important;
        }}
        section[data-testid="stSidebar"] {{
            min-width: 320px !important;
            max-width: 320px !important;
            width: 320px !important;
            transform: none !important;
        }}
    }}

    html {{
        scroll-behavior: smooth;
    }}

    html, body, [class*="css"] {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }}

    h1, h2, h3, .hero h1, .sec, .corp-nav-brand, .why-title, .footer-brand {{
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }}

    .stApp {{
        background-color: {app_bg} !important;
        background-image:
            radial-gradient(circle at 88% 8%, rgba(23, 62, 60, 0.04) 0%, transparent 32%),
            radial-gradient(circle at 12% 45%, rgba(243, 168, 37, 0.04) 0%, transparent 34%),
            radial-gradient(circle at 85% 82%, rgba(19, 122, 115, 0.04) 0%, transparent 35%) !important;
        color: {text_main} !important;
    }}

    .block-container {{
        max-width: 1380px;
        padding-top: 1.2rem !important;
        padding-bottom: 2.5rem !important;
    }}

    .stApp h1, .stApp h2, .stApp h3, .stApp p, .stApp label, .stApp span {{
        color: {text_main};
    }}

    .stCaption, [data-testid="stCaptionContainer"] p {{
        color: {text_muted} !important;
    }}

    /* Frosted Glass Sidebar */
    section[data-testid="stSidebar"] {{
        background: {sidebar_glass} !important;
        backdrop-filter: blur(22px) saturate(160%) !important;
        -webkit-backdrop-filter: blur(22px) saturate(160%) !important;
        border-right: 1px solid {border_col} !important;
        box-shadow: 6px 0 32px rgba(20, 53, 51, 0.05) !important;
        animation: fadeSlideRight 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
    }}

    section[data-testid="stSidebar"] > div:first-child {{
        padding-top: 1.35rem;
        padding-left: 1.15rem;
        padding-right: 1.15rem;
    }}

    section[data-testid="stSidebar"] hr {{
        border-color: {border_col} !important;
        margin: 0.95rem 0 !important;
    }}

    /* ===================== TOP CORPORATE GLASS NAVBAR ===================== */
    .corp-navbar {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.85rem 1.5rem;
        margin-bottom: 1.1rem;
        background: {surface_glass};
        backdrop-filter: blur(18px) saturate(160%);
        -webkit-backdrop-filter: blur(18px) saturate(160%);
        border: 1px solid {border_col};
        border-radius: 18px;
        box-shadow: {card_shadow};
        animation: fadeSlideUp 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
    }}

    .corp-nav-brand {{
        display: flex;
        align-items: center;
        gap: 11px;
        font-weight: 800;
        font-size: 1.12rem;
        color: {text_main};
        letter-spacing: -0.02em;
        cursor: pointer;
    }}

    .corp-brand-badge {{
        width: 34px;
        height: 34px;
        border-radius: 10px;
        background: linear-gradient(135deg, #153937, #137A73);
        color: #F3A825 !important;
        display: grid;
        place-items: center;
        font-size: 1rem;
        font-weight: 800;
        box-shadow: 0 6px 14px rgba(21, 57, 55, 0.22);
    }}

    .corp-nav-links {{
        display: flex;
        align-items: center;
        gap: 22px;
    }}

    .nav-action-link {{
        background: none;
        border: none;
        padding: 4px 2px;
        cursor: pointer;
        color: {text_muted};
        font-family: 'Inter', sans-serif;
        font-size: 0.86rem;
        font-weight: 600;
        transition: color 0.2s ease, transform 0.2s ease;
    }}

    .nav-action-link:hover {{
        color: #137A73;
        transform: translateY(-1px);
    }}

    .corp-nav-actions {{
        display: flex;
        align-items: center;
        gap: 12px;
    }}

    .corp-status-pill {{
        display: inline-flex;
        align-items: center;
        gap: 7px;
        padding: 5px 12px;
        border-radius: 999px;
        background: rgba(19, 122, 115, 0.09);
        border: 1px solid rgba(19, 122, 115, 0.2);
        color: #137A73 !important;
        font-size: 0.74rem;
        font-weight: 700;
    }}

    .corp-status-dot {{
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #10B981;
        animation: pulseBeacon 2s infinite;
    }}

    .corp-nav-cta {{
        border: none;
        cursor: pointer;
        background: #F3A825;
        color: #143533 !important;
        padding: 8px 18px;
        border-radius: 999px;
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 0.82rem;
        font-weight: 700;
        box-shadow: 0 4px 14px rgba(243, 168, 37, 0.32);
        transition: all 0.2s ease;
    }}

    .corp-nav-cta:hover {{
        background: #E09412;
        transform: translateY(-1.5px);
        box-shadow: 0 7px 20px rgba(243, 168, 37, 0.45);
    }}

    /* ===================== SIGNATURE EMERALD HERO SECTION ===================== */
    .hero {{
        position: relative;
        overflow: hidden;
        padding: 2.75rem 3rem 1.85rem;
        margin: 0 0 1.8rem;
        border-radius: 26px 26px 68px 26px;
        background:
            radial-gradient(circle at 82% 24%, rgba(243, 168, 37, 0.20), transparent 36%),
            radial-gradient(circle at 18% 85%, rgba(25, 148, 138, 0.28), transparent 45%),
            linear-gradient(128deg, #143634 0%, #1B4946 58%, #155B56 100%);
        border: 1px solid rgba(255, 255, 255, 0.16);
        box-shadow: 0 24px 50px rgba(20, 54, 52, 0.18), inset 0 1px 0 rgba(255, 255, 255, 0.18);
        animation: fadeSlideUp 0.65s cubic-bezier(0.22, 1, 0.36, 1) 0.08s both;
    }}

    .hero-kicker {{
        display: inline-flex;
        align-items: center;
        gap: 9px;
        padding: 6px 14px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.09);
        border: 1px solid rgba(255, 255, 255, 0.16);
        backdrop-filter: blur(12px);
        color: #DDF2EF !important;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.13em;
        margin-bottom: 1.05rem;
    }}

    .hero-dot {{
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #F3A825;
        animation: pulseBeacon 2.2s infinite;
    }}

    .hero-layout {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 2.2rem;
        min-height: 220px;
    }}

    .hero-copy {{
        max-width: 680px;
        position: relative;
        z-index: 2;
    }}

    .hero h1 {{
        color: #FFFFFF !important;
        font-size: clamp(2.2rem, 4.1vw, 3.55rem);
        line-height: 1.07;
        letter-spacing: -0.04em;
        font-weight: 800;
        margin: 0 0 0.9rem;
    }}

    .hero h1 em {{
        color: #F6B945;
        font-style: normal;
    }}

    .hero p {{
        color: #CBE4E0 !important;
        max-width: 610px;
        font-size: 0.98rem;
        line-height: 1.72;
        margin: 0;
    }}

    .hero-pills {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 1.3rem;
    }}

    .hero-pill-btn {{
        cursor: pointer;
        color: #F4FBFA !important;
        border: 1px solid rgba(255, 255, 255, 0.24);
        background: rgba(255, 255, 255, 0.10);
        backdrop-filter: blur(12px);
        padding: 7px 15px;
        border-radius: 999px;
        font-family: 'Inter', sans-serif;
        font-size: 0.76rem;
        font-weight: 600;
        transition: transform 0.25s ease, background 0.25s ease, border-color 0.25s ease;
    }}

    .hero-pill-btn:hover {{
        transform: translateY(-2px);
        background: rgba(243, 168, 37, 0.22);
        border-color: #F6B945;
    }}

    .hero-stats-row {{
        display: flex;
        align-items: center;
        gap: 28px;
        margin-top: 1.55rem;
        padding-top: 1.15rem;
        border-top: 1px solid rgba(255, 255, 255, 0.15);
    }}

    .hero-stat-item {{
        display: flex;
        flex-direction: column;
    }}

    .hero-stat-item strong {{
        color: #FFFFFF !important;
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 1.45rem;
        font-weight: 800;
        line-height: 1.15;
    }}

    .hero-stat-item small {{
        color: #B4D7D2 !important;
        font-size: 0.72rem;
        margin-top: 2px;
    }}

    .hero-stat-divider {{
        width: 1px;
        height: 32px;
        background: rgba(255, 255, 255, 0.18);
    }}

    /* Floating Animated Glass Preview Artifact */
    .hero-art {{
        width: 260px;
        height: 230px;
        flex: 0 0 260px;
        position: relative;
        display: grid;
        place-items: center;
    }}

    .hero-orbit {{
        position: absolute;
        border: 1px solid rgba(243, 168, 37, 0.34);
        border-radius: 50%;
    }}

    .orbit-one {{
        width: 232px;
        height: 155px;
        animation: spinOrbitSlow 9s ease-in-out infinite;
    }}

    .orbit-two {{
        width: 185px;
        height: 215px;
        border-color: rgba(255, 255, 255, 0.24);
        animation: spinOrbitReverse 11s ease-in-out infinite;
    }}

    .hero-art-card {{
        width: 166px;
        height: 182px;
        z-index: 1;
        border: 1px solid rgba(255, 255, 255, 0.35);
        border-radius: 18px;
        padding: 14px;
        background: linear-gradient(145deg, rgba(255, 255, 255, 0.24), rgba(255, 255, 255, 0.07));
        box-shadow: 0 22px 44px rgba(0, 0, 0, 0.28), inset 0 1px 0 rgba(255, 255, 255, 0.4);
        backdrop-filter: blur(16px);
        animation: floatCard 5.5s ease-in-out infinite;
    }}

    .art-card-top {{ display: flex; gap: 5px; }}
    .art-card-top span {{ width: 6px; height: 6px; border-radius: 50%; background: #F6B945; }}
    .art-icon {{ color: #F6B945; font-size: 1.95rem; line-height: 1; margin: 12px 0 8px; }}
    .art-line {{ width: 72%; height: 5px; border-radius: 5px; background: rgba(255, 255, 255, 0.42); margin: 7px 0; }}
    .art-line.long {{ width: 95%; }}
    .art-chart {{
        height: 40px;
        display: flex;
        align-items: end;
        gap: 5px;
        margin-top: 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.28);
    }}
    .art-chart i {{
        display: block;
        flex: 1;
        background: linear-gradient(180deg, #F6B945, #E08E1B);
        border-radius: 4px 4px 0 0;
        transform-origin: bottom;
        animation: equaliserBar 2.8s ease-in-out infinite;
    }}
    .art-chart i:nth-child(1){{height:34%; animation-delay:0.0s}}
    .art-chart i:nth-child(2){{height:58%; animation-delay:0.2s}}
    .art-chart i:nth-child(3){{height:46%; animation-delay:0.4s}}
    .art-chart i:nth-child(4){{height:82%; animation-delay:0.6s}}
    .art-chart i:nth-child(5){{height:66%; animation-delay:0.8s}}
    .art-chart i:nth-child(6){{height:90%; animation-delay:1.0s}}
    .art-chart i:nth-child(7){{height:100%; animation-delay:1.2s}}
    .art-card-foot {{ color: #E4F5F2; font-size: 7.5px; letter-spacing: 0.12em; margin-top: 10px; }}
    .art-card-foot b {{ color: #F6B945; float: right; }}
    .hero-spark {{
        position: absolute;
        color: #F6B945;
        font-size: 1.55rem;
        animation: twinkleStar 3.2s ease-in-out infinite;
    }}
    .spark-a {{ right: 8px; top: 16px; }}
    .spark-b {{ left: 6px; bottom: 18px; animation-delay: 1.4s; }}

    /* ===================== REFERENCE BRACKET FEATURE CARDS ===================== */
    .why-wrap {{
        margin: 0.4rem 0 1.8rem;
        animation: fadeSlideUp 0.7s cubic-bezier(0.22, 1, 0.36, 1) 0.16s both;
    }}

    .why-header {{
        text-align: center;
        margin-bottom: 1.25rem;
    }}

    .why-title {{
        font-size: 1.45rem;
        font-weight: 800;
        color: {text_main};
        letter-spacing: -0.02em;
        margin: 0;
    }}

    .why-sub {{
        font-size: 0.86rem;
        color: {text_muted};
        margin-top: 4px;
    }}

    .why-grid {{
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 20px;
    }}

    .why-card {{
        position: relative;
        cursor: pointer;
        background: {surface_glass};
        backdrop-filter: blur(18px);
        -webkit-backdrop-filter: blur(18px);
        border: 1px solid {border_col};
        border-radius: 18px;
        padding: 1.45rem 1.4rem;
        box-shadow: {card_shadow};
        transition: transform 0.28s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.28s ease, border-color 0.28s ease;
    }}

    .why-card::before {{
        content: "";
        position: absolute;
        top: -1px;
        right: -1px;
        width: 58px;
        height: 46px;
        border-top: 2.5px solid #153937;
        border-right: 2.5px solid #153937;
        border-top-right-radius: 18px;
        pointer-events: none;
        transition: width 0.28s ease, height 0.28s ease, border-color 0.28s ease;
    }}

    .why-card::after {{
        content: "";
        position: absolute;
        bottom: -1px;
        left: -1px;
        width: 58px;
        height: 46px;
        border-bottom: 2.5px solid #153937;
        border-left: 2.5px solid #153937;
        border-bottom-left-radius: 18px;
        pointer-events: none;
        transition: width 0.28s ease, height 0.28s ease, border-color 0.28s ease;
    }}

    .why-card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 20px 42px rgba(21, 57, 55, 0.11);
        border-color: rgba(19, 122, 115, 0.32);
    }}

    .why-card:hover::before,
    .why-card:hover::after {{
        width: 78px;
        height: 60px;
        border-color: #F3A825;
    }}

    .why-icon-box {{
        width: 44px;
        height: 44px;
        border-radius: 12px;
        background: #153937;
        color: #FFFFFF !important;
        display: grid;
        place-items: center;
        font-size: 1.2rem;
        margin-bottom: 0.9rem;
        box-shadow: 0 8px 18px rgba(21, 57, 55, 0.18);
        transition: transform 0.28s ease, background 0.28s ease;
    }}

    .why-card:hover .why-icon-box {{
        transform: scale(1.07) rotate(-3deg);
        background: #137A73;
    }}

    .why-card h4 {{
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 1.02rem;
        font-weight: 700;
        color: {text_main};
        margin: 0 0 0.4rem;
    }}

    .why-card p {{
        font-size: 0.83rem;
        line-height: 1.58;
        color: {text_muted} !important;
        margin: 0 0 0.75rem;
    }}

    .why-link {{
        font-size: 0.78rem;
        font-weight: 700;
        color: #137A73 !important;
        display: inline-flex;
        align-items: center;
        gap: 5px;
    }}

    /* ===================== WORKFLOW RAIL & FORM GLASS CARDS ===================== */
    .workflow-rail {{
        display: flex;
        align-items: center;
        gap: 14px;
        background: {surface_glass};
        backdrop-filter: blur(18px);
        -webkit-backdrop-filter: blur(18px);
        border: 1px solid {border_col};
        box-shadow: {card_shadow};
        border-radius: 18px;
        padding: 15px 22px;
        margin: 0 0 1.4rem;
        animation: fadeSlideUp 0.75s cubic-bezier(0.22, 1, 0.36, 1) 0.22s both;
    }}

    .workflow-step {{
        cursor: pointer;
        display: grid;
        grid-template-columns: 36px auto;
        column-gap: 11px;
        align-items: center;
        transition: transform 0.2s ease;
    }}

    .workflow-step:hover {{
        transform: translateX(3px);
    }}

    .workflow-step span {{
        grid-row: span 2;
        width: 36px;
        height: 36px;
        border-radius: 11px;
        background: linear-gradient(135deg, #153937, #137A73);
        color: #F3A825 !important;
        display: grid;
        place-items: center;
        font-size: 0.76rem;
        font-weight: 800;
        box-shadow: 0 5px 14px rgba(21, 57, 55, 0.2);
    }}

    .workflow-step b {{ color: {text_main}; font-size: 0.88rem; }}
    .workflow-step small {{ color: {text_muted}; font-size: 0.73rem; }}
    .workflow-connector {{ flex: 1; height: 1px; background: {border_col}; min-width: 16px; }}

    .sec {{
        background: {surface_glass};
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid {border_col};
        border-left: 4px solid #F3A825 !important;
        border-radius: 14px;
        padding: 12px 18px !important;
        margin: 1.9rem 0 0.95rem !important;
        color: {text_main} !important;
        font-size: 1.06rem !important;
        font-weight: 700 !important;
        box-shadow: {card_shadow};
        transition: transform 0.22s ease, box-shadow 0.22s ease;
    }}

    .sec:hover {{
        transform: translateX(3px);
        box-shadow: 0 16px 36px rgba(20, 53, 51, 0.08);
    }}

    /* Glass Tabs */
    .stTabs [data-baseweb="tab-list"] {{
        background: {surface_glass} !important;
        backdrop-filter: blur(18px) !important;
        border: 1px solid {border_col} !important;
        border-radius: 16px !important;
        padding: 6px !important;
        gap: 8px !important;
        box-shadow: {card_shadow};
        flex-wrap: wrap !important;
    }}

    .stTabs [data-baseweb="tab"] {{
        border-radius: 11px !important;
        padding: 10px 22px !important;
        font-weight: 700 !important;
        color: {text_muted} !important;
        transition: all 0.22s ease !important;
    }}

    .stTabs [aria-selected="true"] {{
        background: linear-gradient(135deg, #153937, #137A73) !important;
        color: #FFFFFF !important;
        box-shadow: 0 6px 18px rgba(21, 57, 55, 0.24) !important;
    }}

    .stTabs [data-baseweb="tab-highlight"] {{
        display: none !important;
    }}

    /* Frosted Inputs with Smooth Focus Transitions */
    .stTextInput input,
    .stTextArea textarea,
    .stDateInput input,
    [data-baseweb="select"] > div {{
        background: {input_bg} !important;
        backdrop-filter: blur(12px) !important;
        color: {text_main} !important;
        border: 1px solid {border_col} !important;
        border-radius: 12px !important;
        transition: border-color 0.22s ease, box-shadow 0.22s ease, transform 0.18s ease !important;
    }}

    .stTextInput input:focus,
    .stTextArea textarea:focus {{
        border-color: #137A73 !important;
        box-shadow: 0 0 0 3.5px rgba(19, 122, 115, 0.15) !important;
        transform: translateY(-1px);
    }}

    .stApp label {{
        font-weight: 600 !important;
        font-size: 0.88rem !important;
    }}

    /* Animated Shimmer CTA Button & Glass Action Buttons */
    .stButton button, .stDownloadButton button {{
        position: relative;
        overflow: hidden;
        border-radius: 12px !important;
        min-height: 44px;
        font-weight: 700 !important;
        transition: all 0.24s cubic-bezier(0.22, 1, 0.36, 1) !important;
    }}

    .stButton button[kind="primary"] {{
        background: linear-gradient(135deg, #F3A825 0%, #E09112 100%) !important;
        border: 1px solid rgba(255, 255, 255, 0.4) !important;
        color: #143533 !important;
        box-shadow: 0 8px 22px rgba(243, 168, 37, 0.32) !important;
    }}

    .stButton button[kind="primary"]::after {{
        content: "";
        position: absolute;
        top: 0;
        left: -120%;
        width: 60%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.45), transparent);
        transform: skewX(-22deg);
        animation: shimmerSweep 4s infinite;
    }}

    .stButton button[kind="primary"]:hover {{
        transform: translateY(-2px);
        box-shadow: 0 12px 28px rgba(243, 168, 37, 0.45) !important;
    }}

    .stButton button:not([kind="primary"]),
    .stDownloadButton button {{
        background: {surface_glass} !important;
        backdrop-filter: blur(14px) !important;
        color: {text_main} !important;
        border: 1px solid {border_col} !important;
        box-shadow: {card_shadow};
    }}

    .stButton button:not([kind="primary"]):hover,
    .stDownloadButton button:hover {{
        border-color: #137A73 !important;
        transform: translateY(-2px);
        box-shadow: 0 12px 26px rgba(20, 53, 51, 0.1);
    }}

    /* Metrics, Expanders & File Uploader */
    div[data-testid="stMetric"] {{
        background: {surface_glass} !important;
        backdrop-filter: blur(16px) !important;
        border: 1px solid {border_col} !important;
        border-radius: 16px !important;
        padding: 1rem 1.15rem !important;
        box-shadow: {card_shadow};
        transition: transform 0.25s ease, box-shadow 0.25s ease;
    }}

    div[data-testid="stMetric"]:hover {{
        transform: translateY(-3px);
        box-shadow: 0 16px 34px rgba(20, 53, 51, 0.09);
    }}

    div[data-testid="stMetricLabel"] p {{
        color: {text_muted} !important;
        font-weight: 600 !important;
    }}

    div[data-testid="stMetricValue"] {{
        color: #137A73 !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-weight: 800 !important;
    }}

    [data-testid="stExpander"] {{
        background: {surface_glass} !important;
        backdrop-filter: blur(16px) !important;
        border: 1px solid {border_col} !important;
        border-radius: 14px !important;
        overflow: hidden;
        box-shadow: {card_shadow};
    }}

    [data-testid="stFileUploader"] {{
        background: {surface_glass} !important;
        backdrop-filter: blur(14px) !important;
        border: 1.5px dashed #137A73 !important;
        border-radius: 16px !important;
        padding: 12px !important;
        transition: border-color 0.25s ease, background 0.25s ease;
    }}

    [data-testid="stFileUploader"]:hover {{
        border-color: #F3A825 !important;
    }}

    [data-testid="stDataFrame"],
    [data-testid="stAlert"] {{
        background: {surface_glass} !important;
        backdrop-filter: blur(14px) !important;
        border: 1px solid {border_col} !important;
        border-radius: 14px !important;
    }}

    .stProgress > div > div > div {{
        background: linear-gradient(90deg, #137A73, #F3A825) !important;
    }}

    /* ===================== REALISTIC A4 PAPER PREVIEW ===================== */
    .a4-sheet {{
        background-color: #ffffff !important;
        color: #1a202c !important;
        max-width: 830px;
        margin: 1.2rem auto;
        padding: 52px 60px;
        border-radius: 6px;
        box-shadow: 0 22px 58px rgba(20, 53, 51, 0.16);
        border: 1px solid #cbd5e1;
        font-family: "Times New Roman", Times, serif !important;
        line-height: 1.65;
        animation: fadeSlideUp 0.55s ease both;
    }}
    .a4-sheet * {{
        color: #1a202c !important;
        font-family: "Times New Roman", Times, serif !important;
    }}
    .a4-logo {{
        max-height: 125px;
        width: auto;
        margin-bottom: 10px;
    }}
    .a4-header {{
        text-align: center;
        border-bottom: 2px solid #153937;
        padding-bottom: 16px;
        margin-bottom: 22px;
    }}
    .a4-dept {{
        font-size: 1.05rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        color: #153937 !important;
        text-transform: uppercase;
        margin-bottom: 4px;
    }}
    .a4-header h1 {{
        font-size: 1.6rem;
        color: #153937 !important;
        margin: 4px 0 12px 0;
        font-weight: 700;
    }}
    .a4-student-grid {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 10px;
        font-size: 0.9rem;
        text-align: left;
    }}
    .a4-student-grid td {{
        border: 1px solid #cbd5e1;
        padding: 6px 10px;
    }}
    .a4-student-grid td.lbl {{
        background-color: #eef5f4 !important;
        font-weight: 700;
        color: #153937 !important;
        width: 20%;
    }}
    .a4-section-title {{
        font-size: 1.12rem;
        font-weight: 700;
        color: #153937 !important;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 4px;
        margin: 22px 0 10px 0;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }}
    .a4-sub-title {{
        font-size: 1.0rem;
        font-weight: 700;
        color: #1e293b !important;
        margin: 14px 0 6px 0;
    }}
    .a4-body p {{
        margin: 0 0 10px 0;
        text-align: justify;
        font-size: 0.98rem;
    }}
    .a4-body ul, .a4-body ol {{
        margin: 6px 0 12px 24px;
        padding: 0;
        font-size: 0.96rem;
    }}
    .a4-body li {{
        margin-bottom: 5px;
    }}
    .a4-table {{
        width: 100%;
        border-collapse: collapse;
        margin: 14px 0;
        font-size: 0.9rem;
    }}
    .a4-table th {{
        background-color: #153937 !important;
        color: #ffffff !important;
        font-weight: 600;
        text-align: left;
        padding: 8px 10px;
        border: 1px solid #153937;
    }}
    .a4-table td {{
        padding: 7px 10px;
        border: 1px solid #cbd5e1;
    }}
    .a4-table tr:nth-child(even) td {{
        background-color: #f8fafc !important;
    }}
    .a4-figure {{
        text-align: center;
        margin: 18px 0;
        padding: 10px;
        border: 1px solid #e2e8f0;
        background: #fcfcfd !important;
    }}
    .a4-figure img {{
        max-width: 100%;
        height: auto;
    }}
    .a4-caption {{
        font-size: 0.88rem;
        color: #475569 !important;
        font-style: italic;
        margin-top: 6px;
    }}
    .a4-eq {{
        background: #f8fafc !important;
        border-left: 3px solid #153937;
        padding: 10px 14px;
        margin: 10px 0;
        text-align: center;
        overflow-x: auto;
        font-size: 1.08rem;
    }}

    /* ===================== INSTITUTIONAL CORPORATE FOOTER ===================== */
    .corp-footer {{
        margin-top: 3.5rem;
        border-radius: 26px 26px 18px 18px;
        background:
            radial-gradient(circle at 85% 20%, rgba(243, 168, 37, 0.14), transparent 36%),
            linear-gradient(135deg, #133331 0%, #194441 60%, #124C48 100%);
        color: #E6F4F2 !important;
        padding: 2.6rem 2.8rem 1.5rem;
        border: 1px solid rgba(255, 255, 255, 0.14);
        box-shadow: 0 20px 46px rgba(19, 51, 49, 0.16);
    }}

    .footer-grid {{
        display: grid;
        grid-template-columns: 1.7fr 1fr 1fr 1.1fr;
        gap: 2.2rem;
        padding-bottom: 2rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.14);
    }}

    .footer-brand {{
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 1.25rem;
        font-weight: 800;
        color: #FFFFFF !important;
        margin-bottom: 0.75rem;
    }}

    .footer-desc {{
        font-size: 0.84rem;
        line-height: 1.68;
        color: #B9D8D3 !important;
        margin: 0 0 1.1rem;
        max-width: 340px;
    }}

    .footer-badges {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
    }}

    .footer-badges span {{
        font-size: 0.7rem;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.16);
        color: #F6B945 !important;
    }}

    .footer-col h5 {{
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 0.88rem;
        font-weight: 700;
        color: #FFFFFF !important;
        margin: 0 0 0.85rem;
        letter-spacing: 0.02em;
    }}

    .footer-col ul {{
        list-style: none;
        padding: 0;
        margin: 0;
    }}

    .footer-col li {{
        margin-bottom: 0.52rem;
        font-size: 0.82rem;
        color: #B9D8D3 !important;
        transition: color 0.2s ease, transform 0.2s ease;
    }}

    .footer-col li:hover {{
        color: #F6B945 !important;
        transform: translateX(3px);
    }}

    .footer-link-btn {{
        background: none;
        border: none;
        padding: 0;
        cursor: pointer;
        color: inherit;
        font: inherit;
        text-align: left;
    }}

    .footer-bottom {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 1rem;
        padding-top: 1.25rem;
        font-size: 0.76rem;
        color: #9EC4BE !important;
    }}

    .footer-bottom-links {{
        display: flex;
        flex-wrap: wrap;
        gap: 18px;
    }}

    .footer-bottom-links button {{
        background: none;
        border: none;
        padding: 0;
        cursor: pointer;
        font: inherit;
        color: #B9D8D3 !important;
        transition: color 0.2s ease;
    }}

    .footer-bottom-links button:hover {{
        color: #F6B945 !important;
    }}

    /* ===================== TABLET & MOBILE BREAKPOINTS ===================== */
    @media (max-width: 960px) {{
        .why-grid {{ grid-template-columns: 1fr; }}
        .footer-grid {{ grid-template-columns: 1fr 1fr; }}
        .corp-nav-links {{ display: none; }}
        .hero {{ padding: 2rem 1.5rem; border-radius: 20px 20px 44px 20px; }}
        .hero-art {{ display: none; }}
    }}

    @media (max-width: 640px) {{
        .block-container {{ padding: 2.6rem 0.9rem 2rem !important; }}
        .corp-navbar {{ padding: 0.75rem 1rem; }}
        .corp-status-pill {{ display: none; }}
        .hero-stats-row {{ flex-wrap: wrap; gap: 16px; }}
        .hero-stat-divider {{ display: none; }}
        .workflow-rail {{ flex-direction: column; align-items: flex-start; gap: 10px; }}
        .workflow-connector {{ display: none; }}
        .footer-grid {{ grid-template-columns: 1fr; gap: 1.5rem; }}
        .corp-footer {{ padding: 1.8rem 1.35rem 1.2rem; }}
        .a4-sheet {{ padding: 22px 16px !important; }}
        .a4-student-grid {{ font-size: 0.78rem; }}
    }}
    </style>

    <!-- Sticky Institutional Top Navigation Bar -->
    <nav id="top-hero" class="corp-navbar">
        <div class="corp-nav-brand" data-nav-target="top-hero">
            <div class="corp-brand-badge">🧪</div>
            <span>Lab Report Generator</span>
        </div>
        <div class="corp-nav-links">
            <button type="button" class="nav-action-link" data-nav-target="capabilities">Capabilities</button>
            <button type="button" class="nav-action-link" data-nav-target="workflow">Workflow</button>
            <button type="button" class="nav-action-link" data-nav-target="sec-experiment" data-nav-tab="0">Report Builder</button>
            <button type="button" class="nav-action-link" data-nav-target="sec-viva" data-nav-tab="1">Viva Examiner</button>
            <button type="button" class="nav-action-link" data-nav-target="institutional-footer">Compliance & Support</button>
        </div>
        <div class="corp-nav-actions">
            <span class="corp-status-pill"><span class="corp-status-dot"></span> Academic Engine Ready</span>
            <button type="button" class="corp-nav-cta" data-nav-target="sec-experiment" data-nav-tab="0">Start Report →</button>
        </div>
    </nav>

    <!-- Hero Section -->
    <div class="hero">
        <div class="hero-kicker"><span class="hero-dot"></span> INSTITUTIONAL ACADEMIC DOCUMENTATION PLATFORM</div>
        <div class="hero-layout">
            <div class="hero-copy">
                <h1>Lab Report Generator.<br><em>Engineered for Precision.</em></h1>
                <p>Transform experimental readings into publication-grade, department-aligned engineering lab reports — complete with formula-grounded calculations, automated plots, and interactive oral viva assessment.</p>
                <div class="hero-pills">
                    <button type="button" class="hero-pill-btn" data-nav-target="sec-formulas" data-nav-tab="0">✦ Formula-Grounded AI</button>
                    <button type="button" class="hero-pill-btn" data-nav-target="sec-readings" data-nav-tab="0">▥ Automated Plotting</button>
                    <button type="button" class="hero-pill-btn" data-nav-target="sec-viva" data-nav-tab="1">◎ Oral Viva Examiner</button>
                </div>
                <div class="hero-stats-row">
                    <div class="hero-stat-item">
                        <strong>15+</strong>
                        <small>Structured Report Sections</small>
                    </div>
                    <div class="hero-stat-divider"></div>
                    <div class="hero-stat-item">
                        <strong>100%</strong>
                        <small>User-Formula Compliance</small>
                    </div>
                    <div class="hero-stat-divider"></div>
                    <div class="hero-stat-item">
                        <strong>PDF & DOCX</strong>
                        <small>Instant A4 Institutional Export</small>
                    </div>
                </div>
            </div>
            <div class="hero-art" aria-hidden="true">
                <div class="hero-orbit orbit-one"></div>
                <div class="hero-orbit orbit-two"></div>
                <div class="hero-art-card">
                    <div class="art-card-top"><span></span><span></span><span></span></div>
                    <div class="art-icon">⌁</div>
                    <div class="art-line long"></div>
                    <div class="art-line"></div>
                    <div class="art-chart"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div>
                    <div class="art-card-foot">A4 REPORT <b>VERIFIED</b></div>
                </div>
                <div class="hero-spark spark-a">✦</div>
                <div class="hero-spark spark-b">✧</div>
            </div>
        </div>
    </div>

    <!-- Institutional Value Pillars (Clickable Bracket Cards) -->
    <section id="capabilities" class="why-wrap">
        <div class="why-header">
            <h2 class="why-title">Built for Engineering Rigor & Academic Standards</h2>
            <div class="why-sub">Click any pillar below to jump directly to its interactive module</div>
        </div>
        <div class="why-grid">
            <div class="why-card" data-nav-target="sec-formulas" data-nav-tab="0">
                <div class="why-icon-box">📐</div>
                <h4>Strict Formula Governance</h4>
                <p>Every step-by-step calculation and tabular derivation executes exclusively using your declared LaTeX equations without hallucinated constants.</p>
                <span class="why-link">Jump to Formula Modeling →</span>
            </div>
            <div class="why-card" data-nav-target="sec-readings" data-nav-tab="0">
                <div class="why-icon-box">📊</div>
                <h4>Automated Data & Plot Synthesis</h4>
                <p>Upload raw CSV or Excel laboratory logs to compute statistical descriptors, efficiency metrics, and high-resolution embedded figures automatically.</p>
                <span class="why-link">Jump to Readings & Graphs →</span>
            </div>
            <div class="why-card" data-nav-target="sec-viva" data-nav-tab="1">
                <div class="why-icon-box">🎓</div>
                <h4>A4 Typeset & Viva Readiness</h4>
                <p>Export university-formatted Times New Roman PDF/DOCX dossiers with cover metadata and prepare with a department-specific AI oral examiner.</p>
                <span class="why-link">Launch Viva Examiner →</span>
            </div>
        </div>
    </section>
    """, unsafe_allow_html=True)


_apply_corporate_glass_motion(st.session_state["ui_theme"])


def load_sample():
    choice = st.session_state["sample_choice"]
    s = SAMPLES[choice]
    for k in ["department", "experiment", "aim", "theory", "apparatus", "procedure"]:
        st.session_state[k] = s[k]
    extras = next((v for key, v in _SAMPLE_EXTRAS.items() if key.lower() in choice.lower()), {})
    for k in ["objectives", "problem_statement", "introduction", "assumptions", "math_modeling"]:
        st.session_state[k] = extras.get(k, "")
    st.session_state["readings_text"] = sample_csv(choice)
    st.session_state.pop("report", None)


def _save_uploaded_asset(uploaded_file, prefix: str) -> str | None:
    if uploaded_file is None:
        return None
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ext = os.path.splitext(uploaded_file.name)[1].lower() or ".png"
    out_path = os.path.join(OUTPUT_DIR, f"{prefix}{ext}")
    with open(out_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return out_path


def _img_to_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _format_text_html(text: str) -> str:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        return ""
    if all(ln.startswith("- ") for ln in lines):
        items = "".join(f"<li>{html.escape(ln[2:])}</li>" for ln in lines)
        return f"<ul>{items}</ul>"
    if all(ln[0].isdigit() and ". " in ln[:4] for ln in lines):
        items = "".join(f"<li>{html.escape(ln.split('. ', 1)[1])}</li>" for ln in lines)
        return f"<ol>{items}</ol>"
    html_parts = []
    for ln in lines:
        if ln.startswith("Step "):
            html_parts.append(
                f"<p style='margin:10px 0 2px 12px;font-weight:700;'>{html.escape(ln)}</p>"
            )
        else:
            html_parts.append(f"<p style='margin:0 0 8px 0;'>{html.escape(ln)}</p>")
    return "".join(html_parts)


def _format_latex_html(text: str) -> str:
    """Render $$...$$ blocks in clean typeset mathematical form via KaTeX in A4 preview."""
    normalized = _normalize_latex_blocks(text)
    parts = re.split(r"(\$\$.*?\$\$)", normalized, flags=re.DOTALL)
    out = [
        '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">',
        '<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>',
        '<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js" '
        'onload="renderMathInElement(document.body);"></script>',
    ]
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if p.startswith("$$") and p.endswith("$$"):
            out.append(f"<div class='a4-eq'>{html.escape(p)}</div>")
        else:
            out.append(_format_text_html(p))
    return "".join(out)


def render_a4_preview(rep: dict) -> str:
    meta = rep["meta"]
    logo_html = ""
    if meta.get("logo_path") and os.path.exists(meta["logo_path"]):
        logo_html = f"<img class='a4-logo' src='data:image/png;base64,{_img_to_b64(meta['logo_path'])}' alt='Logo'/><br>"
    student_table = f"""
    <table class='a4-student-grid'>
        <tr>
            <td class='lbl'>Student Name</td><td>{html.escape(meta['student'])}</td>
            <td class='lbl'>PRN</td><td>{html.escape(meta['prn'])}</td>
        </tr>
        <tr>
            <td class='lbl'>Year of Study</td><td>{html.escape(meta['year'])}</td>
            <td class='lbl'>Roll Number</td><td>{html.escape(meta['roll_no'])}</td>
        </tr>
        <tr>
            <td class='lbl'>Division</td><td>{html.escape(meta['division'])}</td>
            <td class='lbl'>Batch</td><td>{html.escape(meta['batch'])}</td>
        </tr>
        <tr>
            <td class='lbl'>Date</td><td>{html.escape(meta['date'])}</td>
            <td class='lbl'>Department</td><td>{html.escape(meta['department'])} Engineering</td>
        </tr>
    </table>
    """
    parts = [
        "<div class='a4-sheet'>",
        "<div class='a4-header'>",
        logo_html,
        f"<div class='a4-dept'>Department of {html.escape(meta['department'])} Engineering</div>",
        f"<h1>{html.escape(meta['experiment'])}</h1>",
        student_table,
        "</div>",
        "<div class='a4-body'>",
    ]
    for n, (heading, blocks) in enumerate(build_blocks(rep), 1):
        parts.append(f"<div class='a4-section-title'>{n}. {html.escape(heading)}</div>")
        for blk in blocks:
            kind = blk[0]
            if kind == "text":
                parts.append(_format_text_html(blk[1]))
            elif kind == "latex":
                parts.append(_format_latex_html(blk[1]))
            elif kind == "sub":
                parts.append(f"<div class='a4-sub-title'>{html.escape(blk[1])}</div>")
            elif kind == "table":
                headers = "".join(f"<th>{html.escape(str(c))}</th>" for c in blk[1])
                rows = "".join(
                    "<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in row) + "</tr>"
                    for row in blk[2]
                )
                parts.append(f"<table class='a4-table'><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table>")
            elif kind == "image":
                img_path, caption = blk[1], blk[2]
                if os.path.exists(img_path):
                    parts.append(
                        f"<div class='a4-figure'>"
                        f"<img src='data:image/png;base64,{_img_to_b64(img_path)}' alt='{html.escape(caption)}'/>"
                        f"<div class='a4-caption'>{html.escape(caption)}</div>"
                        f"</div>"
                    )
    parts.append("</div></div>")
    return "".join(parts)


# ------------------------------------------------------------- sidebar -----
with st.sidebar:
    st.markdown("## 🧪 Lab Report Generator")
    st.caption("Institutional Documentation Suite")

    st.markdown("### Surface Theme")
    selected_theme = st.radio(
        "Theme Mode",
        ["Light", "Dark"],
        index=0 if st.session_state["ui_theme"] == "Light" else 1,
        horizontal=True,
        label_visibility="collapsed",
    )
    if selected_theme != st.session_state["ui_theme"]:
        st.session_state["ui_theme"] = selected_theme
        st.rerun()

    st.divider()
    st.markdown("### 🏛️ Institution & Department")
    st.selectbox("Department *", DEPARTMENTS, key="department")
    logo_file = st.file_uploader(
        "University / College Logo (Page 1)",
        type=["png", "jpg", "jpeg"],
        key="logo_upload",
    )

    st.divider()
    st.markdown("### 🎓 Student Metadata (Mandatory)")
    st.text_input("Student Full Name *", key="student", placeholder="e.g. Suyash Dixit")
    st.text_input("Permanent Registration Number (PRN) *", key="prn", placeholder="e.g. 22110458")
    c_yr, c_roll = st.columns(2)
    c_yr.selectbox("Year *", ["FE (1st Year)", "SE (2nd Year)", "TE (3rd Year)", "BE (4th Year)"], key="year")
    c_roll.text_input("Roll Number *", key="roll_no", placeholder="e.g. 42")
    c_div, c_bat = st.columns(2)
    c_div.text_input("Division *", key="division", placeholder="e.g. A")
    c_bat.text_input("Batch *", key="batch", placeholder="e.g. B2")
    st.date_input("Experiment Date *", key="exp_date")

    st.divider()
    st.markdown("### 📂 Preset Templates")
    st.selectbox("Sample experiment", list(SAMPLES), key="sample_choice")
    st.button("Load sample experiment", on_click=load_sample, use_container_width=True)


def collect_inputs():
    df = load_dataframe(st.session_state.get("upload"), st.session_state["readings_text"])
    inputs = {
        k: st.session_state[k]
        for k in [
            "department", "experiment", "aim", "apparatus", "objectives",
            "problem_statement", "introduction", "assumptions", "theory",
            "math_modeling", "procedure",
        ]
    }
    stats = compute_stats(df) if df is not None else {"columns": {}, "efficiency": None, "n_rows": 0}
    inputs["readings_text"] = df.head(60).to_string(index=False) if df is not None else ""
    return inputs, df, stats


def get_engine():
    try:
        return AIEngine()
    except Exception as exc:
        st.error(f"AI Engine initialisation failed: {exc}")
        return None


def _validate_required_fields() -> list[str]:
    required = {
        "Experiment Title": st.session_state["experiment"],
        "Aim": st.session_state["aim"],
        "Objectives": st.session_state["objectives"],
        "Problem Statement / Description": st.session_state["problem_statement"],
        "Introduction": st.session_state["introduction"],
        "Assumptions / Specifications": st.session_state["assumptions"],
        "Theory": st.session_state["theory"],
        "Mathematical Modeling (Formulas/Equations)": st.session_state["math_modeling"],
        "Procedure": st.session_state["procedure"],
        "Student Name": st.session_state["student"],
        "PRN": st.session_state["prn"],
        "Year of Studying": st.session_state["year"],
        "Roll Number": st.session_state["roll_no"],
        "Division": st.session_state["division"],
        "Batch": st.session_state["batch"],
    }
    return [label for label, val in required.items() if not str(val).strip()]


st.markdown("""
<div id="workflow" class="workflow-rail">
  <div class="workflow-step" data-nav-target="sec-experiment" data-nav-tab="0"><span>01</span><b>Define</b><small>Experiment & methodology</small></div>
  <div class="workflow-connector"></div>
  <div class="workflow-step" data-nav-target="sec-readings" data-nav-tab="0"><span>02</span><b>Analyze</b><small>Readings & data insights</small></div>
  <div class="workflow-connector"></div>
  <div class="workflow-step" data-nav-target="sec-generate" data-nav-tab="0"><span>03</span><b>Generate</b><small>A4 report & downloadable files</small></div>
</div>
""", unsafe_allow_html=True)

tab_report, tab_viva = st.tabs(["✦  Build Your Lab Report", "◎  Viva Examination Practice"])

# =============================================================== REPORT ====
with tab_report:
    st.markdown('<div id="sec-experiment" class="sec">1 · Experiment Information & Student Base Content</div>', unsafe_allow_html=True)
    st.caption("Provide the base content for each section below. AI refines technical phrasing, aligns terminology with your chosen department, and computes results strictly using your formulas.")

    st.text_input(
        "Experiment Title *",
        key="experiment",
        placeholder="e.g. Verification of Ohm's Law",
    )

    c1, c2 = st.columns(2)
    c1.text_area("Aim *", key="aim", height=110, placeholder="State the primary goal of the experiment...")
    c2.text_area("Apparatus / Equipment / Setup (one item per line)", key="apparatus", height=110)

    setup_img_file = st.file_uploader(
        "Apparatus / Equipment / Setup Image (optional - included under Setup section)",
        type=["png", "jpg", "jpeg"],
        key="setup_img_upload",
    )

    c3, c4 = st.columns(2)
    c3.text_area(
        "Objectives *",
        key="objectives",
        height=120,
        placeholder="- To determine...\n- To verify...",
    )
    c4.text_area(
        "Problem Statement / Description *",
        key="problem_statement",
        height=120,
        placeholder="Describe the engineering problem or physical behavior being investigated...",
    )

    c5, c6 = st.columns(2)
    c5.text_area(
        "Introduction *",
        key="introduction",
        height=125,
        placeholder="Provide background context on the system/phenomenon...",
    )
    c6.text_area(
        "Assumptions / Specifications *",
        key="assumptions",
        height=125,
        placeholder="- Ambient temperature constant at 27 °C\n- Steady-state flow assumed...",
    )

    c7, c8 = st.columns(2)
    c7.text_area(
        "Theory *",
        key="theory",
        height=145,
        placeholder="Enter the governing laws and theoretical explanation...",
    )
    c8.text_area(
        "Procedure *",
        key="procedure",
        height=145,
        placeholder="Describe the step-by-step experimental procedure performed...",
    )

    st.markdown('<div id="sec-formulas"></div>', unsafe_allow_html=True)
    st.text_area(
        "Mathematical Modeling — Formulas / Equations (Enter in LaTeX format) *",
        key="math_modeling",
        height=135,
        placeholder="Enter equations in LaTeX (e.g. $$R = \\frac{V}{I}$$) and variable definitions. AI will use ONLY these formulas for Calculations.",
    )

    if st.session_state["math_modeling"].strip():
        with st.expander("Preview Rendered Mathematical Equations", expanded=True):
            for raw_ln in st.session_state["math_modeling"].splitlines():
                ln = raw_ln.strip()
                if ln.startswith("$$") and ln.endswith("$$"):
                    st.latex(ln[2:-2].strip())
                elif ln.startswith("$") and ln.endswith("$") and len(ln) > 2:
                    st.latex(ln[1:-1].strip())
                elif "=" in ln and ("\\" in ln or "_" in ln or "^" in ln) and not ln.startswith("- "):
                    st.latex(ln)

    st.checkbox(
        "Include Error Analysis section in the report (Optional - computed by AI)",
        key="include_error_analysis",
    )

    st.markdown('<div id="sec-readings" class="sec">2 · Experimental Readings & Data</div>', unsafe_allow_html=True)
    u1, u2 = st.columns(2)
    u1.file_uploader("Upload Excel / CSV (first column = X-axis)", type=["csv", "xlsx", "xls"], key="upload")
    u2.text_area("…or paste CSV readings (header row first)", key="readings_text", height=150)

    try:
        _inputs, _df, _stats = collect_inputs()
        if _df is not None:
            with st.expander(f"Data preview · {len(_df)} rows", expanded=False):
                st.dataframe(_df, use_container_width=True)
            if _stats["columns"]:
                cols = st.columns(min(4, len(_stats["columns"])))
                for col, (name, v) in zip(cols, list(_stats["columns"].items())[:4]):
                    col.metric(f"{name} (mean)", f"{v['mean']:.4g}", f"σ = {v['std']:.3g}", delta_color="off")
                if _stats["efficiency"]:
                    st.success(
                        f"Efficiency detected ({_stats['efficiency']['method']}): "
                        f"mean {_stats['efficiency']['mean']:.1f} % · max {_stats['efficiency']['max']:.1f} %"
                    )
    except ValueError as exc:
        st.error(str(exc))

    st.markdown('<div id="sec-generate" class="sec">3 · Generate Report</div>', unsafe_allow_html=True)
    if st.button("🚀 Generate Report", type="primary"):
        missing = _validate_required_fields()
        if missing:
            st.error("Please fill in all mandatory fields before generating: **" + ", ".join(missing) + "**")
        else:
            engine = get_engine()
            if engine:
                try:
                    inputs, df, stats = collect_inputs()
                    logo_path = _save_uploaded_asset(logo_file, "college_logo")
                    setup_image_path = _save_uploaded_asset(setup_img_file, "apparatus_setup")
                    graphs = generate_graphs(df, OUTPUT_DIR) if df is not None else []
                    bar = st.progress(0.0, text="Starting…")
                    sections = engine.generate_report(
                        inputs,
                        stats,
                        graphs,
                        include_error_analysis=st.session_state["include_error_analysis"],
                        progress=lambda i, n, label: bar.progress(i / n, text=f"Writing: {label}…"),
                    )
                    viva = sections.pop("viva")
                    formatted_date = st.session_state["exp_date"].strftime("%d %B %Y")
                    report = {
                        "meta": {
                            **inputs,
                            "student": st.session_state["student"].strip(),
                            "prn": st.session_state["prn"].strip(),
                            "year": st.session_state["year"].strip(),
                            "roll_no": st.session_state["roll_no"].strip(),
                            "division": st.session_state["division"].strip(),
                            "batch": st.session_state["batch"].strip(),
                            "date": formatted_date,
                            "logo_path": logo_path,
                            "setup_image_path": setup_image_path,
                        },
                        "sections": sections,
                        "viva": viva,
                        "stats": stats,
                        "graphs": graphs,
                        "df": df,
                    }
                    base = safe_filename(inputs["experiment"])
                    report["pdf"] = build_pdf(report, os.path.join(OUTPUT_DIR, base + ".pdf"))
                    report["docx"] = build_docx(report, os.path.join(OUTPUT_DIR, base + ".docx"))
                    report["base"] = base
                    st.session_state["report"] = report
                    bar.empty()
                    st.success("Report generated successfully.")
                except Exception as exc:
                    st.error(f"Generation failed: {exc}")

    rep = st.session_state.get("report")
    if rep:
        st.markdown('<div class="sec">4 · Generated Report Preview</div>', unsafe_allow_html=True)
        preview_mode = st.radio(
            "Preview format",
            ["📄 Formatted Document Sheet (A4)", "📑 Actual Exported PDF Pages"],
            horizontal=True,
            label_visibility="collapsed",
        )
        if preview_mode == "📄 Formatted Document Sheet (A4)":
            st.markdown(render_a4_preview(rep), unsafe_allow_html=True)
        else:
            pdf_bytes = rep["pdf"] if isinstance(rep["pdf"], (bytes, bytearray)) else open(rep["pdf"], "rb").read()
            if hasattr(st, "pdf"):
                st.pdf(pdf_bytes, height=850)
            else:
                b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
                st.markdown(
                    f'<iframe src="data:application/pdf;base64,{b64_pdf}" '
                    f'width="100%" height="850px" style="border:1px solid #cbd5e1;border-radius:8px;"></iframe>',
                    unsafe_allow_html=True,
                )

        d1, d2 = st.columns(2)
        d1.markdown('<div class="sec">5 · Download PDF</div>', unsafe_allow_html=True)
        d1.download_button(
            "⬇️ Download PDF", rep["pdf"], f"{rep['base']}.pdf", "application/pdf", use_container_width=True
        )
        d2.markdown('<div class="sec">6 · Download DOCX</div>', unsafe_allow_html=True)
        d2.download_button(
            "⬇️ Download DOCX",
            rep["docx"],
            f"{rep['base']}.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )


# ================================================================= VIVA ====
def level_for(i, n):
    return "Beginner" if i < round(n * 0.4) else "Intermediate" if i < round(n * 0.8) else "Advanced"


with tab_viva:
    st.markdown('<div id="sec-viva" class="sec">Viva Mode - AI Oral Examination</div>', unsafe_allow_html=True)
    st.caption(
        "The examiner asks one department-specific question at a time, scores your answer for "
        "technical accuracy, confidence and completeness, and gives an overall mark out of 10."
    )
    viva = st.session_state.get("viva")
    if not viva:
        n_q = st.slider("Number of questions", 3, 10, 5)
        if st.button("▶️ Start Viva", type="primary"):
            if not st.session_state["experiment"].strip() or not st.session_state["aim"].strip():
                st.error("Fill in the experiment title and aim first (Build Your Lab Report tab).")
            else:
                engine = get_engine()
                if engine:
                    try:
                        inputs, _, stats = collect_inputs()
                        dept = inputs["department"]
                        ctx = engine.build_context(inputs, stats)
                        q = engine.viva_question(ctx, dept, [], level_for(0, n_q))
                        st.session_state["viva"] = {
                            "n": n_q,
                            "dept": dept,
                            "ctx": ctx,
                            "stage": "answering",
                            "items": [{"level": level_for(0, n_q), "q": q, "answer": "", "eval": None}],
                        }
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not start viva: {exc}")
    else:
        items, n, dept = viva["items"], viva["n"], viva["dept"]
        done = [it for it in items if it["eval"]]
        for it in done:
            ev = it["eval"]
            with st.expander(f"✅ {it['level']} · score {ev['score']:.1f}/10 - {it['q'][:80]}"):
                st.markdown(f"**Your answer:** {it['answer'] or '(blank)'}")
                st.markdown(f"**Feedback:** {ev['feedback']}")
                st.markdown(f"**Model answer:** {ev['model_answer']}")

        cur = items[-1]
        if viva["stage"] == "answering":
            st.progress((len(items) - 1) / n, text=f"Question {len(items)} of {n} · {cur['level']}")
            st.info(f"**Examiner:** {cur['q']}")
            ans = st.text_area("Your answer", key=f"viva_ans_{len(items)}", height=140)
            if st.button("Submit answer", type="primary"):
                engine = get_engine()
                if engine:
                    try:
                        cur["answer"] = ans
                        cur["eval"] = engine.viva_evaluate(viva["ctx"], dept, cur["q"], ans)
                        viva["stage"] = "feedback"
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Evaluation failed: {exc}")

        elif viva["stage"] == "feedback":
            ev = cur["eval"]
            st.info(f"**Examiner:** {cur['q']}")
            m = st.columns(4)
            m[0].metric("Technical accuracy", f"{ev['technical_accuracy']:.1f}/10")
            m[1].metric("Confidence", f"{ev['confidence']:.1f}/10")
            m[2].metric("Completeness", f"{ev['completeness']:.1f}/10")
            m[3].metric("Overall score", f"{ev['score']:.1f}/10")
            st.markdown(f"**Feedback:** {ev['feedback']}")
            st.markdown(f"**Model answer:** {ev['model_answer']}")
            last = len(items) >= n
            if st.button("Finish viva" if last else "Next question ➜", type="primary"):
                if last:
                    viva["stage"] = "done"
                    st.rerun()
                else:
                    engine = get_engine()
                    if engine:
                        try:
                            lvl = level_for(len(items), n)
                            q = engine.viva_question(viva["ctx"], dept, [i["q"] for i in items], lvl)
                            items.append({"level": lvl, "q": q, "answer": "", "eval": None})
                            viva["stage"] = "answering"
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not get next question: {exc}")
        else:
            avg = sum(i["eval"]["score"] for i in items) / len(items)
            st.success(f"Viva complete - average score **{avg:.1f}/10**")
            for key, label in (
                ("technical_accuracy", "Technical accuracy"),
                ("confidence", "Confidence"),
                ("completeness", "Completeness"),
            ):
                st.write(f"{label}: {sum(i['eval'][key] for i in items) / len(items):.1f}/10")
            st.write(
                "Verdict: "
                + (
                    "Excellent - exam ready."
                    if avg >= 8
                    else "Good - revise the weaker answers above."
                    if avg >= 6
                    else "Needs work - re-read the theory and retry."
                )
            )

        if st.button("🔄 Reset viva"):
            st.session_state.pop("viva")
            st.rerun()


# ===================================================== CORPORATE FOOTER ====
st.markdown("""
<footer id="institutional-footer" class="corp-footer">
    <div class="footer-grid">
        <div>
            <div class="footer-brand">
                <div class="corp-brand-badge">🧪</div>
                <span>Lab Report Generator</span>
            </div>
            <p class="footer-desc">
                An institutional academic documentation and oral assessment platform engineered for undergraduate and postgraduate engineering laboratories.
            </p>
            <div class="footer-badges">
                <span>A4 Print Standard</span>
                <span>LaTeX Equation Engine</span>
                <span>ISO Academic Format</span>
            </div>
        </div>
        <div class="footer-col">
            <h5>Platform Modules</h5>
            <ul>
                <li><button type="button" class="footer-link-btn" data-nav-target="sec-experiment" data-nav-tab="0">Structured Report Builder →</button></li>
                <li><button type="button" class="footer-link-btn" data-nav-target="sec-formulas" data-nav-tab="0">LaTeX Formula Parser →</button></li>
                <li><button type="button" class="footer-link-btn" data-nav-target="sec-readings" data-nav-tab="0">Automated Graph Synthesizer →</button></li>
                <li><button type="button" class="footer-link-btn" data-nav-target="sec-viva" data-nav-tab="1">AI Oral Viva Examiner →</button></li>
            </ul>
        </div>
        <div class="footer-col">
            <h5>Supported Disciplines</h5>
            <ul>
                <li><button type="button" class="footer-link-btn" data-nav-target="sec-experiment" data-nav-tab="0">Mechanical Engineering</button></li>
                <li><button type="button" class="footer-link-btn" data-nav-target="sec-experiment" data-nav-tab="0">Electrical & Electronics</button></li>
                <li><button type="button" class="footer-link-btn" data-nav-target="sec-experiment" data-nav-tab="0">Computer & AI Engineering</button></li>
                <li><button type="button" class="footer-link-btn" data-nav-target="sec-experiment" data-nav-tab="0">Civil & Chemical Labs</button></li>
            </ul>
        </div>
        <div class="footer-col">
            <h5>Academic Governance</h5>
            <ul>
                <li><button type="button" class="footer-link-btn" data-nav-target="sec-formulas" data-nav-tab="0">Formula-Grounded Outputs</button></li>
                <li><button type="button" class="footer-link-btn" data-nav-target="sec-generate" data-nav-tab="0">Times New Roman A4 Export</button></li>
                <li><button type="button" class="footer-link-btn" data-nav-target="sec-generate" data-nav-tab="0">PDF & Editable DOCX</button></li>
                <li><button type="button" class="footer-link-btn" data-nav-target="top-hero">Back to Top ↑</button></li>
            </ul>
        </div>
    </div>
    <div class="footer-bottom">
        <span>© 2026 Lab Report Generator · Institutional Engineering Documentation Suite. All rights reserved.</span>
        <div class="footer-bottom-links">
            <button type="button" data-nav-target="capabilities">Academic Integrity Policy</button>
            <button type="button" data-nav-target="workflow">Documentation Standards</button>
            <button type="button" data-nav-target="top-hero">System Status: Operational ↑</button>
        </div>
    </div>
</footer>
""", unsafe_allow_html=True)

# ----------------- JS Navigation & Smooth Scroll Bridge for Streamlit ------
components.html(
    """
    <script>
    (function() {
        const doc = window.parent.document;

        function navigateToTarget(targetId, tabIdx) {
            if (tabIdx !== null && tabIdx !== undefined && tabIdx !== "") {
                const tabs = doc.querySelectorAll('[data-baseweb="tab"]');
                const idx = parseInt(tabIdx, 10);
                if (tabs && tabs[idx]) {
                    tabs[idx].click();
                }
            }
            setTimeout(() => {
                const el = doc.getElementById(targetId);
                if (el) {
                    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }, 90);
        }

        function bindNavElements() {
            const triggers = doc.querySelectorAll('[data-nav-target]');
            triggers.forEach((el) => {
                if (el.dataset.navBound === "true") return;
                el.dataset.navBound = "true";
                el.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    const targetId = el.getAttribute('data-nav-target');
                    const tabIdx = el.getAttribute('data-nav-tab');
                    navigateToTarget(targetId, tabIdx);
                });
            });
        }

        bindNavElements();
        const observer = new MutationObserver(() => bindNavElements());
        observer.observe(doc.body, { childList: true, subtree: true });
    })();
    </script>
    """,
    height=0,
    width=0,
)