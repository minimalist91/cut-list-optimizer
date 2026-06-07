# pdf_export.py
# Generates a formatted A4 PDF of the optimized cut plan.
# Uses reportlab — install with: pip3 install reportlab

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.utils import simpleSplit
import datetime

# ── Colour palette (same as the GUI) ─────────────────────────────
PART_COLOURS_HEX = [
    "#BDD7EE","#FCE4D6","#E2EFDA","#FFF2CC","#D6DCE4",
    "#F4CCFF","#D0E0E3","#FFD966","#C9DAF8","#FFD7D7",
    "#C6EFCE","#FFEB9C","#B4C6E7","#FF9999","#92D050",
    "#00B0F0","#FF6600","#C5A3FF","#00B050","#FFC000",
]

def hex_to_rgb(hex_str):
    """Convert '#RRGGBB' to a 0-1 float tuple for reportlab."""
    h = hex_str.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))


def generate_pdf(filepath, job_name, groups, stats, stock_len, end_trim, min_offcut):
    """
    filepath   = where to save the PDF e.g. '/Users/you/Desktop/cutlist.pdf'
    job_name   = string shown in the header
    groups     = list of {"bar": [...], "count": N, "offcut": mm}
    stats      = dict from optimizer
    stock_len  = int
    end_trim   = int
    min_offcut = int
    """

    # ── Page setup ────────────────────────────────────────────────
    PAGE_W, PAGE_H = A4          # 595 x 842 points (1 point = 1/72 inch)
    MARGIN  = 18 * mm
    CONTENT_W = PAGE_W - 2 * MARGIN

    c = pdf_canvas.Canvas(filepath, pagesize=A4)
    c.setTitle(f"Cut List — {job_name}")

    # ── Assign colours to part names ─────────────────────────────
    part_colours = {}
    idx = 0
    for g in groups:
        for name, _ in g["bar"]:
            if name not in part_colours:
                part_colours[name] = hex_to_rgb(
                    PART_COLOURS_HEX[idx % len(PART_COLOURS_HEX)])
                idx += 1

    # ── Helper: draw page header ──────────────────────────────────
    def draw_header(page_num):
        # Dark navy banner
        c.setFillColorRGB(0.122, 0.220, 0.392)   # #1F3864
        c.rect(0, PAGE_H - 28*mm, PAGE_W, 28*mm, fill=1, stroke=0)

        # App title
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(MARGIN, PAGE_H - 12*mm, "✂  Cut List Optimizer")

        # Job name
        c.setFont("Helvetica", 11)
        c.drawString(MARGIN, PAGE_H - 20*mm, job_name)

        # Date + page number on the right
        today = datetime.date.today().strftime("%d %B %Y")
        c.setFont("Helvetica", 9)
        c.drawRightString(PAGE_W - MARGIN, PAGE_H - 12*mm, today)
        c.drawRightString(PAGE_W - MARGIN, PAGE_H - 20*mm, f"Page {page_num}")

    # ── Helper: draw summary box ───────────────────────────────────
    def draw_summary(y):
        box_h = 22 * mm
        # Light green background
        c.setFillColorRGB(0.91, 0.96, 0.91)
        c.roundRect(MARGIN, y - box_h, CONTENT_W, box_h,
                    4*mm, fill=1, stroke=0)

        # Summary values
        items = [
            ("Total Bars",    str(stats["total_bars"])),
            ("Unique Patterns", str(stats["unique_patterns"])),
            ("Utilisation",   f"{stats['utilisation']}%"),
            ("Total Waste",   f"{stats['total_waste']:,} mm"),
            ("Stock Length",  f"{stock_len:,} mm"),
        ]
        col_w = CONTENT_W / len(items)
        for i, (label, value) in enumerate(items):
            x = MARGIN + i * col_w + col_w / 2

            c.setFillColorRGB(0.3, 0.3, 0.3)
            c.setFont("Helvetica", 7)
            c.drawCentredString(x, y - 8*mm, label)

            c.setFillColorRGB(0.1, 0.1, 0.1)
            c.setFont("Helvetica-Bold", 13)
            c.drawCentredString(x, y - 17*mm, value)

        return y - box_h - 6*mm

    # ── Helper: draw one bar pattern row ─────────────────────────
    BAR_H   = 14 * mm
    BADGE_W = 16 * mm
    INFO_W  = 14 * mm

    def draw_bar_row(y, group):
        bar    = group["bar"]
        count  = group["count"]
        offcut = group["offcut"]

        usable   = stock_len - 2 * end_trim
        bar_used = sum(length for _, length in bar)
        util_pct = round(bar_used / usable * 100, 1) if usable > 0 else 0
        bar_draw_w = CONTENT_W - BADGE_W - INFO_W
        scale    = bar_draw_w / usable if usable > 0 else 1

        # ── Count badge ───────────────────────────────────────────
        c.setFillColorRGB(0.122, 0.220, 0.392)   # navy
        c.roundRect(MARGIN, y - BAR_H, BADGE_W - 2*mm, BAR_H,
                    2*mm, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(MARGIN + (BADGE_W - 2*mm) / 2,
                            y - BAR_H / 2 - 2*mm, f"×{count}")

        # ── Piece rectangles ──────────────────────────────────────
        px = MARGIN + BADGE_W
        for name, length in bar:
            piece_w = max(length * scale, 1*mm)
            rgb     = part_colours.get(name, (0.9, 0.9, 0.9))
            c.setFillColorRGB(*rgb)
            c.rect(px, y - BAR_H, piece_w, BAR_H, fill=1, stroke=0)

            # White divider line between pieces
            c.setStrokeColorRGB(1, 1, 1)
            c.setLineWidth(0.5)
            c.line(px + piece_w, y - BAR_H, px + piece_w, y)

            # Label inside piece (if wide enough)
            if piece_w > 12 * mm:
                c.setFillColorRGB(0.15, 0.15, 0.15)
                c.setFont("Helvetica-Bold", 7)
                c.drawCentredString(px + piece_w/2, y - BAR_H/2 + 1*mm, name)
            if piece_w > 16 * mm:
                c.setFont("Helvetica", 6)
                c.setFillColorRGB(0.35, 0.35, 0.35)
                c.drawCentredString(px + piece_w/2, y - BAR_H/2 - 2.5*mm,
                                    f"{length:,} mm")
            px += piece_w

        # ── Off-cut rectangle ─────────────────────────────────────
        offcut_w = bar_draw_w - bar_used * scale
        if offcut_w > 0:
            is_waste = offcut < min_offcut
            if is_waste:
                c.setFillColorRGB(1.0, 0.88, 0.40)   # yellow = waste
            else:
                c.setFillColorRGB(0.82, 0.82, 0.82)   # grey = usable
            c.rect(px, y - BAR_H, offcut_w, BAR_H, fill=1, stroke=0)
            if offcut_w > 8 * mm:
                c.setFillColorRGB(0.4, 0.4, 0.4)
                c.setFont("Helvetica", 6)
                c.drawCentredString(px + offcut_w/2, y - BAR_H/2 - 1*mm,
                                    f"{offcut:,}mm")

        # ── Outer border around whole bar ─────────────────────────
        c.setStrokeColorRGB(0.75, 0.75, 0.75)
        c.setLineWidth(0.4)
        c.rect(MARGIN + BADGE_W, y - BAR_H, bar_draw_w, BAR_H,
               fill=0, stroke=1)

        # ── Utilisation % on the right ────────────────────────────
        if util_pct >= 85:
            c.setFillColorRGB(0.15, 0.68, 0.38)    # green
        elif util_pct >= 65:
            c.setFillColorRGB(0.90, 0.49, 0.13)    # orange
        else:
            c.setFillColorRGB(0.91, 0.30, 0.24)    # red
        c.setFont("Helvetica-Bold", 9)
        info_x = MARGIN + BADGE_W + bar_draw_w + INFO_W / 2
        c.drawCentredString(info_x, y - BAR_H/2 - 1.5*mm, f"{util_pct}%")

        return y - BAR_H - 4*mm   # return new y position

    # ── Helper: draw legend ───────────────────────────────────────
    def draw_legend(y):
        c.setFillColorRGB(0.2, 0.2, 0.2)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(MARGIN, y, "Part Legend:")
        y -= 5*mm

        lx  = MARGIN
        sw  = 8 * mm    # swatch width
        sh  = 4 * mm    # swatch height

        for name, rgb in part_colours.items():
            # Swatch
            c.setFillColorRGB(*rgb)
            c.rect(lx, y - sh, sw, sh, fill=1, stroke=0)
            c.setStrokeColorRGB(0.6, 0.6, 0.6)
            c.setLineWidth(0.3)
            c.rect(lx, y - sh, sw, sh, fill=0, stroke=1)

            # Name
            c.setFillColorRGB(0.2, 0.2, 0.2)
            c.setFont("Helvetica", 7)
            c.drawString(lx + sw + 2*mm, y - sh/2 - 1*mm, name)

            lx += sw + len(name) * 3.5 + 10*mm

            # Wrap to next line if near edge
            if lx > PAGE_W - MARGIN - 30*mm:
                lx  = MARGIN
                y  -= sh + 3*mm

        return y - sh - 6*mm

    # ── Draw column labels ────────────────────────────────────────
    def draw_col_labels(y):
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(MARGIN + BADGE_W/2, y, "Count")
        c.drawRightString(PAGE_W - MARGIN + 2*mm, y, "Usage")
        return y - 4*mm

    # ═══════════════════════════════════════════════════════════════
    #  RENDER PAGES
    # ═══════════════════════════════════════════════════════════════
    page_num = 1
    draw_header(page_num)

    # Start y position below header
    y = PAGE_H - 30*mm - 6*mm

    # Summary box on first page only
    y = draw_summary(y)
    y -= 4*mm

    # Column labels
    y = draw_col_labels(y)

    BOTTOM_MARGIN = 20*mm   # stop before the bottom of the page

    for g in groups:
        # Check if this bar row fits on the current page
        if y - BAR_H < BOTTOM_MARGIN:
            # Start a new page
            c.showPage()
            page_num += 1
            draw_header(page_num)
            y = PAGE_H - 30*mm - 6*mm
            y = draw_col_labels(y)

        y = draw_bar_row(y, g)

    # Legend — start new page if not enough room
    if y - 30*mm < BOTTOM_MARGIN:
        c.showPage()
        page_num += 1
        draw_header(page_num)
        y = PAGE_H - 30*mm - 10*mm

    y -= 4*mm
    draw_legend(y)

    c.save()