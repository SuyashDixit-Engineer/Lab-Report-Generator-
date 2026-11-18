# 🧪 Lab Report generator

**Engineering Lab Copilot** is an AI-powered laboratory report generator and interactive viva-voce simulator designed for undergraduate engineering students. It transforms raw experimental observations, CSV/Excel datasets, and student-provided base notes into a formatted, department-specific academic engineering report with automated graphs, step-by-step calculations, and one-click **PDF** and **DOCX** exports.

## ✨ Key Features

* **Department-Aware Engineering Intelligence:** Tailors technical vocabulary, physical interpretations, and analytical reasoning across **Mechanical**, **Electrical**, **Civil**, **Electronics**, and **Chemical** Engineering.

* **Academic Cover Page & Student Metadata:** Automatically formats Page 1 with the uploaded **University / College Logo**, **Department Name**, **Experiment Title**, and a structured student credential block (**Student Name, PRN, Year of Study, Roll Number, Division, Batch, and Experiment Date**).

* **User-Driven Base + Formula-Locked Calculations:**

  * Students provide the foundational content for *Aim, Apparatus/Setup (with optional setup photograph), Objectives, Problem Statement, Introduction, Assumptions/Specifications, Theory, Procedure,* and *Mathematical Modeling*.

  * Accepts equations in **LaTeX format** (`$$R = \frac{V}{I}$$`), renders live previews, and converts equations into clean, readable mathematical notation across the report.

  * Performs step-by-step **Calculations** strictly using the user's supplied formulas, constants/specifications, and measured dataset.

* **Automated Data Analysis & Plotting (`matplotlib` / `seaborn`):**

  * Parses uploaded `.csv`, `.xlsx`, or `.xls` files (or pasted CSV text).

  * Computes descriptive statistics (*Mean, Max, Min, Standard Deviation*) and automatically detects hydraulic/electrical efficiency metrics.

  * Generates high-resolution plots with least-squares linear regression fits and $R^2$ values.

* **Dual Live Report Preview & Export:**

  * **Formatted Document Sheet (A4):** Realistic white A4 paper preview in Times New Roman directly inside the dashboard.

  * **Actual Exported PDF Pages:** Built-in multi-page PDF viewer alongside one-click **`.pdf`** (`fpdf2`) and **`.docx`** (`python-docx`) downloads.

* **Interactive AI Viva Mode:** Simulates an oral viva-voce examination with progressive difficulty (*Beginner → Intermediate → Advanced*), scoring responses on **Technical Accuracy**, **Confidence**, and **Completeness** out of 10 with model answers.

* **Light & Dark Theme Support:** Instant UI theme toggle between Dark and Light modes.

## 🏗️ Project Architecture

```
project/
├── .env                        # Environment variables (GEMINI_API_KEY)
├── .gitignore                  # Git ignore rules for secrets, cache, and temp outputs
├── .streamlit/
│   └── config.toml             # Streamlit server and UI configuration
├── app.py                      # Main Streamlit dashboard, A4 previewer & Viva UI
├── ai_engine.py                # Google Gemini integration, prompts & LaTeX-to-math parser
├── graph_generator.py          # Automated Matplotlib/Seaborn plotting & regression engine
├── report_generator.py         # Academic PDF (fpdf2) & DOCX (python-docx) builders
├── utils.py                    # Data ingestion, statistical computations & text helpers
├── templates/
│   ├── __init__.py
│   └── report_template.py      # Unified report section layout & department focus rules
├── assets/
│   └── sample_data/
│       ├── ohms_law.csv        # Sample Electrical Engineering dataset
│       └── pump_test.csv       # Sample Mechanical Engineering dataset
├── outputs/
│   └── .gitkeep                # Directory for generated graphs, PDFs, and DOCX files
├── Dockerfile                  # Containerized deployment configuration
└── requirements.txt            # Python package dependencies

```

## 🚀 Getting Started

### 1. Prerequisites

* **Python 3.10+** (tested on Python 3.13)

* A **Google Gemini API Key** from [Google AI Studio](https://aistudio.google.com/)

### 2. Installation

Clone the repository and navigate into the project directory:

```
git clone <your-repository-url>
cd project

```

Create and activate a virtual environment (recommended):

```
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate

```

Install the required dependencies:

```
pip install -r requirements.txt

```

### 3. Configure Environment Variables

Create a `.env` file in the root directory and add your Gemini API key:

```
GEMINI_API_KEY=your_gemini_api_key_here

```

### 4. Run the Application

```
streamlit run app.py

```

The application will open in your browser at `http://localhost:8501`.

## 🐳 Docker Deployment

To build and run the application inside a Docker container:

```
docker build -t engineering-lab-copilot .
docker run -p 8501:8501 --env-file .env engineering-lab-copilot

```

## 📖 How to Use

1. **Configure Sidebar Details:**

   * Choose **Dark** or **Light** appearance mode.

   * Select your **Engineering Department** and optionally upload your **University / College Logo**.

   * Fill in your mandatory student credentials (**Full Name, PRN, Year, Roll Number, Division, Batch, and Date**).

   * *(Optional)* Click **Load sample experiment** (`Ohm's Law` or `Centrifugal Pump`) to test with pre-filled data.

2. **Enter Experiment Details & Formulas:**

   * Fill in the experiment title, aim, apparatus list (and optional setup image), objectives, problem statement, introduction, assumptions/specifications, theory, and procedure.

   * Enter governing formulas in **LaTeX format** inside the *Mathematical Modeling* box.

3. **Upload Experimental Readings:**

   * Upload a `.csv` or `.xlsx` file (with the independent X-axis variable in the first column) or paste raw CSV rows.

4. **Generate, Preview & Export:**

   * Click **🚀 Generate Report** to generate the graphs, step-by-step calculations, error analysis, results, and conclusion.

   * Inspect the report in **Formatted Document Sheet (A4)** or **Actual Exported PDF Pages** view, then download the **PDF** or **DOCX** file.

5. **Practice in Viva Mode:**

   * Switch to the **🎤 Viva Mode** tab to practice answering department-specific oral exam questions evaluated by the AI examiner.

## 🛠️ Tech Stack

* **Frontend / UI:** Streamlit

* **Generative AI:** Google Gemini (`gemini-3.5-flash-lite` via `google-generativeai`)

* **Data Analysis:** Pandas, NumPy

* **Visualization:** Matplotlib, Seaborn

* **Document Generation:** `fpdf2` (PDF), `python-docx` (Word DOCX)
