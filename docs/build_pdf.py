"""
Generate docs/USER_GUIDE.pdf from docs/USER_GUIDE.md using ReportLab.
Run from the project root:  python docs/build_pdf.py
"""

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

# ── Colour palette ──────────────────────────────────────────────────────────
BLUE_DARK  = colors.HexColor("#1a3a5c")
BLUE_MID   = colors.HexColor("#2563a8")
BLUE_LIGHT = colors.HexColor("#dbeafe")
GREY_CODE  = colors.HexColor("#f3f4f6")
GREY_LINE  = colors.HexColor("#d1d5db")
WHITE      = colors.white
BLACK      = colors.black

# ── Styles ──────────────────────────────────────────────────────────────────
base = getSampleStyleSheet()

S = {
    "h1": ParagraphStyle(
        "h1", parent=base["Normal"],
        fontSize=22, leading=28, textColor=BLUE_DARK,
        fontName="Helvetica-Bold", spaceBefore=6, spaceAfter=10,
    ),
    "h2": ParagraphStyle(
        "h2", parent=base["Normal"],
        fontSize=14, leading=18, textColor=BLUE_DARK,
        fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=4,
        borderPad=0,
    ),
    "h3": ParagraphStyle(
        "h3", parent=base["Normal"],
        fontSize=11, leading=15, textColor=BLUE_MID,
        fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=2,
    ),
    "body": ParagraphStyle(
        "body", parent=base["Normal"],
        fontSize=9.5, leading=14, textColor=BLACK,
        fontName="Helvetica", spaceBefore=2, spaceAfter=4,
    ),
    "bullet": ParagraphStyle(
        "bullet", parent=base["Normal"],
        fontSize=9.5, leading=13, textColor=BLACK,
        fontName="Helvetica", leftIndent=14, spaceBefore=1, spaceAfter=1,
        bulletIndent=4,
    ),
    "code_block": ParagraphStyle(
        "code_block", parent=base["Normal"],
        fontSize=8, leading=11, textColor=BLACK,
        fontName="Courier", leftIndent=10, rightIndent=10,
        backColor=GREY_CODE, spaceBefore=4, spaceAfter=4,
        borderPad=6,
    ),
    "code_inline": ParagraphStyle(
        "code_inline", parent=base["Normal"],
        fontSize=9.5, leading=14, textColor=BLACK,
        fontName="Courier", spaceBefore=2, spaceAfter=4,
    ),
    "toc_h": ParagraphStyle(
        "toc_h", parent=base["Normal"],
        fontSize=9.5, leading=13, fontName="Helvetica",
        textColor=BLUE_MID, leftIndent=0,
    ),
    "note": ParagraphStyle(
        "note", parent=base["Normal"],
        fontSize=9, leading=13, textColor=colors.HexColor("#374151"),
        fontName="Helvetica-Oblique", leftIndent=12, rightIndent=12,
        backColor=BLUE_LIGHT, spaceBefore=4, spaceAfter=6,
        borderPad=5,
    ),
}

TABLE_STYLE = TableStyle([
    ("BACKGROUND",   (0, 0), (-1, 0), BLUE_DARK),
    ("TEXTCOLOR",    (0, 0), (-1, 0), WHITE),
    ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE",     (0, 0), (-1, 0), 9),
    ("ALIGN",        (0, 0), (-1, 0), "LEFT"),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, colors.HexColor("#f0f4f8")]),
    ("FONTNAME",     (0, 1), (-1, -1), "Helvetica"),
    ("FONTSIZE",     (0, 1), (-1, -1), 9),
    ("ALIGN",        (0, 1), (-1, -1), "LEFT"),
    ("VALIGN",       (0, 0), (-1, -1), "TOP"),
    ("GRID",         (0, 0), (-1, -1), 0.4, GREY_LINE),
    ("LEFTPADDING",  (0, 0), (-1, -1), 6),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ("TOPPADDING",   (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
])


def _escape(text: str) -> str:
    """Escape ReportLab XML special characters."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def _inline(text: str) -> str:
    """Convert inline markdown (bold, code, italic) to ReportLab markup."""
    # inline code  `…`
    text = re.sub(r'`([^`]+)`',
                  lambda m: f'<font name="Courier">{_escape(m.group(1))}</font>',
                  text)
    # bold **…**
    text = re.sub(r'\*\*(.+?)\*\*',
                  lambda m: f'<b>{m.group(1)}</b>', text)
    # italic *…*
    text = re.sub(r'\*(.+?)\*',
                  lambda m: f'<i>{m.group(1)}</i>', text)
    return text


def parse_md(md_text: str):
    """
    Walk through the markdown line by line and build a list of
    (kind, payload) tuples consumed by build_story().

    kinds: h1, h2, h3, body, bullet, code, table, hr, blank, note
    """
    items = []
    lines = md_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]

        # fenced code block
        if line.strip().startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            items.append(("code", "\n".join(code_lines)))
            i += 1
            continue

        # markdown table
        if "|" in line and i + 1 < len(lines) and re.match(r"^\|[-| :]+\|", lines[i + 1]):
            rows = []
            while i < len(lines) and "|" in lines[i]:
                if re.match(r"^\|[-| :]+\|", lines[i]):
                    i += 1
                    continue
                cells = [c.strip() for c in lines[i].split("|") if c.strip() != ""]
                rows.append(cells)
                i += 1
            items.append(("table", rows))
            continue

        # horizontal rule
        if re.match(r"^---+$", line.strip()):
            items.append(("hr", None))
            i += 1
            continue

        # headings
        if line.startswith("### "):
            items.append(("h3", _escape(line[4:].strip())))
        elif line.startswith("## "):
            items.append(("h2", _escape(line[3:].strip())))
        elif line.startswith("# "):
            items.append(("h1", _escape(line[2:].strip())))

        # blockquote / note
        elif line.startswith("> "):
            items.append(("note", _inline(_escape(line[2:].strip()))))

        # bullet
        elif re.match(r"^[-*] ", line):
            items.append(("bullet", _inline(_escape(line[2:].strip()))))
        elif re.match(r"^\d+\. ", line):
            items.append(("bullet", _inline(_escape(re.sub(r"^\d+\. ", "", line)))))

        # blank
        elif line.strip() == "":
            items.append(("blank", None))

        # body text
        else:
            items.append(("body", _inline(_escape(line.strip()))))

        i += 1
    return items


def build_story(items):
    """Convert parsed items into ReportLab flowables."""
    story = []
    PAGE_W = A4[0] - 40 * mm  # usable table width

    for kind, payload in items:
        if kind == "h1":
            story.append(Spacer(1, 4))
            story.append(Paragraph(payload, S["h1"]))
            story.append(HRFlowable(width="100%", thickness=2,
                                    color=BLUE_MID, spaceAfter=4))
        elif kind == "h2":
            story.append(Paragraph(payload, S["h2"]))
            story.append(HRFlowable(width="100%", thickness=0.5,
                                    color=GREY_LINE, spaceAfter=2))
        elif kind == "h3":
            story.append(Paragraph(payload, S["h3"]))
        elif kind == "body":
            if payload.strip():
                story.append(Paragraph(payload, S["body"]))
        elif kind == "bullet":
            story.append(Paragraph(f"• {payload}", S["bullet"]))
        elif kind == "code":
            # Split into lines, escape each, rejoin with <br/>
            escaped = "<br/>".join(
                _escape(l) for l in payload.splitlines()
            )
            story.append(Paragraph(escaped, S["code_block"]))
        elif kind == "note":
            story.append(Paragraph(f"<i>{payload}</i>", S["note"]))
        elif kind == "hr":
            story.append(Spacer(1, 4))
            story.append(HRFlowable(width="100%", thickness=1,
                                    color=GREY_LINE))
            story.append(Spacer(1, 4))
        elif kind == "blank":
            story.append(Spacer(1, 3))
        elif kind == "table":
            if not payload:
                continue
            headers = payload[0]
            data_rows = payload[1:]
            # Convert cells to Paragraphs
            hdr_style = ParagraphStyle(
                "th", parent=base["Normal"],
                fontSize=9, fontName="Helvetica-Bold",
                textColor=WHITE, leading=12,
            )
            cell_style = ParagraphStyle(
                "td", parent=base["Normal"],
                fontSize=9, fontName="Helvetica",
                textColor=BLACK, leading=12,
            )
            n_cols = len(headers)
            col_w = PAGE_W / n_cols
            table_data = [[Paragraph(_inline(_escape(h)), hdr_style) for h in headers]]
            for row in data_rows:
                # Pad short rows
                while len(row) < n_cols:
                    row.append("")
                table_data.append(
                    [Paragraph(_inline(_escape(c)), cell_style) for c in row]
                )
            tbl = Table(table_data, colWidths=[col_w] * n_cols,
                        repeatRows=1, hAlign="LEFT")
            tbl.setStyle(TABLE_STYLE)
            story.append(Spacer(1, 4))
            story.append(tbl)
            story.append(Spacer(1, 6))

    return story


def on_first_page(canvas, doc):
    canvas.saveState()
    # Header band
    canvas.setFillColor(BLUE_DARK)
    canvas.rect(0, A4[1] - 18 * mm, A4[0], 18 * mm, fill=1, stroke=0)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.setFillColor(WHITE)
    canvas.drawString(20 * mm, A4[1] - 12 * mm, "i-PRO Easy IP Setup Tool")
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(A4[0] - 20 * mm, A4[1] - 12 * mm, "User Guide")
    # Footer
    canvas.setFillColor(GREY_LINE)
    canvas.rect(0, 0, A4[0], 10 * mm, fill=1, stroke=0)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#6b7280"))
    canvas.drawString(20 * mm, 3.5 * mm, "https://github.com/Rickardjd/Easy_IP")
    canvas.drawRightString(A4[0] - 20 * mm, 3.5 * mm, f"Page {doc.page}")
    canvas.restoreState()


def on_later_pages(canvas, doc):
    on_first_page(canvas, doc)


def main():
    src = Path(__file__).parent / "USER_GUIDE.md"
    dst = Path(__file__).parent / "USER_GUIDE.pdf"

    md_text = src.read_text(encoding="utf-8")
    items = parse_md(md_text)
    story = build_story(items)

    doc = SimpleDocTemplate(
        str(dst),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=22 * mm,
        bottomMargin=14 * mm,
        title="Easy IP Setup Tool — User Guide",
        author="i-PRO Easy IP",
        subject="User Guide",
    )
    doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
    print(f"PDF written to: {dst}")


if __name__ == "__main__":
    main()
