"""PDF (fpdf2) and DOCX (python-docx) exporters with Logo, Student Metadata & LaTeX rendering."""
import datetime
import hashlib
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from fpdf import FPDF

from templates.report_template import build_blocks
from utils import OUTPUT_DIR, latin1
from ai_engine import latex_to_readable

NAVY = (11, 31, 51)


def _render_latex_png(expr: str) -> str | None:
    """Render a LaTeX math expression into a clean transparent/white 300-DPI PNG via matplotlib."""
    clean_expr = expr.strip().strip("$").strip()
    if not clean_expr:
        return None
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    digest = hashlib.md5(clean_expr.encode("utf-8")).hexdigest()[:12]
    out_path = os.path.join(OUTPUT_DIR, f"eq_{digest}.png")
    if os.path.exists(out_path):
        return out_path
    try:
        fig = plt.figure(figsize=(6.5, 0.75), dpi=300)
        fig.patch.set_facecolor("white")
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis("off")
        ax.text(0.5, 0.5, f"${clean_expr}$", fontsize=14, ha="center", va="center", color="#0B1F33")
        fig.savefig(out_path, dpi=300, bbox_inches="tight", pad_inches=0.08, facecolor="white")
        plt.close(fig)
        return out_path
    except Exception:
        plt.close("all")
        return None


def _split_latex_blocks(text: str):
    """Split text containing $$...$$ blocks into ('text', str) and ('eq', str) items."""
    parts = re.split(r"(\$\$.*?\$\$)", text, flags=re.DOTALL)
    items = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if p.startswith("$$") and p.endswith("$$"):
            items.append(("eq", p[2:-2].strip()))
        else:
            items.append(("text", p))
    return items


def _student_meta_rows(meta: dict):
    date_str = meta.get("date") or datetime.date.today().strftime("%d %B %Y")
    return [
        ["Student Name", meta.get("student", ""), "PRN", meta.get("prn", "")],
        ["Year of Study", meta.get("year", ""), "Roll Number", meta.get("roll_no", "")],
        ["Division", meta.get("division", ""), "Batch", meta.get("batch", "")],
        ["Date", date_str, "Department", f"{meta.get('department', '')} Engineering"],
    ]


def _paragraph_items(text):
    items, buf = [], []
    for line in text.split("\n"):
        s = line.rstrip()
        if s.startswith("- "):
            if buf:
                items.append(("p", " ".join(buf)))
                buf = []
            items.append(("b", s[2:].strip()))
        elif not s.strip():
            if buf:
                items.append(("p", " ".join(buf)))
                buf = []
        elif s.startswith("Step ") or s[:3].strip().rstrip(".").isdigit():
            if buf:
                items.append(("p", " ".join(buf)))
                buf = []
            items.append(("eq_line", s.strip()))
        else:
            if buf:
                items.append(("p", " ".join(buf)))
                buf = []
            items.append(("p", s.strip()))
    if buf:
        items.append(("p", " ".join(buf)))
    return items

# =================================================================== PDF ====
class _PDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Times", "I", 9)
        self.set_text_color(90, 90, 90)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def build_pdf(report, path):
    meta = report["meta"]
    pdf = _PDF(format="A4")
    pdf.set_margins(20, 18, 20)
    pdf.set_auto_page_break(True, margin=20)
    pdf.add_page()
    W = pdf.w - pdf.l_margin - pdf.r_margin

    # 1. University / College Logo (Centered at Top)
    logo_path = meta.get("logo_path")
    if logo_path and os.path.exists(logo_path):
        logo_w = 44  # increased from 28 mm for prominent header presence
        pdf.image(logo_path, x=(pdf.w - logo_w) / 2, w=logo_w)
        pdf.ln(5)

    # 2. Department Name directly below Logo
    pdf.set_font("Times", "B", 13)
    pdf.set_text_color(*NAVY)
    pdf.multi_cell(0, 7, latin1(f"DEPARTMENT OF {meta['department'].upper()} ENGINEERING"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # 3. Laboratory Report Header & Experiment Title
    pdf.set_font("Times", "", 11)
    pdf.set_text_color(70, 85, 100)
    pdf.cell(0, 6, "LABORATORY EXPERIMENT REPORT", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_font("Times", "B", 17)
    pdf.set_text_color(*NAVY)
    pdf.multi_cell(0, 9, latin1(meta["experiment"]), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # 4. Student Details Grid Table on First Page
    col_w = [W * 0.22, W * 0.28, W * 0.22, W * 0.28]
    for row in _student_meta_rows(meta):
        for idx, val in enumerate(row):
            is_label = idx in (0, 2)
            pdf.set_font("Times", "B" if is_label else "", 10)
            pdf.set_fill_color(235, 241, 246) if is_label else pdf.set_fill_color(255, 255, 255)
            pdf.set_text_color(*NAVY) if is_label else pdf.set_text_color(20, 20, 20)
            pdf.cell(col_w[idx], 7, latin1(str(val)), border=1, align="L", fill=True)
        pdf.ln(7)

    pdf.ln(4)
    pdf.set_draw_color(*NAVY)
    pdf.set_line_width(0.7)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(7)

    # 5. Report Sections
    for n, (heading, blocks) in enumerate(build_blocks(report), 1):
        if pdf.get_y() > pdf.h - 45:
            pdf.add_page()
        pdf.set_font("Times", "B", 13)
        pdf.set_text_color(*NAVY)
        pdf.cell(0, 8, latin1(f"{n}. {heading.upper()}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

        for blk in blocks:
            kind = blk[0]
            if kind == "text":
                for t, content in _paragraph_items(blk[1]):
                    if t == "b":
                        pdf.set_font("Times", "", 11.5)
                        pdf.set_x(pdf.l_margin + 5)
                        pdf.multi_cell(W - 5, 6, latin1("- " + content), new_x="LMARGIN", new_y="NEXT")
                    elif t == "eq_line":
                        pdf.ln(1.5)
                        pdf.set_font("Times", "B", 11.5)
                        pdf.set_x(pdf.l_margin + 4)
                        pdf.multi_cell(W - 4, 6.2, latin1(content), new_x="LMARGIN", new_y="NEXT")
                    else:
                        pdf.set_font("Times", "", 11.5)
                        pdf.multi_cell(0, 6, latin1(content), align="J", new_x="LMARGIN", new_y="NEXT")
                        pdf.ln(1.8)
            elif kind == "latex":
                for item_type, val in _split_latex_blocks(blk[1]):
                    if item_type == "eq":
                        eq_png = _render_latex_png(val)
                        if eq_png and os.path.exists(eq_png):
                            if pdf.get_y() > pdf.h - 30:
                                pdf.add_page()
                            pdf.image(eq_png, x=pdf.l_margin + 25, w=W - 50)
                            pdf.ln(2)
                        else:
                            pdf.set_font("Times", "B", 11.5)
                            pdf.multi_cell(0, 6.5, latin1(latex_to_readable(val)), align="C", new_x="LMARGIN", new_y="NEXT")
                    else:
                        for t, content in _paragraph_items(val):
                            pdf.set_font("Times", "", 11.5)
                            if t == "b":
                                pdf.set_x(pdf.l_margin + 5)
                                pdf.multi_cell(W - 5, 6, latin1("- " + content), new_x="LMARGIN", new_y="NEXT")
                            else:
                                pdf.multi_cell(0, 6, latin1(content), align="J", new_x="LMARGIN", new_y="NEXT")
            elif kind == "sub":
                pdf.set_font("Times", "BI", 11.5)
                pdf.cell(0, 7, latin1(blk[1]), new_x="LMARGIN", new_y="NEXT")
            elif kind == "table":
                _pdf_table(pdf, blk[1], blk[2], W)
            elif kind == "image":
                if os.path.exists(blk[1]):
                    if pdf.get_y() > pdf.h - 105:
                        pdf.add_page()
                    pdf.image(blk[1], x=pdf.l_margin + 12, w=W - 24)
                    pdf.set_font("Times", "I", 10)
                    pdf.multi_cell(0, 5, latin1(blk[2]), align="C", new_x="LMARGIN", new_y="NEXT")
                    pdf.ln(3)
        pdf.ln(2.5)

    pdf.output(path)
    with open(path, "rb") as f:
        return f.read()


def _pdf_table(pdf, header, rows, W):
    ncol = max(1, len(header))
    cw = W / ncol
    size = 10 if ncol <= 5 else 8 if ncol <= 7 else 7
    maxc = max(4, int(cw / (size * 0.19)))
    fit = lambda s: latin1(str(s))[:maxc]
    pdf.set_font("Times", "B", size)
    pdf.set_fill_color(220, 228, 238)
    for h in header:
        pdf.cell(cw, 7, fit(h), border=1, align="C", fill=True)
    pdf.ln(7)
    pdf.set_font("Times", "", size)
    for r in rows:
        if pdf.get_y() > pdf.h - 25:
            pdf.add_page()
            pdf.set_font("Times", "B", size)
            for h in header:
                pdf.cell(cw, 7, fit(h), border=1, align="C", fill=True)
            pdf.ln(7)
            pdf.set_font("Times", "", size)
        for v in r:
            pdf.cell(cw, 6.5, fit(v), border=1, align="C")
        pdf.ln(6.5)
    pdf.ln(3)


# ================================================================== DOCX ====
def _shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def _page_number(paragraph):
    run = paragraph.add_run()
    for tag, txt in (("begin", None), (None, "PAGE"), ("end", None)):
        if tag:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), tag)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = txt
        run._r.append(el)


def build_docx(report, path):
    meta = report["meta"]
    doc = Document()
    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Inches(0.85)
    sec.top_margin = sec.bottom_margin = Inches(0.85)

    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15

    h1 = doc.styles["Heading 1"]
    h1.font.name = "Times New Roman"
    h1.font.size = Pt(13.5)
    h1.font.bold = True
    h1.font.color.rgb = RGBColor(*NAVY)
    h1.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    h1.paragraph_format.space_before = Pt(14)
    h1.paragraph_format.space_after = Pt(5)

    # 1. Logo at Top
    logo_path = meta.get("logo_path")
    if logo_path and os.path.exists(logo_path):
        p_logo = doc.add_paragraph()
        p_logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_logo.add_run().add_picture(logo_path, width=Inches(1.75))

    # 2. Department Name below Logo
    p_dept = doc.add_paragraph()
    p_dept.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_dept = p_dept.add_run(f"DEPARTMENT OF {meta['department'].upper()} ENGINEERING")
    r_dept.bold = True
    r_dept.font.size = Pt(14)
    r_dept.font.color.rgb = RGBColor(*NAVY)

    # 3. Title Block
    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_sub = p_sub.add_run("LABORATORY EXPERIMENT REPORT")
    r_sub.font.size = Pt(11)

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_title = p_title.add_run(meta["experiment"])
    r_title.bold = True
    r_title.font.size = Pt(17)
    r_title.font.color.rgb = RGBColor(*NAVY)

    # 4. Student Details Table on Page 1
    meta_rows = _student_meta_rows(meta)
    meta_tbl = doc.add_table(rows=len(meta_rows), cols=4)
    meta_tbl.style = "Table Grid"
    meta_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for r_idx, row in enumerate(meta_rows):
        for c_idx, val in enumerate(row):
            cell = meta_tbl.rows[r_idx].cells[c_idx]
            cell.text = ""
            run = cell.paragraphs[0].add_run(str(val))
            run.font.size = Pt(10.5)
            if c_idx in (0, 2):
                run.bold = True
                _shade(cell, "EBF1F6")

    doc.add_paragraph()

    foot = sec.footer.paragraphs[0]
    foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    foot.add_run("Page ")
    _page_number(foot)

    for n, (heading, blocks) in enumerate(build_blocks(report), 1):
        doc.add_heading(f"{n}. {heading.upper()}", level=1)
        for blk in blocks:
            kind = blk[0]
            if kind == "text":
                for t, content in _paragraph_items(blk[1]):
                    if t == "b":
                        doc.add_paragraph(content, style="List Bullet")
                    elif t == "eq_line":
                        p = doc.add_paragraph()
                        p.paragraph_format.left_indent = Inches(0.2)
                        p.paragraph_format.space_before = Pt(6)
                        p.paragraph_format.space_after = Pt(2)
                        r = p.add_run(content)
                        r.bold = True
                        r.font.name = "Times New Roman"
                    else:
                        p = doc.add_paragraph(content)
                        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            elif kind == "latex":
                for item_type, val in _split_latex_blocks(blk[1]):
                    if item_type == "eq":
                        eq_png = _render_latex_png(val)
                        if eq_png and os.path.exists(eq_png):
                            p_eq = doc.add_paragraph()
                            p_eq.alignment = WD_ALIGN_PARAGRAPH.CENTER
                            p_eq.add_run().add_picture(eq_png, width=Inches(4.2))
                        else:
                            p_eq = doc.add_paragraph(latex_to_readable(val))
                            p_eq.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    else:
                        for t, content in _paragraph_items(val):
                            if t == "b":
                                doc.add_paragraph(content, style="List Bullet")
                            else:
                                p = doc.add_paragraph(content)
                                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            elif kind == "sub":
                p = doc.add_paragraph()
                r = p.add_run(blk[1])
                r.bold = True
                r.italic = True
            elif kind == "table":
                header, rows = blk[1], blk[2]
                tbl = doc.add_table(rows=1, cols=len(header))
                tbl.style = "Table Grid"
                tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
                for i, h in enumerate(header):
                    c = tbl.rows[0].cells[i]
                    c.text = ""
                    run = c.paragraphs[0].add_run(str(h))
                    run.bold = True
                    run.font.size = Pt(10)
                    c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                    _shade(c, "DCE4EE")
                for r_ in rows:
                    cells = tbl.add_row().cells
                    for i, v in enumerate(r_):
                        cells[i].text = ""
                        run = cells[i].paragraphs[0].add_run(str(v))
                        run.font.size = Pt(10)
                        cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                doc.add_paragraph()
            elif kind == "image" and os.path.exists(blk[1]):
                doc.add_picture(blk[1], width=Inches(5.4))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                cap = doc.add_paragraph()
                cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cr = cap.add_run(blk[2])
                cr.italic = True
                cr.font.size = Pt(10)

    doc.save(path)
    with open(path, "rb") as f:
        return f.read()