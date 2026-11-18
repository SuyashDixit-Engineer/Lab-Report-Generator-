# 🧪 Engineering Lab Copilot

A GenAI web app that turns raw experiment data into a professional, data-driven lab report
(PDF + DOCX), with automatic statistics, graphs, department-specific analysis and an AI viva examiner.

## Architecture

```
project/
├── app.py                    Streamlit UI (sidebar, 6 dashboard sections, Viva Mode tab)
├── ai_engine.py              Provider abstraction (Gemini/OpenAI), engineered prompts, viva logic
├── utils.py                  CSV/Excel loading, statistics + efficiency detection, text cleaning, samples
├── graph_generator.py        Matplotlib/Seaborn plots + linear fit (slope, R²)
├── report_generator.py       PDF (fpdf2) and DOCX (python-docx) renderers
├── templates/
│   └── report_template.py    Report layout, department focus text, shared block builder
├── assets/sample_data/       ohms_law.csv, pump_test.csv
├── outputs/                  Generated graphs, PDFs, DOCX
├── requirements.txt  .env.example  Dockerfile  .streamlit/config.toml
```

**Data flow:** inputs → `utils.compute_stats` (mean/max/min/std/efficiency) → `graph_generator`
→ `ai_engine` (11 targeted prompts, each given the real computed statistics so the AI interprets
numbers instead of inventing them) → `report_template.build_blocks` → preview / PDF / DOCX.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # add GEMINI_API_KEY and/or OPENAI_API_KEY
streamlit run app.py
```

Open http://localhost:8501. Free Gemini key: https://aistudio.google.com/apikey

## Using it

1. Pick a **sample** in the sidebar and click *Load sample experiment* (or enter your own data).
2. Paste CSV readings or upload CSV/Excel. **First column = X axis**; every other numeric column is plotted against it.
3. Click **Generate Report**, preview it, then download PDF/DOCX.
4. Open the **Viva Mode** tab for a one-question-at-a-time oral exam scored on technical accuracy, confidence and completeness.

Efficiency is computed automatically if the data has an `efficiency` column or `Input…`/`Output…` columns.

## Environment variables

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Google Gemini key (default model `gemini-2.0-flash`) |
| `OPENAI_API_KEY` | OpenAI key (default model `gpt-4o-mini`) |

The key can also be typed into the sidebar; the model name is overridable there.

## Deployment

**Streamlit Community Cloud (free):** push to GitHub → share.streamlit.io → New app → `app.py`
→ Settings → Secrets: `GEMINI_API_KEY = "..."` (secrets are exposed as env vars).

**Docker:**
```bash
docker build -t lab-copilot .
docker run -p 8501:8501 -e GEMINI_API_KEY=xxx lab-copilot
```

**Render / Railway / Cloud Run:** deploy the Dockerfile, set the key as an env var, expose port 8501.

## Notes

- Add images/logo to `assets/` and extend `report_generator.py` for a college cover page.
- PDF uses Latin-1 core fonts; Greek/special symbols are transliterated (σ → sigma). Use DOCX for full Unicode.
- Always review AI-written text before submitting; the app is a drafting assistant.
