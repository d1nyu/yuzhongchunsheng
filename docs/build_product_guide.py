#!/usr/bin/env python3
"""生成《羽中纯声 · 产品说明书》Word 文档。"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import (
    WD_ALIGN_VERTICAL,
    WD_ROW_HEIGHT_RULE,
    WD_TABLE_ALIGNMENT,
)
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
PREVIEW = ROOT / "preview"
OUT = Path(__file__).resolve().parent / "羽中纯声产品说明书-V1.0.docx"

# ---------------------------------------------------------------- design tokens
DARK = "211D1E"
MUTED = "786D6F"
FAINT = "A09597"
ACCENT = "D9364B"
ACCENT_DARK = "AD1D33"
ACCENT_SOFT = "FCEBEF"
CREAM = "FFF9F8"
BG = "F8F5F5"
BORDER = "ECE5E4"
WHITE = "FFFFFF"
GREEN = "0FA968"

HEAD_FONT = "微软雅黑"
BODY_FONT = "宋体"
CODE_FONT = "Consolas"

TEXT_WIDTH_CM = 16.6

# ---------------------------------------------------------------- xml ordering
PPR_ORDER = [
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl",
    "numPr", "suppressLineNumbers", "pBdr", "shd", "tabs", "suppressAutoHyphens",
    "kinsoku", "wordWrap", "overflowPunct", "topLinePunct", "autoSpaceDE",
    "autoSpaceDN", "bidi", "adjustRightInd", "snapToGrid", "spacing", "ind",
    "contextualSpacing", "mirrorIndents", "suppressOverlap", "jc", "textDirection",
    "textAlignment", "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr",
    "sectPr", "pPrChange",
]
RPR_ORDER = [
    "rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike",
    "dstrike", "outline", "shadow", "emboss", "imprint", "noProof", "snapToGrid",
    "vanish", "webHidden", "color", "spacing", "w", "kern", "position", "sz",
    "szCs", "highlight", "u", "effect", "bdr", "shd", "fitText", "vertAlign",
    "rtl", "cs", "em", "lang", "eastAsianLayout", "specVanish", "oMath",
]
TBLPR_ORDER = [
    "tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize",
    "tblStyleColBandSize", "tblW", "jc", "tblCellSpacing", "tblInd",
    "tblBorders", "shd", "tblLayout", "tblCellMar", "tblLook", "tblCaption",
    "tblDescription",
]
TCPR_ORDER = [
    "cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders", "shd",
    "noWrap", "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark",
]
TRPR_ORDER = [
    "cnfStyle", "divId", "gridBefore", "gridAfter", "wBefore", "wAfter",
    "cantSplit", "trHeight", "tblHeader", "tblCellSpacing", "jc", "hidden",
    "ins", "del", "trPrChange",
]


def _ordered_insert(parent, child, order):
    tag = child.tag.split("}")[1]
    index = order.index(tag) if tag in order else len(order)
    for position, existing in enumerate(list(parent)):
        etag = existing.tag.split("}")[1]
        if etag in order and order.index(etag) > index:
            parent.insert(position, child)
            return child
    parent.append(child)
    return child


def _apply_font(rpr, name: str) -> None:
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        _ordered_insert(rpr, fonts, RPR_ORDER)
    for attr in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
        key = qn("w:" + attr)
        if key in fonts.attrib:
            del fonts.attrib[key]
    fonts.set(qn("w:ascii"), name)
    fonts.set(qn("w:hAnsi"), name)
    fonts.set(qn("w:eastAsia"), name)


def _apply_spacing(rpr, points: float) -> None:
    old = rpr.find(qn("w:spacing"))
    if old is not None:
        rpr.remove(old)
    el = OxmlElement("w:spacing")
    el.set(qn("w:val"), str(int(round(points * 20))))
    _ordered_insert(rpr, el, RPR_ORDER)


def style_run(run, *, size=10.5, color=DARK, bold=False, font=BODY_FONT,
              italic=False, spacing=None):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = RGBColor.from_string(color)
    rpr = run._element.get_or_add_rPr()
    _apply_font(rpr, font)
    if spacing is not None:
        _apply_spacing(rpr, spacing)
    return run


def _p_border(paragraph, *, bottom=None, top=None, space=4):
    ppr = paragraph._p.get_or_add_pPr()
    old = ppr.find(qn("w:pBdr"))
    if old is not None:
        ppr.remove(old)
    pbdr = OxmlElement("w:pBdr")
    for edge, spec in (("top", top), ("bottom", bottom)):
        if spec is None:
            continue
        size, color = spec
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(size))
        el.set(qn("w:space"), str(space))
        el.set(qn("w:color"), color)
        pbdr.append(el)
    _ordered_insert(ppr, pbdr, PPR_ORDER)


def _shade(cell, color: str) -> None:
    tcpr = cell._tc.get_or_add_tcPr()
    old = tcpr.find(qn("w:shd"))
    if old is not None:
        tcpr.remove(old)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    _ordered_insert(tcpr, shd, TCPR_ORDER)


def _table_borders(table, color=BORDER, size=4, none=False):
    tblpr = table._tbl.tblPr
    old = tblpr.find(qn("w:tblBorders"))
    if old is not None:
        tblpr.remove(old)
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        if none:
            el.set(qn("w:val"), "nil")
        else:
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), str(size))
            el.set(qn("w:space"), "0")
            el.set(qn("w:color"), color)
        borders.append(el)
    _ordered_insert(tblpr, borders, TBLPR_ORDER)


def _cell_borders(cell, spec: dict):
    tcpr = cell._tc.get_or_add_tcPr()
    old = tcpr.find(qn("w:tcBorders"))
    if old is not None:
        tcpr.remove(old)
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        size, color = spec.get(edge, (0, BORDER))
        el = OxmlElement(f"w:{edge}")
        if not size:
            el.set(qn("w:val"), "nil")
        else:
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), str(size))
            el.set(qn("w:space"), "0")
            el.set(qn("w:color"), color)
        borders.append(el)
    _ordered_insert(tcpr, borders, TCPR_ORDER)


def _cell_margins(table, top=90, bottom=90, left=110, right=110):
    tblpr = table._tbl.tblPr
    old = tblpr.find(qn("w:tblCellMar"))
    if old is not None:
        tblpr.remove(old)
    mar = OxmlElement("w:tblCellMar")
    for edge, value in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:w"), str(value))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    _ordered_insert(tblpr, mar, TBLPR_ORDER)


def _fixed_layout(table, widths_cm):
    table.autofit = False
    tblpr = table._tbl.tblPr
    old = tblpr.find(qn("w:tblLayout"))
    if old is not None:
        tblpr.remove(old)
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    _ordered_insert(tblpr, layout, TBLPR_ORDER)

    tblw = tblpr.find(qn("w:tblW"))
    if tblw is None:
        tblw = OxmlElement("w:tblW")
        _ordered_insert(tblpr, tblw, TBLPR_ORDER)
    tblw.set(qn("w:type"), "dxa")
    tblw.set(qn("w:w"), str(int(round(sum(widths_cm) * 567))))

    for index, width in enumerate(widths_cm):
        table.columns[index].width = Cm(width)


def _row_flags(row, *, header=False, cant_split=True):
    trpr = row._tr.get_or_add_trPr()
    if cant_split:
        _ordered_insert(trpr, OxmlElement("w:cantSplit"), TRPR_ORDER)
    if header:
        _ordered_insert(trpr, OxmlElement("w:tblHeader"), TRPR_ORDER)


def _fill_cell(cell, text, *, size=9.2, color=DARK, bold=False, font=BODY_FONT,
               align=WD_ALIGN_PARAGRAPH.LEFT, line=1.35):
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    lines = str(text).split("\n")
    cell.paragraphs[0].text = ""
    for index, line_text in enumerate(lines):
        paragraph = cell.paragraphs[0] if index == 0 else cell.add_paragraph()
        paragraph.alignment = align
        fmt = paragraph.paragraph_format
        fmt.space_before = Pt(0)
        fmt.space_after = Pt(0)
        fmt.line_spacing = line
        style_run(paragraph.add_run(line_text), size=size, color=color, bold=bold, font=font)


def _spec(value):
    if isinstance(value, tuple):
        return value[0], value[1]
    return value, {}


def add_caption(number, text):
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(8)
    paragraph.paragraph_format.space_after = Pt(4)
    paragraph.paragraph_format.keep_with_next = True
    style_run(paragraph.add_run(f"表 {number}　"), size=8.5, color=ACCENT_DARK, bold=True)
    style_run(paragraph.add_run(text), size=8.5, color=MUTED, bold=True)


def add_table(rows, widths, *, header=None, caption=None, zebra=False,
              header_fill=ACCENT_SOFT, header_color=ACCENT_DARK, size=9.2,
              first_col=None, no_borders=False):
    if caption:
        add_caption(next_table_number(), caption)

    table = doc.add_table(rows=0, cols=len(widths))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _fixed_layout(table, widths)
    _table_borders(table, none=no_borders)
    _cell_margins(table)

    if header:
        row = table.add_row()
        _row_flags(row, header=True)
        row.height = Cm(0.85)
        row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
        for index, value in enumerate(header):
            cell = row.cells[index]
            cell.width = Cm(widths[index])
            _shade(cell, header_fill)
            _fill_cell(cell, value, size=size, color=header_color, bold=True)

    for row_index, values in enumerate(rows):
        row = table.add_row()
        _row_flags(row)
        for index, value in enumerate(values):
            text, opts = _spec(value)
            cell = row.cells[index]
            cell.width = Cm(widths[index])
            fill = opts.get("fill")
            if fill is None and zebra and row_index % 2 == 1:
                fill = "FDFBFB"
            if fill:
                _shade(cell, fill)
            base = first_col if (index == 0 and first_col) else {}
            _fill_cell(
                cell,
                text,
                size=opts.get("size", base.get("size", size)),
                color=opts.get("color", base.get("color", DARK)),
                bold=opts.get("bold", base.get("bold", False)),
                align=opts.get("align", base.get("align", WD_ALIGN_PARAGRAPH.LEFT)),
            )

    spacer(6)
    return table


def add_figure(path: Path, width_cm: float, number: int, caption: str):
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(8)
    paragraph.paragraph_format.space_after = Pt(2)
    paragraph.paragraph_format.keep_with_next = True
    paragraph.add_run().add_picture(str(path), width=Cm(width_cm))

    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_before = Pt(0)
    cap.paragraph_format.space_after = Pt(10)
    style_run(cap.add_run(f"图 {number}　"), size=8.5, color=ACCENT_DARK, bold=True)
    style_run(cap.add_run(caption), size=8.5, color=MUTED)


def spacer(points=6):
    paragraph = doc.add_paragraph()
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(0)
    fmt.line_spacing = Pt(points)
    style_run(paragraph.add_run(""), size=1)


def rich(paragraph, parts, *, size=10.5, color=DARK):
    if isinstance(parts, str):
        parts = [(parts, {})]
    for text, opts in parts:
        style_run(
            paragraph.add_run(text),
            size=opts.get("size", size),
            color=opts.get("color", color),
            bold=opts.get("bold", False),
            font=opts.get("font", BODY_FONT),
            spacing=opts.get("spacing"),
        )


def body(parts, *, after=7, before=0, size=10.5, color=DARK,
         align=WD_ALIGN_PARAGRAPH.LEFT, line=1.62, indent=0.0):
    paragraph = doc.add_paragraph()
    paragraph.alignment = align
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(before)
    fmt.space_after = Pt(after)
    fmt.line_spacing = line
    if indent:
        fmt.first_line_indent = Cm(indent)
    rich(paragraph, parts, size=size, color=color)
    return paragraph


def bullet(parts, *, after=4, size=10.5, color=DARK):
    paragraph = doc.add_paragraph()
    # 段落右缩进留白，避免长行触边
    fmt = paragraph.paragraph_format
    fmt.left_indent = Cm(0.62)
    fmt.first_line_indent = Cm(-0.62)
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(after)
    fmt.line_spacing = 1.55
    fmt.alignment = WD_ALIGN_PARAGRAPH.LEFT
    style_run(paragraph.add_run("•　"), size=size, color=ACCENT, bold=True)
    rich(paragraph, parts, size=size, color=color)
    return paragraph


def step(number, parts, *, after=5, size=10.5):
    paragraph = doc.add_paragraph()
    fmt = paragraph.paragraph_format
    fmt.left_indent = Cm(0.85)
    fmt.first_line_indent = Cm(-0.85)
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(after)
    fmt.line_spacing = 1.55
    fmt.alignment = WD_ALIGN_PARAGRAPH.LEFT
    style_run(paragraph.add_run(f"{number}."), size=10, color=ACCENT, bold=True,
              font=HEAD_FONT)
    style_run(paragraph.add_run("　"), size=size)
    rich(paragraph, parts, size=size)
    return paragraph


def callout(label, text, *, tone="cream", trail=8):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    _fixed_layout(table, [TEXT_WIDTH_CM])
    _table_borders(table, none=True)
    _cell_margins(table, top=130, bottom=130, left=220, right=220)
    cell = table.cell(0, 0)
    cell.width = Cm(TEXT_WIDTH_CM)
    _shade(cell, CREAM if tone == "cream" else ACCENT_SOFT)
    _cell_borders(cell, {
        "left": (18, ACCENT),
        "top": (4, "F3DDE1"),
        "right": (4, "F3DDE1"),
        "bottom": (4, "F3DDE1"),
    })
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    paragraph = cell.paragraphs[0]
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(0)
    fmt.line_spacing = 1.5
    style_run(paragraph.add_run(f"{label}　"), size=9.2, color=ACCENT_DARK, bold=True,
              font=HEAD_FONT)
    style_run(paragraph.add_run(text), size=9.4, color=DARK)
    if trail:
        spacer(trail)


def code_block(lines):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    _fixed_layout(table, [TEXT_WIDTH_CM])
    _table_borders(table, none=True)
    _cell_margins(table, top=110, bottom=110, left=200, right=160)
    cell = table.cell(0, 0)
    cell.width = Cm(TEXT_WIDTH_CM)
    _shade(cell, BG)
    _cell_borders(cell, {
        "left": (12, "D8CFCE"),
        "top": (4, BORDER),
        "right": (4, BORDER),
        "bottom": (4, BORDER),
    })
    for index, line in enumerate(lines):
        paragraph = cell.paragraphs[0] if index == 0 else cell.add_paragraph()
        fmt = paragraph.paragraph_format
        fmt.space_before = Pt(1)
        fmt.space_after = Pt(1)
        fmt.line_spacing = 1.3
        style_run(paragraph.add_run(line), size=8.6, color=DARK, font=CODE_FONT)
    spacer(8)


def h1(number, title, *, new_page=False):
    paragraph = doc.add_paragraph(style="Heading 1")
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(4 if new_page else 30)
    fmt.space_after = Pt(12)
    fmt.keep_with_next = True
    if new_page:
        fmt.page_break_before = True
    style_run(paragraph.add_run(number), size=11, color=ACCENT, bold=True,
              font=HEAD_FONT, spacing=1.5)
    style_run(paragraph.add_run("　　" + title), size=17, color=DARK, bold=True,
              font=HEAD_FONT, spacing=0.8)
    _p_border(paragraph, bottom=(8, "F3DDE1"), space=8)
    return paragraph


def h2(number, title):
    paragraph = doc.add_paragraph(style="Heading 2")
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(15)
    fmt.space_after = Pt(6)
    fmt.keep_with_next = True
    style_run(paragraph.add_run(number), size=9.5, color=ACCENT, bold=True,
              font=HEAD_FONT)
    style_run(paragraph.add_run("　" + title), size=12.5, color=DARK, bold=True,
              font=HEAD_FONT)
    return paragraph


def add_page_number_field(paragraph, instruction: str, cached: str = "1"):
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), instruction)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    fonts = OxmlElement("w:rFonts")
    fonts.set(qn("w:ascii"), HEAD_FONT)
    fonts.set(qn("w:hAnsi"), HEAD_FONT)
    fonts.set(qn("w:eastAsia"), HEAD_FONT)
    rpr.append(fonts)
    color = OxmlElement("w:color")
    color.set(qn("w:val"), MUTED)
    rpr.append(color)
    size = OxmlElement("w:sz")
    size.set(qn("w:val"), "17")
    rpr.append(size)
    run.append(rpr)
    text = OxmlElement("w:t")
    text.text = cached
    run.append(text)
    fld.append(run)
    paragraph._p.append(fld)


TABLE_COUNTER = [0]


def next_table_number():
    TABLE_COUNTER[0] += 1
    return TABLE_COUNTER[0]


# ---------------------------------------------------------------- document
doc = Document()

core = doc.core_properties
core.title = "羽中纯声 · 产品说明书"
core.subject = "Windows 桌面翻译与视频理解工具"
core.author = "羽中纯声"
core.last_modified_by = "羽中纯声"
core.category = "产品说明书"
core.comments = "基于羽中纯声 V1.0.0 编写"
core.keywords = "羽中纯声, 翻译, 语音识别, 视频理解, Whisper, OCR, DeepSeek"
core.language = "zh-CN"


def setup_styles():
    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGBColor.from_string(DARK)
    rpr = normal.element.get_or_add_rPr()
    _apply_font(rpr, BODY_FONT)
    fmt = normal.paragraph_format
    fmt.line_spacing = 1.62
    fmt.space_after = Pt(7)
    fmt.space_before = Pt(0)

    for name, size, color, before, after in (
        ("Heading 1", 17, DARK, 30, 12),
        ("Heading 2", 12.5, DARK, 15, 6),
    ):
        style = doc.styles[name]
        style.font.name = HEAD_FONT
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        _apply_font(style.element.get_or_add_rPr(), HEAD_FONT)
        pf = style.paragraph_format
        pf.space_before = Pt(before)
        pf.space_after = Pt(after)
        pf.keep_with_next = True
        pf.line_spacing = 1.25
        pf.outline_level = 0 if name == "Heading 1" else 1

    doc.styles["Heading 1"].paragraph_format.page_break_before = False

    for name in ("List Bullet", "List Number"):
        try:
            style = doc.styles[name]
            style.font.name = BODY_FONT
            style.font.size = Pt(10.5)
            _apply_font(style.element.get_or_add_rPr(), BODY_FONT)
        except KeyError:
            pass

    # 清除内置页眉样式的居中/右对齐制表位，避免页眉文字跳到版心中央
    for name in ("Header", "Footer"):
        try:
            doc.styles[name].paragraph_format.tab_stops.clear_all()
        except KeyError:
            pass


def setup_page():
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)
    section.top_margin = Cm(2.4)
    section.bottom_margin = Cm(2.2)
    section.header_distance = Cm(1.2)
    section.footer_distance = Cm(1.1)
    section.different_first_page_header_footer = True

    header = section.header.paragraphs[0]
    header.paragraph_format.tab_stops.clear_all()
    header.paragraph_format.tab_stops.add_tab_stop(
        Cm(TEXT_WIDTH_CM), WD_TAB_ALIGNMENT.RIGHT
    )
    header.paragraph_format.space_after = Pt(0)
    style_run(header.add_run("羽中纯声　·　产品说明书"), size=8, color=FAINT,
              font=HEAD_FONT, spacing=0.5)
    header.add_run("\t")
    style_run(header.add_run("V1.0.0"), size=8, color=FAINT, font=HEAD_FONT)
    _p_border(header, bottom=(4, BORDER), space=5)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.paragraph_format.space_before = Pt(0)
    style_run(footer.add_run("第 "), size=8, color=MUTED)
    add_page_number_field(footer, " PAGE ", "2")
    style_run(footer.add_run(" 页　·　共 "), size=8, color=MUTED)
    add_page_number_field(footer, " NUMPAGES ", "16")
    style_run(footer.add_run(" 页"), size=8, color=MUTED)

    first_footer = section.first_page_footer.paragraphs[0]
    first_footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    first_footer.paragraph_format.space_after = Pt(0)
    style_run(
        first_footer.add_run(
            "适用平台　Windows 10 / 11（64 位）　·　文档版本　V1.0.0　·　2026 年 11 月"
        ),
        size=8,
        color=FAINT,
        font=HEAD_FONT,
        spacing=0.4,
    )


def build_cover():
    spacer(30)
    logo = doc.add_paragraph()
    logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    logo.paragraph_format.space_before = Pt(0)
    logo.paragraph_format.space_after = Pt(0)
    logo.add_run().add_picture(str(ROOT / "docs" / "logo_white.jpg"), width=Cm(3.3))

    spacer(18)
    name = doc.add_paragraph()
    name.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name.paragraph_format.space_before = Pt(0)
    name.paragraph_format.space_after = Pt(4)
    style_run(name.add_run("羽中纯声"), size=36, color=DARK, bold=True,
              font=HEAD_FONT, spacing=7)

    tagline = doc.add_paragraph()
    tagline.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tagline.paragraph_format.space_before = Pt(0)
    tagline.paragraph_format.space_after = Pt(0)
    style_run(tagline.add_run("羽落成声　·　翻译　·　理解　·　视频辅助"), size=10.5,
              color=MUTED, font=HEAD_FONT, spacing=1.2)

    spacer(40)
    rule = doc.add_paragraph()
    rule.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rule.paragraph_format.left_indent = Cm(6.4)
    rule.paragraph_format.right_indent = Cm(6.4)
    rule.paragraph_format.space_before = Pt(0)
    rule.paragraph_format.space_after = Pt(18)
    rule.paragraph_format.line_spacing = Pt(1)
    _p_border(rule, bottom=(14, ACCENT), space=1)
    style_run(rule.add_run(""), size=1)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_before = Pt(0)
    title.paragraph_format.space_after = Pt(10)
    style_run(title.add_run("产 品 说 明 书"), size=19, color=DARK, bold=True,
              font=HEAD_FONT, spacing=5)

    english = doc.add_paragraph()
    english.alignment = WD_ALIGN_PARAGRAPH.CENTER
    english.paragraph_format.space_before = Pt(0)
    english.paragraph_format.space_after = Pt(0)
    style_run(english.add_run("PRODUCT GUIDE　·　VERSION 1.0.0"), size=8.5,
              color=FAINT, font=HEAD_FONT, spacing=3.2)

    doc.add_page_break()


def micro_label(text, english=""):
    paragraph = doc.add_paragraph()
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(10)
    style_run(paragraph.add_run(text), size=8.5, color=ACCENT_DARK, bold=True,
              font=HEAD_FONT, spacing=2.4)
    if english:
        style_run(paragraph.add_run("　" + english), size=8, color=FAINT,
                  font=HEAD_FONT, spacing=1.6)
    _p_border(paragraph, bottom=(4, BORDER), space=5)


def build_info_page():
    micro_label("文档信息", "DOCUMENT INFORMATION")

    rows = [
        ["产品名称", "羽中纯声（Yuzhong Chunsheng）"],
        ["产品类型", "Windows 桌面翻译与视频理解工具"],
        ["当前版本", "V1.0.0"],
        ["适用平台", "Windows 10 / Windows 11（64 位）"],
        ["文档类型", "产品说明书"],
        ["文档编号", "YZCS-PD-001"],
        ["更新日期", "2026 年 11 月"],
    ]
    add_table(
        rows,
        [4.0, 12.6],
        first_col={"bold": True, "color": MUTED, "fill": BG},
        no_borders=False,
    )

    spacer(14)
    label = doc.add_paragraph()
    label.paragraph_format.space_before = Pt(0)
    label.paragraph_format.space_after = Pt(12)
    style_run(label.add_run("目录"), size=19, color=DARK, bold=True, font=HEAD_FONT,
              spacing=2)
    style_run(label.add_run("　CONTENTS"), size=8, color=FAINT, font=HEAD_FONT,
              spacing=2.4)
    _p_border(label, bottom=(8, "F3DDE1"), space=6)

    toc = [
        ("01", "产品概览", "产品定位、三个场景与设计原则"),
        ("02", "核心功能", "文字、语音、选区、视频与视频理解"),
        ("03", "使用指南", "三个典型场景的操作步骤与快捷键"),
        ("04", "翻译引擎与语言", "四种引擎、密钥管理与语言目录"),
        ("05", "隐私与数据", "数据流向与本地处理边界"),
        ("06", "运行环境", "系统要求、安装步骤与性能建议"),
        ("07", "常见问题", "使用中最容易遇到的疑问"),
        ("08", "版本与支持", "版本记录与问题反馈"),
        ("A", "附录 A　数据与文件位置", "配置、日志与本地模型存放路径"),
        ("B", "附录 B　术语表", "理解本说明书需要的几个关键词"),
    ]

    for index, (number, title_text, desc) in enumerate(toc):
        entry = doc.add_paragraph()
        fmt = entry.paragraph_format
        fmt.left_indent = Cm(1.35)
        fmt.first_line_indent = Cm(-1.35)
        fmt.space_before = Pt(9 if index == 0 else 4)
        fmt.space_after = Pt(0)
        fmt.line_spacing = 1.0
        fmt.tab_stops.add_tab_stop(Cm(1.35))
        style_run(entry.add_run(number), size=10.5, color=ACCENT, bold=True,
                  font=HEAD_FONT)
        entry.add_run("\t")
        style_run(entry.add_run(title_text), size=10.5, color=DARK, bold=True,
                  font=HEAD_FONT)

        description = doc.add_paragraph()
        dfmt = description.paragraph_format
        dfmt.left_indent = Cm(1.35)
        dfmt.space_before = Pt(0)
        dfmt.space_after = Pt(0)
        dfmt.line_spacing = 1.0
        style_run(description.add_run(desc), size=8.2, color=FAINT)

    spacer(12)
    callout(
        "怎么读",
        "本说明书按「先认识、再上手、后查阅」组织。第一次使用建议从第 1、3 章读起；"
        "需要配置引擎或排查问题时，可直接跳转到第 4、7 章。",
        trail=0,
    )


# ---------------------------------------------------------------- chapter 1
def chapter_overview():
    h1("01", "产品概览", new_page=True)

    h2("1.1", "一句话认识羽中纯声")
    body(
        "羽中纯声是一款运行在 Windows 桌面的翻译与理解工具。它把「看文字」「听声音」"
        "「看视频」三件事收进同一个窗口：按一次快捷键，框选屏幕上任意一段外文，"
        "译文就会在选区旁边弹出；电脑里播放的外语视频，即使没有字幕，也能在本机完成"
        "转写、分人与翻译，并在看完后生成一份可以继续追问的总结。"
    )
    body(
        "「羽中纯声」取意于羽毛落下的轻响——不打扰，却能听见。产品也按这个标准设计："
        "能力要够强，存在感要够轻。"
    )
    callout(
        "一句话",
        "把看不懂、听不清、记不住的内容，变成看得懂、跟得上、查得到的记录。",
    )

    h2("1.2", "三个真实场景")
    body("羽中纯声不是把所有功能堆在一起的工具箱，它只围绕三个高频场景做深：", after=6)
    bullet([
        ("文字在图片里，复制不了。 ", {"bold": True, "color": DARK}),
        (
            "PDF 扫描件、课程截图、软件界面、游戏对话——选中区域，按 Ctrl + Alt + T，"
            "译文就在选区旁边弹出，不用切走当前窗口。",
            {},
        ),
    ])
    bullet([
        ("视频没有字幕，或者字幕不能复制。", {"bold": True, "color": DARK}),
        (
            "网课、发布会、访谈、外语直播，声音从电脑里出来就能用；有硬字幕的视频，"
            "也可以直接识别画面。",
            {},
        ),
    ])
    bullet([
        ("看完了，却记不住讲了什么。", {"bold": True, "color": DARK}),
        (
            "停止识别后自动生成总结：一句话结论、关键内容、分人观点、决定与待办，"
            "以及可以点击回到原片的章节时间线。",
            {},
        ),
    ])

    h2("1.3", "设计原则")
    bullet([
        ("本地优先。", {"bold": True}),
        (
            "OCR、语音识别、视频声音转写、说话人分离全部在本机完成，音频与画面不出电脑；"
            "只有需要翻译或总结的文字会发往所选引擎。",
            {},
        ),
    ])
    bullet([
        ("不打断。", {"bold": True}),
        (
            "置顶悬浮字幕、选区结果卡片和漂浮按钮都不抢焦点、不切走主窗口，"
            "让翻译出现在内容旁边，而不是另一个应用里。",
            {},
        ),
    ])
    bullet([
        ("可追溯。", {"bold": True}),
        (
            "每条字幕记录都带时间与说话人，总结中的时间引用可以点击回到原片，"
            "观点与原文一一对应。",
            {},
        ),
    ])
    bullet([
        ("诚实。", {"bold": True}),
        (
            "识别不确定、音乐重叠、多人同时说话都会明确标注；证据不足时直接说明，"
            "而不是编一个看起来完整的答案。",
            {},
        ),
    ])

    h2("1.4", "适合谁")
    body("如果你经常遇到「这门语言我不熟，但内容很重要」，羽中纯声就是为你准备的：", after=6)
    bullet("需要大量阅读外文资料的学生、研究者与知识工作者；")
    bullet("处理跨境业务，需要快速看懂外语邮件、会议与直播的从业者；")
    bullet("经常观看外语课程、访谈、发布会的内容消费者；")
    bullet("需要为视频做笔记、复盘与检索的创作者与团队。")

    h2("1.5", "产品速览")
    rows = [
        ["产品定位", "桌面级翻译与视频理解工具，偏个人与小团队使用"],
        ["运行平台", "Windows 10 / Windows 11（64 位）"],
        ["翻译引擎", "DeepSeek（默认）、Google 免费、MyMemory 免费、OpenAI 兼容"],
        ["语言支持", "源语言自动检测，130 余种目标语言"],
        ["本地能力", "OCR、语音识别、Whisper 转写、说话人分离、音乐过滤"],
        ["联网需求", "仅翻译与总结需要联网；音视频识别在本机完成"],
        ["数据存储", "只保存设置与界面状态，不保存翻译历史"],
        ["交互入口", "主窗口、桌面漂浮按钮、系统托盘、全局快捷键"],
    ]
    add_table(rows, [4.0, 12.6], first_col={"bold": True, "color": MUTED, "fill": BG},
              size=9.4, zebra=True)

    h2("1.6", "工作方式")
    body(
        "无论是屏幕上的文字，还是电脑里播放的声音，都会经过同一条处理链路："
        "先在本机把内容变成文字，再交给翻译引擎，最后以不打断的方式呈现，并沉淀成可检索的记录。",
        after=10,
    )
    flow_steps = [
        ("采集", "选区截图 / 声音回环 / 画面字幕"),
        ("本地识别", "OCR、语音识别、Whisper 转写、说话人分离"),
        ("在线翻译", "DeepSeek 等引擎逐条翻译，保留原文"),
        ("呈现", "主窗口、置顶悬浮字幕、选区结果卡片"),
        ("理解", "视频总结、分人观点、时间线与连续追问"),
    ]
    build_flow(flow_steps)


def build_flow(steps):
    widths = [3.3, 3.3, 3.3, 3.3, 3.3]
    table = doc.add_table(rows=1, cols=5)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _fixed_layout(table, widths)
    _table_borders(table, color=BORDER, size=4)
    _cell_margins(table, top=120, bottom=130, left=120, right=110)

    row = table.rows[0]
    _row_flags(row)
    row.height = Cm(2.6)
    row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST

    for index, (title_text, desc) in enumerate(steps):
        cell = row.cells[index]
        cell.width = Cm(3.3)
        _shade(cell, CREAM)
        _cell_borders(cell, {
            "top": (14, ACCENT),
            "left": (4, BORDER),
            "right": (4, BORDER),
            "bottom": (4, BORDER),
        })
        cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP

        number_paragraph = cell.paragraphs[0]
        number_paragraph.paragraph_format.space_before = Pt(0)
        number_paragraph.paragraph_format.space_after = Pt(1)
        number_paragraph.paragraph_format.line_spacing = 1.0
        style_run(number_paragraph.add_run(f"{index + 1:02d}"), size=7.8, color=ACCENT,
                  bold=True, font=HEAD_FONT, spacing=0.8)

        title_paragraph = cell.add_paragraph()
        title_paragraph.paragraph_format.space_before = Pt(0)
        title_paragraph.paragraph_format.space_after = Pt(3)
        title_paragraph.paragraph_format.line_spacing = 1.05
        style_run(title_paragraph.add_run(title_text), size=9.2, color=DARK,
                  bold=True, font=HEAD_FONT)

        desc_paragraph = cell.add_paragraph()
        desc_paragraph.paragraph_format.space_before = Pt(0)
        desc_paragraph.paragraph_format.space_after = Pt(0)
        desc_paragraph.paragraph_format.line_spacing = 1.35
        style_run(desc_paragraph.add_run(desc), size=7.6, color=MUTED)
    spacer(6)


# ---------------------------------------------------------------- chapter 2
def chapter_features():
    h1("02", "核心功能")
    body(
        "羽中纯声把能力分成三条主线：文字、语音、视频辅助。三条线共享同一套翻译引擎、"
        "语言目录与朗读能力，切换时不需要重新配置。"
    )

    h2("2.1", "功能总览")
    rows = [
        ["文字翻译", "自动检测源语言、130 余种目标语言、自动翻译、朗读与复制",
         "读文档、写邮件、查句子"],
        ["语音翻译", "本机语音识别、停顿自动断句、识别结果可修改后重新翻译",
         "面对面简单交流、口语练习"],
        ["选区翻译", "全局快捷键框选屏幕、本机 OCR、置顶结果卡片",
         "图片、扫描 PDF、软件界面、游戏"],
        ["电脑声音", "回环采集、Whisper 多语言转写、说话人分离、音乐过滤、悬浮字幕",
         "无字幕网课、访谈、发布会、外语直播"],
        ["画面字幕", "区域 OCR、字幕变化触发翻译、悬浮字幕",
         "硬字幕视频、字幕无法复制的播放器"],
        ["视频理解", "总结、分人观点、决定与待办、章节时间线、连续追问、时间跳转",
         "会议复盘、课程笔记、长视频速览"],
        ["时间同步", "浏览器扩展提供真实播放时间，桌面播放器可手动校准",
         "需要按原片时间定位"],
        ["桌面常驻", "漂浮按钮、系统托盘、后台识别",
         "边看边译、随时唤起"],
    ]
    add_table(rows, [2.7, 9.3, 4.6], header=["模块", "核心能力", "典型场景"],
              size=9.0, zebra=True)

    h2("2.2", "文字翻译")
    body(
        "在主窗口「文字翻译」中输入或粘贴内容，选择源语言（默认自动检测）与目标语言，"
        "点「翻译」或按 Ctrl + Enter。左栏是原文，右栏是译文，译文可以复制，"
        "也可以用 Windows 本地语音朗读。"
    )
    bullet("自动翻译：输入停顿后自动查询，适合边写边译、边看边查。")
    bullet("自动朗读：译文生成后自动朗读，可用来练听力、跟读或校对。")
    bullet("字数上限：单次 5000 字符，长文建议分段处理。")
    bullet("语言目录：常用语言置顶，其余 130 余种可在下拉列表中滚动选择。")
    bullet([
        ("双向对照：", {"bold": True}),
        ("左原文、右译文，随时复制或朗读，原文不会被覆盖。", {}),
    ])
    add_figure(PREVIEW / "text-translated.png", 13.6, 1,
               "文字翻译：左右对照，自动检测源语言并保留原文")

    h2("2.3", "语音翻译")
    body(
        "切到「语音翻译」，点话筒开始说话。程序使用 Windows 本地语音引擎识别，"
        "说完停顿后自动结束；识别结果可以直接修改，再点「重新翻译」。"
    )
    body(
        "识别与朗读都依赖 Windows 语音包。中文普通话通常已随系统安装；"
        "需要识别英语、日语等语言时，请在「设置 → 时间和语言 → 语言和区域 → 语音」中"
        "安装对应语音包。朗读同样需要目标语言的语音包。"
    )
    callout(
        "适用边界",
        "语音翻译适合短句、面对面简单交流与口语练习；长时间的会议、课程与访谈，"
        "请使用「视频辅助 → 电脑声音」，识别质量与记录完整度更高。",
    )

    h2("2.4", "屏幕选区翻译")
    body(
        "在任意软件中按 Ctrl + Alt + T，拖出选区，程序在本机 OCR 后，"
        "会在选区附近弹出一张置顶结果卡片，显示原文与译文。卡片不会把主窗口切到前台，"
        "可以继续手头的工作。"
    )
    bullet("小范围选区只识别框内内容，不会向外补边；OCR 前会自动放大区块以提高清晰度。")
    bullet("快捷键在程序最小化时依然有效；如果被其他软件占用，程序会给出提示。")
    bullet("结果卡片可以复制译文、朗读或关闭，也可以拖到不遮挡内容的位置。")
    add_figure(PREVIEW / "quick-popup.png", 9.6, 2,
               "选区翻译：结果卡片支持复制、朗读与拖动")
    h2("2.5", "视频辅助 · 电脑声音（无需字幕）")
    body(
        "这是羽中纯声最完整的一条链路：不需要视频有字幕，也不占用麦克风，"
        "只要声音从电脑里播放出来，就能边看边得到译文。"
    )
    step(1, "正常播放视频，确认声音从默认扬声器输出，系统没有静音。")
    step(2, "打开「视频辅助」，识别来源选择「电脑声音（无需字幕）」。")
    step(3, "点「开始识别」，程序通过 Windows 声音回环采集播放声音。")
    step(4, "本地 Whisper 自动识别语言并转写，按自然停顿断句，约 0.6 秒静音即出结果。")
    step(5, "程序自动区分说话人，按时间顺序保留每位说话人的内容。")
    step(6, "每条转写交给 DeepSeek 翻译；勾选「显示置顶悬浮字幕」可边看边读译文。")
    step(7, "停止识别后自动打开「视频理解」，生成总结并可继续追问。")

    body("几个关键设计：", before=6, after=5)
    bullet([
        ("多人对话：", {"bold": True}),
        (
            "自动标记「说话人 1」「说话人 2」，不需要预先录入声纹，也没有阈值需要调。",
            {},
        ),
    ])
    bullet([
        ("中途换语言：", {"bold": True}),
        (
            "每位说话人的语言判断与最近三句上下文分别保存。即使视频里有人中途切换语言，"
            "或不同人使用不同语言，也不会沿用上一位说话人的判断。",
            {},
        ),
    ])
    bullet([
        ("音乐与歌词：", {"bold": True}),
        (
            "纯音乐或只有歌词的段落自动跳过；歌词、音乐与对白重叠时明确标记"
            "「多人重叠，内容可能不完整」，但仍尽量识别和翻译。",
            {},
        ),
    ])
    bullet([
        ("悬浮字幕：", {"bold": True}),
        ("只显示最近 2～3 条，避免文字铺满屏幕；右上角关闭按钮可直接停止识别。", {}),
    ])
    bullet([
        ("隐私边界：", {"bold": True}),
        ("音频只在本机处理，不上传；发送给 DeepSeek 的是转写后的文字。", {}),
    ])

    add_figure(PREVIEW / "video-audio-test.png", 14.8, 3,
               "电脑声音模式：识别、翻译与悬浮字幕同步进行")
    add_figure(PREVIEW / "overlay.png", 11.4, 4,
               "置顶悬浮字幕：原文在上、译文在下，可拖动位置")

    callout(
        "识别质量",
        "结果受背景音乐、语速与口音影响。多人同时说话时，任何单音轨都无法保证每个字都还原，"
        "程序会如实标注，而不是拼成看似完整的句子。",
    )

    h2("2.6", "视频辅助 · 画面字幕")
    body(
        "如果视频本身带有清晰字幕，也可以直接识别画面。这条路径不依赖声音，"
        "适合静音观看、字幕比语音更准确的视频，或声音无法回环采集的播放器。"
    )
    step(1, "播放视频，让字幕完整出现在画面中。")
    step(2, "识别来源选择「画面字幕」。")
    step(3, "点「框选字幕区域」，拖出一个刚好覆盖字幕条的矩形。")
    step(4, "程序持续截取该区域，用本地 OCR 识别文字。")
    step(5, "字幕变化时自动调用 DeepSeek 翻译，并记录本次播放时间。")
    step(6, "勾选「显示置顶悬浮字幕」，译文显示在所有窗口上方，可拖动位置。")
    body("使用建议：", before=6, after=5)
    bullet("框选区域尽量只包含字幕，少含画面和台标，识别更快也更准。")
    bullet(
        "不要让悬浮字幕挡住框选区域，否则它可能把自己的译文再次识别进去；"
        "程序默认会把悬浮字幕放到字幕区域的反方向。"
    )
    bullet("画面字幕 OCR 目前主要支持中文与英文混合字幕；字幕越清晰、对比度越高越好。")

    h2("2.7", "视频理解与追问")
    body(
        "停止识别后，程序会自动打开「视频理解」窗口，基于本次转写与译文生成一份结构化总结："
    )
    bullet("一句话总结；")
    bullet("关键内容；")
    bullet("按说话人整理的观点、依据与分歧；")
    bullet("决定与待办；")
    bullet("识别不确定、音乐重叠或多人重叠提示；")
    bullet("带真实视频时间或本次播放时间的章节时间线。")
    body(
        "除了「刚才讲了什么」「最近五分钟」「人物观点」「决定与待办」四个快捷问题，"
        "还可以在输入框继续追问。连续追问会带上本次会话之前的问答上下文，"
        "因此可以接着问「那第二点呢」「他为什么反对」。每次重新生成整体总结时，"
        "会开始一轮新的问答上下文。",
        before=4,
    )
    body(
        "长会话会先按片段提取带时间的证据笔记，再汇总成最终结果，避免一次发送过长文本。"
        "总结只依据本次转写和译文，不会判断观点真假，也不会虚构说话人；"
        "证据不完整时，结论会明确标注。"
    )
    body(
        "时间引用有两种写法：「视频 01:23:45」会在主窗口定位记录，并让浏览器跳转到对应位置；"
        "「本次播放 03:42」只定位主窗口中的原话，表示从点击「开始识别」后经过的时间。"
    )

    h2("2.8", "播放器时间同步")
    body(
        "普通字幕记录使用的是「从开始识别算起」的相对时间。连接播放器时间同步后，"
        "字幕与总结改用视频真实播放时间，总结里的时间引用还能直接控制浏览器跳转。"
    )
    body("Chrome、Edge 与其他 Chromium 浏览器需要安装一次本地扩展：", after=5)
    step(1, "在「视频辅助」点「连接」，打开时间同步说明。")
    step(2, "点「打开扩展文件夹」，在浏览器扩展页开启「开发者模式」。")
    step(3, "点「加载已解压的扩展程序」，选择 browser_extension 文件夹。")
    step(4, "刷新正在播放视频的网页。")
    body("连接成功后：", before=5, after=5)
    bullet("视频页显示当前网页标题和绿色「时间同步」状态；")
    bullet("字幕记录使用「视频 01:23:45」格式；")
    bullet("暂停、播放和手动拖动进度后，时间会自动重新同步；")
    bullet(
        "其他桌面播放器没有统一的安全跳转接口，可点「手动同步当前时间」输入播放器时间——"
        "能正确记录和总结，但不能自动控制播放器跳转。"
    )
    body(
        "本地桥接服务只监听 127.0.0.1。浏览器扩展只发送网页标题、地址、视频总时长、"
        "当前播放时间和播放/暂停状态，不读取 Cookie 或账号信息。",
        size=9.6,
        color=MUTED,
    )

    h2("2.9", "桌面常驻与漂浮按钮")
    body(
        "程序运行后，桌面右侧会出现红色羽毛漂浮按钮：单击展开快捷菜单，双击打开主窗口，"
        "按住可以拖动，程序会记住上次的位置。"
    )
    bullet("菜单可直接进入文字翻译、语音翻译与视频辅助，也可以启动选区翻译、电脑声音识别、"
           "画面字幕识别和视频总结。")
    bullet("正在识别时，按钮右下角显示绿色状态点，菜单切换为「停止识别」。")
    bullet("开始框选屏幕区域前，漂浮按钮会暂时隐藏，避免被截进 OCR 画面。")
    body(
        "关闭主窗口时，程序会隐藏到系统托盘并继续在后台运行；正在进行的识别、"
        "全局快捷键和漂浮按钮都不会停止。恢复窗口可以双击漂浮按钮、单击托盘图标，"
        "或在漂浮菜单里选择「打开主窗口」。需要完全退出时，请在托盘或漂浮菜单底部选择"
        "「彻底退出羽中纯声」——直接关闭主窗口只表示转到后台。",
        before=4,
    )


# ---------------------------------------------------------------- chapter 3
def chapter_usage():
    h1("03", "使用指南")
    body(
        "这一章按「第一次使用」的顺序，把三个典型场景串起来。看完这一章，"
        "基本就能覆盖日常 90% 的使用。"
    )

    h2("3.1", "启动与首次设置")
    step(1, "双击工作目录里的「羽中纯声.lnk」或「启动羽中纯声.cmd」；"
            "源码方式可运行 pythonw main.py。")
    step(2, "如果换了电脑或重装 Python，先安装依赖（见 6.2）。")
    step(3, "打开右上角「设置」，选择翻译引擎。默认 DeepSeek，需要填入 API Key。")
    step(4, "如需电脑声音转写与说话人分离，运行本地模型安装脚本；首次只装 Whisper 也能用。")
    step(5, "先用一段文字测试翻译是否连通，再进入视频场景。")
    callout(
        "关于密钥",
        "DeepSeek 密钥使用 Windows DPAPI 加密，并与当前 Windows 用户绑定。"
        "换电脑或换用户后需要重新填写，这是正常的。",
    )

    h2("3.2", "场景一：读外文资料")
    body("按内容形态选择入口，不必每次都打开主窗口：", after=6)
    rows = [
        ["屏幕上的文字，无法复制", "选区翻译：Ctrl + Alt + T", "扫描件、截图、软件界面"],
        ["可以复制的文字", "文字翻译：粘贴后 Ctrl + Enter", "网页、PDF、邮件、文档"],
        ["需要原文译文对照", "文字翻译左右分栏", "精读、校对、写作"],
        ["需要听发音", "结果栏朗读，或 Ctrl + Shift + S", "听力、口语、发音确认"],
        ["只想快速看一眼", "漂浮按钮 → 选区翻译", "阅读中随时查词句"],
    ]
    add_table(rows, [5.0, 7.0, 4.6], header=["你的情况", "推荐入口", "适用内容"],
              size=9.0, zebra=True)

    h2("3.3", "场景二：看无字幕外语视频")
    step(1, "打开视频并正常播放，确认声音从默认扬声器输出。")
    step(2, "打开「视频辅助」，识别来源选「电脑声音（无需字幕）」。")
    step(3, "点「开始识别」；需要边看边读时，勾选「显示置顶悬浮字幕」。")
    step(4, "正常观看。识别结果与译文会按时间顺序进入记录区，多人内容会自动分人。")
    step(5, "看完后点「停止识别」，自动打开「视频理解」。")
    step(6, "在总结里点击时间引用回看原片，或在输入框继续追问细节。")
    callout(
        "第一次使用",
        "先在设置中运行 Whisper 模型安装脚本。低配机器可以在安装时选择 base 模型，"
        "速度更快、准确率略低；分人模型不是必需的，未安装时所有声音会统一标记为「说话人 1」。",
    )

    h2("3.4", "场景三：看有字幕的视频并做笔记")
    step(1, "让字幕完整出现在画面中，避免被播放器控制栏遮挡。")
    step(2, "识别来源选「画面字幕」，点「框选字幕区域」并拖出选区。")
    step(3, "开始识别；字幕变化时会自动翻译并记录时间。")
    step(4, "如需按原片时间定位，先在「视频辅助」连接浏览器时间同步。")
    step(5, "停止识别后查看总结，用快捷问题或自由追问整理笔记。")
    step(6, "分析结果可以一键复制，粘贴到笔记软件或文档中。")

    h2("3.5", "快捷键")
    rows = [
        ["Ctrl + Enter", "翻译当前模式的内容", "文字、语音、视频"],
        ["Ctrl + Alt + T", "全局快捷键，框选屏幕文字并翻译", "任意软件"],
        ["Ctrl + Shift + C", "复制当前译文", "主窗口"],
        ["Ctrl + Shift + S", "朗读当前译文", "主窗口"],
        ["Ctrl + L", "定位到输入区域", "主窗口"],
        ["Esc", "停止朗读或停止语音识别", "主窗口"],
    ]
    add_table(rows, [4.2, 8.0, 4.4], header=["快捷键", "功能", "适用范围"],
              size=9.2, zebra=True)


# ---------------------------------------------------------------- chapter 4
def chapter_engines():
    h1("04", "翻译引擎与语言")
    h2("4.1", "四种引擎")
    body(
        "在右上角「设置」中可以随时切换引擎，无需重启。默认使用 DeepSeek；"
        "如果没有密钥，也可以先用免费引擎体验流程。"
    )
    rows = [
        ["DeepSeek", "需要 API Key", "默认引擎，中文表达自然，适合中英互译与长文本", "日常首选"],
        ["Google 免费", "不需要", "速度快，受网络环境影响", "快速试用、连通性测试"],
        ["MyMemory 免费", "不需要", "适合 500 字符以内的短文本，可填邮箱提升额度", "短句、单词"],
        ["OpenAI 兼容", "需要", "可连接 OpenAI 或本地兼容服务", "已有账号或自建服务"],
    ]
    add_table(rows, [3.0, 2.6, 7.0, 4.0], header=["引擎", "密钥", "特点", "适用"],
              size=9.0, zebra=True)
    body(
        "如果当前引擎是 Google 或 MyMemory，但已经保存了 DeepSeek 密钥，"
        "视频总结会自动改用 DeepSeek，以保证结构化输出的质量。",
        before=4,
    )

    h2("4.2", "密钥与安全")
    body(
        "DeepSeek 密钥使用 Windows DPAPI 加密后保存在 %APPDATA%\\YiSheng\\settings.json，"
        "与当前 Windows 用户绑定，不写入源码。换电脑或换 Windows 用户后，需要重新填写。"
    )
    body(
        "内部数据目录沿用旧标识 YiSheng，是为了保留已有设置和密钥，不影响应用名称与界面。"
    )

    h2("4.3", "语言支持")
    body(
        "源语言支持自动检测，目标语言覆盖 130 余种，包括英语、日语、韩语、法语、德语、"
        "西班牙语、俄语、阿拉伯语、印地语、泰语、越南语等。常用语言置顶，"
        "其余可在完整目录中滚动选择。"
    )
    body(
        "语音识别与朗读能力取决于 Windows 已安装的语音包；视频声音转写使用本地 Whisper，"
        "可识别英语、日语、韩语、法语、德语、西班牙语等常见语言，源语言建议保持「自动检测」。"
        "画面字幕 OCR 目前主要支持中文与英文。"
    )


# ---------------------------------------------------------------- chapter 5
def chapter_privacy():
    h1("05", "隐私与数据")
    body(
        "羽中纯声的边界很明确：识别在本机，翻译在云端，密钥在本地加密。"
        "下表列出每类数据的实际去向。"
    )
    rows = [
        ["屏幕截图与 OCR 文字", "本机", ("否", {"color": GREEN, "bold": True})],
        ["麦克风语音识别", "本机（Windows 语音引擎）", ("否", {"color": GREEN, "bold": True})],
        ["电脑声音转写", "本机（Whisper / Vosk）", ("否", {"color": GREEN, "bold": True})],
        ["说话人分离与音乐过滤", "本机", ("否", {"color": GREEN, "bold": True})],
        ["待翻译的原文与译文", "所选翻译引擎（默认 DeepSeek）", ("是", {"color": ACCENT, "bold": True})],
        ["视频总结与追问记录", "DeepSeek 或 OpenAI 兼容模型", ("是", {"color": ACCENT, "bold": True})],
        ["播放状态", "本机 127.0.0.1 桥接服务", ("否", {"color": GREEN, "bold": True})],
        ["设置与密钥", "本机 DPAPI 加密", ("否", {"color": GREEN, "bold": True})],
    ]
    add_table(rows, [5.6, 7.0, 4.0],
              header=["数据类型", "处理位置", "是否离开本机"], size=9.2, zebra=True)

    body("补充说明：", before=4, after=5)
    bullet("程序不在本地保存翻译历史，只保存设置、窗口位置、漂浮按钮位置和字幕区域坐标。")
    bullet("浏览器扩展只把播放状态发送到本机 127.0.0.1 的桥接端口，不向外部服务器发送网页地址或浏览记录。")
    bullet("发送给翻译引擎的只有文字；音频、截图和视频画面都不会上传。")
    bullet("生成视频总结或追问时，带时间和说话人的本次会话记录会发送给所选模型。")
    callout(
        "建议",
        "处理敏感内容时，优先使用本地识别能力；确需翻译时，可以切换到自建的 OpenAI 兼容服务，"
        "让文字也留在可控范围内。",
    )


# ---------------------------------------------------------------- chapter 6
def chapter_environment():
    h1("06", "运行环境")
    h2("6.1", "系统要求")
    rows = [
        ["操作系统", "Windows 10 / Windows 11（64 位）"],
        ["运行方式", "双击快捷方式启动；源码方式使用 pythonw main.py"],
        ["运行时", "Python 3.10 及以上（源码运行）"],
        ["主要依赖", "PyQt5、RapidOCR、Whisper / Vosk、sherpa-onnx、webrtcvad"],
        ["网络", "翻译与总结需要联网；本地识别不需要"],
        ["硬件", "双核以上 CPU；建议 8 GB 内存；语音翻译需要麦克风"],
        ["磁盘", "程序与本地模型视所选模型而定，约数百 MB 至 1 GB"],
    ]
    add_table(rows, [4.0, 12.6], first_col={"bold": True, "color": MUTED, "fill": BG},
              size=9.2, zebra=True)

    h2("6.2", "安装与本地模型")
    body("首次使用按下面的顺序准备环境：", after=6)
    step(1, "安装 Python 3.10 及以上版本，安装时勾选「Add Python to PATH」。")
    step(2, "安装程序依赖：")
    code_block(["python -m pip install -r requirements.txt"])
    step(3, "安装 Whisper 多语言模型（默认 small，准确率更高；低配可用 base）：")
    code_block([
        "python scripts/install_whisper_model.py",
        "python scripts/install_whisper_model.py --model base",
    ])
    step(4, "安装说话人分离与音乐分类模型（多人视频与歌词过滤需要）：")
    code_block(["python scripts/install_diarization_models.py"])
    step(5, "可选：安装 Vosk 英语模型，作为 Whisper 不可用时的回退：")
    code_block(["python scripts/install_vosk_model.py"])
    step(6, "启动程序，在设置中填入翻译引擎密钥，先用文字翻译验证连通性。")

    h2("6.3", "性能与体验建议")
    bullet("视频声音模式保持默认扬声器输出、系统音量适中；回环采集的是系统混音，戴耳机同样有效，但静音会没有声音。")
    bullet("低配机器优先使用 Whisper base 模型，或减少同时运行的程序。")
    bullet("画面字幕识别只框选字幕条，避免台标、进度条和画面主体，速度和准确率都会更好。")
    bullet("悬浮字幕不要覆盖字幕区域，程序默认放在反方向；也可以手动拖到画面留白处。")
    bullet("长视频建议连接播放器时间同步，总结中的时间引用才能精确跳转。")


# ---------------------------------------------------------------- chapter 7
def chapter_faq():
    h1("07", "常见问题")

    questions = [
        (
            "视频声音模式有延迟，正常吗？",
            "系统声音需要采集、断句、转写再翻译，天然会有一小段延迟，适合连续观看。"
            "程序检测到约 0.6 秒静音就立即断句，不再使用固定 5 秒切片；"
            "暂停播放时不会继续产生字幕。",
        ),
        (
            "提示 Whisper 多语言模型未安装，怎么办？",
            "运行 python scripts/install_whisper_model.py，默认安装 small 模型；"
            "需要更快的低配版本时加 --model base。模型会安装到 "
            "%PROGRAMDATA%\\YiSheng\\models\\whisper。",
        ),
        (
            "Whisper 不可用时还能用吗？",
            "程序会回退到英语 Vosk 模型。运行 python scripts/install_vosk_model.py 安装，"
            "模型位于 %PROGRAMDATA%\\YiSheng\\models\\vosk。Vosk 只支持英语回退。",
        ),
        (
            "字幕识别不正确？",
            "尽量选择清晰、对比度高的硬字幕，不要把播放器控制栏一起框进去；"
            "OCR 目前主要支持中英文。如果字幕在变化时被遮挡，也会漏识别。",
        ),
        (
            "翻译提示无法连接？",
            "检查网络、代理和防火墙。也可以先在设置中切换到 Google 或 MyMemory 做连通性测试；"
            "如果免费引擎可用而 DeepSeek 不可用，通常是密钥或接口地址的问题。",
        ),
        (
            "没有声音朗读？",
            "译文朗读调用 Windows 本地语音。检查系统输出设备，并在 Windows「语音」设置中"
            "安装目标语言语音包。",
        ),
        (
            "语音模式提示没有识别引擎？",
            "在 Windows「设置 → 时间和语言 → 语言和区域」中添加对应语言，"
            "并在该语言的「语音」可选功能中安装语音识别包。",
        ),
        (
            "关闭窗口后程序还在运行？",
            "这是设计行为：关闭主窗口会隐藏到系统托盘，识别与快捷键继续工作。"
            "需要完全退出时，在托盘图标菜单或漂浮菜单底部选择「彻底退出羽中纯声」。",
        ),
        (
            "换了电脑，密钥需要重新填？",
            "DeepSeek 密钥使用 DPAPI 加密，与当前 Windows 用户绑定。换电脑或换用户后"
            "无法解密，需要重新填写；这是 Windows 的安全机制，不是配置丢失。",
        ),
    ]

    for index, (question, answer) in enumerate(questions, start=1):
        paragraph = doc.add_paragraph()
        fmt = paragraph.paragraph_format
        fmt.space_before = Pt(12 if index > 1 else 2)
        fmt.space_after = Pt(3)
        fmt.keep_with_next = True
        style_run(paragraph.add_run(f"Q{index}　"), size=9, color=ACCENT, bold=True,
                  font=HEAD_FONT)
        style_run(paragraph.add_run(question), size=10.5, color=DARK, bold=True,
                  font=HEAD_FONT)
        answer_paragraph = doc.add_paragraph()
        answer_paragraph.paragraph_format.left_indent = Cm(0.62)
        answer_paragraph.paragraph_format.space_before = Pt(0)
        answer_paragraph.paragraph_format.space_after = Pt(2)
        answer_paragraph.paragraph_format.line_spacing = 1.55
        answer_paragraph.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        style_run(answer_paragraph.add_run(answer), size=9.8, color=MUTED)


# ---------------------------------------------------------------- chapter 8
def chapter_release():
    h1("08", "版本与支持")
    h2("8.1", "版本记录")
    rows = [
        ["V1.0.0", "2026 年 11 月",
         "首个完整版本：文字 / 语音 / 视频三种模式，选区翻译、电脑声音转写与分人、"
         "画面字幕识别、视频理解与追问、浏览器时间同步、漂浮按钮与托盘常驻。"],
    ]
    add_table(rows, [2.4, 3.6, 10.6], header=["版本", "日期", "主要变化"], size=9.2)

    h2("8.2", "问题反馈")
    body("提交问题前，建议先确认版本号，并准备好以下信息：", after=5)
    bullet("问题现象与复现步骤；")
    bullet("Windows 版本与羽中纯声版本；")
    bullet("涉及识别质量时，说明视频来源、语言、是否有背景音乐或多人同时说话；")
    bullet("涉及崩溃或异常时，附上错误日志：%APPDATA%\\YiSheng\\error.log。")
    body(
        "本说明书基于 V1.0.0 编写。界面与功能可能随版本更新调整，"
        "以实际运行版本为准。",
        size=9.6,
        color=MUTED,
        before=6,
    )


# ---------------------------------------------------------------- appendix
def appendix_files():
    h1("A", "附录 A　数据与文件位置")
    body("羽中纯声只保存必要的配置与界面状态，所有路径都可以直接打开查看：")
    rows = [
        ["设置文件", "%APPDATA%\\YiSheng\\settings.json"],
        ["错误日志", "%APPDATA%\\YiSheng\\error.log"],
        ["Whisper 模型", "%PROGRAMDATA%\\YiSheng\\models\\whisper"],
        ["Vosk 模型", "%PROGRAMDATA%\\YiSheng\\models\\vosk"],
        ["界面与区域记忆", "设置文件内：窗口位置、漂浮按钮位置、字幕区域坐标"],
    ]
    add_table(rows, [4.2, 12.4], first_col={"bold": True, "color": MUTED, "fill": BG},
              size=9.2, zebra=True)
    body(
        "设置文件中的密钥字段是 DPAPI 加密后的密文，直接复制到其他电脑无法使用。",
        size=9.6,
        color=MUTED,
        before=2,
    )


def appendix_glossary():
    h1("B", "附录 B　术语表")
    rows = [
        ["OCR", "光学字符识别，把图片里的文字转成可编辑、可翻译的文本。"],
        ["ASR", "自动语音识别，把声音转成文字。"],
        ["Whisper", "OpenAI 开源的多语言语音识别模型，在羽中纯声里本机运行。"],
        ["Vosk", "轻量级离线语音识别引擎，作为 Whisper 不可用时的英语回退。"],
        ["说话人分离", "判断一段音频里有几个人、每句话分别是谁说的。"],
        ["声音回环", "采集电脑正在播放的声音，不经过麦克风，也不占用麦克风。"],
        ["悬浮字幕", "置顶显示在所有窗口上方的译文字幕，可拖动位置。"],
        ["DPAPI", "Windows 数据保护接口，用当前用户身份加密本地数据。"],
    ]
    add_table(rows, [4.0, 12.6], first_col={"bold": True, "color": MUTED, "fill": BG},
              size=9.2, zebra=True)
    spacer(1)


def main():
    setup_styles()
    setup_page()
    build_cover()
    build_info_page()
    chapter_overview()
    chapter_features()
    chapter_usage()
    chapter_engines()
    chapter_privacy()
    chapter_environment()
    chapter_faq()
    chapter_release()
    appendix_files()
    appendix_glossary()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(f"saved: {OUT}")


if __name__ == "__main__":
    main()
