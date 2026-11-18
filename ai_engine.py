"""AI layer: Gemini engine, user-grounded refinement, formula-locked calculations + viva."""
import json
import os
import re
import time

import google.generativeai as genai

from templates.report_template import DEPARTMENT_FOCUS
from utils import clean_text, extract_json, stats_to_text

SYSTEM = (
    "You are a senior engineering professor grading undergraduate laboratory reports. "
    "Write in a precise, objective, past-tense academic engineering style tailored strictly "
    "to the specified engineering branch. Rules you never break:\n"
    "1. Preserve and build directly upon the student's supplied base text for Objectives, "
    "Problem Statement, Introduction, Assumptions/Specifications, Theory, Procedure, and "
    "Mathematical Modeling. Refine clarity, academic tone, and department terminology without "
    "contradicting or discarding what the student provided.\n"
    "2. Use ONLY the numbers, readings, and facts supplied in the experiment data; never "
    "fabricate measurements or instrument specs.\n"
    "3. Always quote numerical values with proper SI/engineering units.\n"
    "4. Be thorough, clear, and technically detailed, yet concise and factual—never use "
    "over-exaggerated praise, dramatic adjectives, or AI filler ('in today's world', 'delve', "
    "'crucial role', 'groundbreaking', 'testament').\n"
    "5. Except for 'mathematical_modeling' (which keeps LaTeX equations wrapped in $$ ... $$), "
    "write all other sections in clean plain text using '- ' for bullets and '1. ' for numbered "
    "steps (no markdown bold/headings)."
)

PROMPTS = {
    "objectives": (
        "Refine and structure the student's base Objectives into 4-5 clear, measurable OBJECTIVES "
        "as '- ' bullet points starting with action verbs ('To determine...', 'To verify...', "
        "'To analyze...', 'To evaluate...'). Keep the student's core objectives intact while "
        "aligning phrasing with {dept} Engineering. {dept_focus}"
    ),
    "problem_statement": (
        "Refine and expand the student's base Problem Statement / Description (110-150 words). "
        "Define the engineering problem or physical relationship investigated, why quantifying it "
        "matters in {dept} Engineering systems, and the operating range tested. Preserve all "
        "details provided by the student. {dept_focus}"
    ),
    "introduction": (
        "Refine and expand the student's base Introduction (150-200 words). Introduce the physical "
        "system/phenomenon, its context in {dept} Engineering, and how the independent and dependent "
        "variables interact, building directly on the student's input. {dept_focus}"
    ),
    "assumptions": (
        "Refine and structure the student's base Assumptions / Specifications into a clear bulleted "
        "list ('- ...') of 4-7 engineering assumptions, boundary conditions, and apparatus/material "
        "specifications (such as constant ambient temperature, steady-state flow, rated component "
        "values, or negligible stray losses). Preserve every specification supplied by the student."
    ),
    "theory": (
        "Refine and expand the student's base Theory (220-280 words). Explain the governing physical "
        "laws, underlying principles, and expected theoretical behavior using domain-specific "
        "{dept} Engineering terminology. Build directly upon the student's theory notes; if a note "
        "contains a technical inaccuracy, gently state the exact physical relation. {dept_focus}"
    ),
    "mathematical_modeling": (
        "Format and complete the MATHEMATICAL MODELING section based directly on the formulas/equations "
        "provided by the student. Every equation MUST be written in valid LaTeX display math format "
        "wrapped in $$ ... $$ on its own line (e.g., $$R = \\frac{{V}}{{I}}$$ or "
        "$$\\eta = \\frac{{\\rho g Q H}}{{P_{{in}}}} \\times 100\\%$$). "
        "Immediately below each equation, list and define every variable with its SI unit using "
        "'- symbol: description (unit)' bullets. Keep all student-provided equations intact and only "
        "clarify symbol definitions if missing."
    ),
    "procedure": (
        "Rewrite the student's base Procedure as a clean numbered list of 7-10 steps ('1. ...') in "
        "past tense, passive voice. Each step must describe one clear experimental action, naming "
        "the instrument used and parameter recorded. Do not invent steps the student did not describe."
    ),
    "calculations": (
        "Write the CALCULATIONS section (200-280 words) using ONLY the exact formulas supplied "
        "by the student in Mathematical Modeling, any fixed constants/rated specifications given "
        "in Assumptions / Specifications (e.g., density rho, gravity g, nominal resistance, rated "
        "speed/voltage), and the supplied readings/statistics. "
        "CRITICAL LAYOUT RULE — NEVER write a single dense paragraph. Format every calculation step "
        "strictly as two separate lines followed by a blank line:\n"
        "Line 1 (The Equation & Substitution on its own line): 'Step N — <Parameter>: <Formula> = <Substituted values with units> = <Final answer with units>'\n"
        "Line 2 (Brief theory/physical line on the next line): One concise sentence explaining what this calculated value represents.\n\n"
        "Include: (1) Sample calculation for the first/representative reading, (2) Sample calculation "
        "for the peak or final reading, (3) Mean/overall parameter calculation across all trials, "
        "and (4) Percentage error or deviation calculation against any nominal/rated specification "
        "supplied in Assumptions / Specifications. "
        "Use clean, normal human-readable mathematical notation (e.g., 'R₁ = 1.0 V / 0.0046 A = 217.39 Ω', "
        "'% Error = (|219.70 - 220| / 220) × 100% = 0.14%'). NEVER output raw LaTeX symbols like '$', '\\frac', or '\\Omega'."
    ),

    "error_analysis": (
        "Write the ERROR ANALYSIS section (160-220 words). Quantify experimental scatter using "
        "the supplied standard deviation, R^2 linearity, or deviation from theoretical/rated values. "
        "Then list 4-6 specific sources of experimental error in this {dept} Engineering setup as "
        "'- ' bullets formatted as '- <Source>: <Physical effect on measured values>; <Mitigation>'. "
        "{dept_focus}"
    ),
    "results": (
        "Write the RESULTS section (100-140 words). State the exact numerical findings determined "
        "from the experiment (mean, min, max, calculated parameters, and deviation) in a crisp, "
        "direct technical summary with SI units, followed by a short bulleted summary of key results."
    ),
    "conclusion": (
        "Write the CONCLUSION (100-140 words). Confirm whether the aim and objectives were met, "
        "restate the principal quantitative result with units, comment on the validity of the "
        "governing law within the tested range, and state one practical engineering takeaway "
        "for {dept} Engineering. No exaggeration. {dept_focus}"
    ),
}

ORDER = [
    "objectives",
    "problem_statement",
    "introduction",
    "assumptions",
    "theory",
    "mathematical_modeling",
    "procedure",
    "calculations",
    "error_analysis",
    "results",
    "conclusion",
]

LABELS = {
    "objectives": "Objectives",
    "problem_statement": "Problem Statement",
    "introduction": "Introduction",
    "assumptions": "Assumptions & Specifications",
    "theory": "Theory",
    "mathematical_modeling": "Mathematical Modeling",
    "procedure": "Procedure",
    "calculations": "Calculations",
    "error_analysis": "Error Analysis",
    "results": "Results",
    "conclusion": "Conclusion",
    "viva": "Viva Q&A",
}

VIVA_PROMPT = (
    "Create a viva-voce question bank for this {dept} Engineering experiment. Respond with "
    'JSON ONLY in this exact shape: {{"beginner": [{{"q": "...", "a": "..."}}], '
    '"intermediate": [...], "advanced": [...]}}. Counts: 8 beginner, 8 intermediate, 4 '
    "advanced. Questions and 2-4 sentence answers must use {dept} Engineering terminology "
    "and reference this specific experiment's setup, formulas, and data. {dept_focus}"
)

VIVA_Q_PROMPT = (
    "You are a {dept} Engineering external viva examiner. Ask exactly ONE new {level}-level "
    "oral exam question about this experiment. Do not repeat or paraphrase:\n{asked}\n\n"
    "Return only the question text."
)

VIVA_EVAL_PROMPT = (
    "You are a strict, fair {dept} Engineering viva examiner. Evaluate the student's answer.\n"
    "Question: {question}\nStudent answer: {answer}\n\n"
    'Return JSON ONLY: {{"technical_accuracy": <0-10>, "confidence": <0-10>, '
    '"completeness": <0-10>, "score": <0-10>, '
    '"feedback": "2-3 direct sentences on accuracy and missing points", '
    '"model_answer": "2-4 sentence technically exact answer"}}.'
)


def _normalize_latex_blocks(text: str) -> str:
    """Ensure standalone LaTeX equation lines are properly wrapped in $$ ... $$."""
    out_lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            out_lines.append("")
            continue
        if line.startswith("$$") and line.endswith("$$"):
            out_lines.append(line)
        elif line.startswith("$") and line.endswith("$") and len(line) > 2:
            out_lines.append(f"$${line[1:-1].strip()}$$")
        elif ("=" in line and ("\\" in line or "_" in line or "^" in line)) and not line.startswith("- "):
            out_lines.append(f"$${line}$$")
        else:
            out_lines.append(line)
    return "\n".join(out_lines)

_SUBSCRIPTS = str.maketrans("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎")
_SUPERSCRIPTS = str.maketrans("0123456789+-=()", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾")

_GREEK_AND_SYMBOLS = {
    r"\Omega": "Ω", r"\omega": "ω", r"\eta": "η", r"\rho": "ρ",
    r"\Delta": "Δ", r"\delta": "δ", r"\sigma": "σ", r"\Sigma": "Σ",
    r"\theta": "θ", r"\alpha": "α", r"\beta": "β", r"\gamma": "γ",
    r"\lambda": "λ", r"\mu": "μ", r"\pi": "π", r"\phi": "φ",
    r"\times": "×", r"\cdot": "·", r"\div": "÷", r"\pm": "±",
    r"\approx": "≈", r"\neq": "≠", r"\leq": "≤", r"\geq": "≥",
    r"\infty": "∞", r"\degree": "°", r"\%": "%",
}


def latex_to_readable(text: str) -> str:
    """Convert any LaTeX expressions ($...$, $$...$$, \\frac, \\Omega, subscripts) into clean readable math."""
    if not text:
        return ""

    s = text.replace("$$", "").replace("$", "")

    # Replace \text{...}, \mathrm{...}, \mathbf{...} with inner content
    s = re.sub(r"\\(?:text|mathrm|mathbf|mathit)\{([^{}]*)\}", r"\1", s)

    # Convert nested/simple \frac{a}{b} -> (a) / (b) (or a / b for simple tokens)
    def _repl_frac(m):
        num, den = m.group(1).strip(), m.group(2).strip()
        num_fmt = num if re.match(r"^[A-Za-z0-9_.]+$", num) else f"({num})"
        den_fmt = den if re.match(r"^[A-Za-z0-9_.]+$", den) else f"({den})"
        return f"{num_fmt} / {den_fmt}"

    for _ in range(3):
        s = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", _repl_frac, s)

    # Convert \sqrt{x} -> √(x)
    s = re.sub(r"\\sqrt\{([^{}]+)\}", r"√(\1)", s)

    # Replace Greek letters and math operators
    for cmd, uni in _GREEK_AND_SYMBOLS.items():
        s = s.replace(cmd, uni)

    # Convert numeric subscripts R_{1} or R_1 -> R₁, and keep text subscripts clean R_{exp} -> R_exp
    s = re.sub(r"_\{([0-9+-=()]+)\}", lambda m: m.group(1).translate(_SUBSCRIPTS), s)
    s = re.sub(r"_([0-9])", lambda m: m.group(1).translate(_SUBSCRIPTS), s)
    s = re.sub(r"_\{([^{}]+)\}", r"_\1", s)

    # Convert numeric superscripts x^{2} or x^2 -> x²
    s = re.sub(r"\^\{([0-9+-=()]+)\}", lambda m: m.group(1).translate(_SUPERSCRIPTS), s)
    s = re.sub(r"\^([0-9])", lambda m: m.group(1).translate(_SUPERSCRIPTS), s)
    s = re.sub(r"\^\{([^{}]+)\}", r"^\1", s)

    # Clean any remaining LaTeX spacing/slashes
    s = s.replace(r"\,", " ").replace(r"\;", " ").replace(r"\!", "")
    s = s.replace("{", "").replace("}", "")
    return s

class AIEngine:
    def __init__(self, api_key=None, model=None):
        key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
        if not key:
            raise ValueError("GEMINI_API_KEY is missing. Please set it in your .env file.")
        genai.configure(api_key=key)
        self.model_name = model or "gemini-3.5-flash-lite"
        self._model = genai.GenerativeModel(self.model_name, system_instruction=SYSTEM)

    def _complete(self, prompt, json_mode=False, temperature=0.3):
        last = None
        for attempt in range(3):
            try:
                cfg = {"temperature": temperature}
                if json_mode:
                    cfg["response_mime_type"] = "application/json"
                return self._model.generate_content(prompt, generation_config=cfg).text
            except Exception as exc:
                last = exc
                err_str = str(exc)
                if "429" in err_str or "quota" in err_str.lower():
                    match = re.search(r"retry in (\d+(?:\.\d+)?)s", err_str, re.IGNORECASE)
                    wait_sec = (float(match.group(1)) + 2.0) if match else 35.0
                    time.sleep(min(wait_sec, 65.0))
                else:
                    time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"Gemini request failed after 3 attempts: {last}")

    @staticmethod
    def build_context(inputs, stats):
        dept = inputs["department"]
        return (
            f"=== EXPERIMENT DATA & STUDENT BASE INPUTS ===\n"
            f"Department: Department of {dept} Engineering\n"
            f"Experiment Title: {inputs['experiment']}\n"
            f"Aim: {inputs['aim']}\n"
            f"Apparatus / Equipment / Setup: {inputs.get('apparatus') or 'not provided'}\n"
            f"Student Base Objectives: {inputs.get('objectives') or 'not provided'}\n"
            f"Student Base Problem Statement / Description: {inputs.get('problem_statement') or 'not provided'}\n"
            f"Student Base Introduction: {inputs.get('introduction') or 'not provided'}\n"
            f"Student Base Assumptions / Specifications: {inputs.get('assumptions') or 'not provided'}\n"
            f"Student Base Theory: {inputs.get('theory') or 'not provided'}\n"
            f"Student Mathematical Modeling Equations (LaTeX - USE THESE EXACT FORMULAS FOR CALCULATIONS):\n"
            f"{inputs.get('math_modeling') or 'not provided'}\n"
            f"Student Base Procedure: {inputs.get('procedure') or 'not provided'}\n"
            f"Experimental Readings Table:\n{inputs.get('readings_text') or 'none'}\n"
            f"Computed Statistical Summary:\n{stats_to_text(stats)}\n"
            f"Student Base Assumptions / Specifications (EXTRACT ANY FIXED CONSTANTS OR RATED VALUES FOR CALCULATIONS):\n"
            f"{inputs.get('assumptions') or 'not provided'}\n"
            f"=== END DATA ==="
        )

    def generate_report(self, inputs, stats, graphs, include_error_analysis=True, progress=None):
        dept = inputs["department"]
        ctx = self.build_context(inputs, stats)
        focus = DEPARTMENT_FOCUS[dept]
        if graphs:
            ctx += "\nGenerated Graphs Included: " + "; ".join(g["title"] for g in graphs)

        active_keys = [k for k in ORDER if k != "error_analysis" or include_error_analysis]

        if progress:
            progress(0, 2, f"Generating {dept} Engineering report sections")

        section_specs = "\n".join(
            f'- "{key}": {PROMPTS[key].replace("{dept}", dept).replace("{dept_focus}", focus)}'
            for key in active_keys
        )
        schema_example = json.dumps({key: "..." for key in active_keys})
        combined_prompt = (
            f"{ctx}\n\n"
            f"TASK: Generate all {len(active_keys)} laboratory report sections for a "
            f"Department of {dept} Engineering report in a SINGLE valid JSON object.\n"
            f"Exact JSON keys required: {schema_example}\n\n"
            "Section instructions:\n"
            f"{section_specs}\n\n"
            "CRITICAL OUTPUT RULES:\n"
            "1. Return valid JSON only.\n"
            "2. Treat the student's supplied base sections as the foundation—refine and polish them without altering their core facts or formulas.\n"
            "3. In 'calculations', use ONLY the formulas supplied in 'Student Mathematical Modeling Equations' "
                "together with any fixed constants, physical properties, or nominal/rated values stated in "
                "'Student Base Assumptions / Specifications'.\n"
            "4. Escape backslashes properly inside JSON strings (e.g., use \\\\frac instead of \\frac).\n"
            "5. Keep tone authoritative, detailed, and realistic—never over-exaggerated."
        )
        
        raw = self._complete(combined_prompt, json_mode=True, temperature=0.3)
        parsed = extract_json(raw)

        sections = {}
        for key in active_keys:
            val = parsed.get(key, "")
            if isinstance(val, list):
                val = "\n".join(str(item) for item in val)
            if key == "mathematical_modeling":
                raw_math = str(val).strip() or inputs.get("math_modeling", "").strip()
                sections[key] = _normalize_latex_blocks(raw_math)
            else:
                sections[key] = latex_to_readable(clean_text(str(val)))

        if progress:
            progress(1, 2, LABELS["viva"])

        sections["viva"] = self.generate_viva_bank(ctx, dept, focus)

        if progress:
            progress(2, 2, "Done")
        return sections

    def generate_viva_bank(self, ctx, dept, focus):
        prompt = f"{ctx}\n\nTASK: " + VIVA_PROMPT.format(dept=dept, dept_focus=focus)
        for _ in range(2):
            try:
                data = extract_json(self._complete(prompt, json_mode=True, temperature=0.45))
                return {
                    k: [{"q": clean_text(str(x.get("q", ""))), "a": clean_text(str(x.get("a", "")))}
                        for x in data.get(k, [])]
                    for k in ("beginner", "intermediate", "advanced")
                }
            except Exception:
                continue
        return {"beginner": [], "intermediate": [], "advanced": []}

    def viva_question(self, ctx, dept, asked, level):
        asked_txt = "\n".join(f"- {q}" for q in asked) or "(none yet)"
        task = VIVA_Q_PROMPT.format(dept=dept, level=level.lower(), asked=asked_txt)
        return clean_text(self._complete(f"{ctx}\n\nTASK: {task}", temperature=0.75))

    def viva_evaluate(self, ctx, dept, question, answer):
        task = VIVA_EVAL_PROMPT.format(dept=dept, question=question, answer=answer or "(no answer)")
        data = extract_json(self._complete(f"{ctx}\n\nTASK: {task}", json_mode=True, temperature=0.2))

        def num(k):
            try:
                return max(0.0, min(10.0, float(data.get(k, 0))))
            except (TypeError, ValueError):
                return 0.0

        return {
            "technical_accuracy": num("technical_accuracy"),
            "confidence": num("confidence"),
            "completeness": num("completeness"),
            "score": num("score"),
            "feedback": clean_text(str(data.get("feedback", ""))),
            "model_answer": clean_text(str(data.get("model_answer", ""))),
        }

