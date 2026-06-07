# pdf_export.py
# Generates a formatted A4 PDF of the optimized cut plan.
# Uses reportlab — install with: pip3 install reportlab

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdf_canvas
import datetime

PART_COLOURS_HEX = [
    "#BDD7EE","#FCE4D6","#E2EFDA","#FFF2CC","#D6DCE4",
    "#F4CCFF","#D0E0E3","#FFD966","#C9DAF8","#FFD7D7",
    "#C6EFCE","#FFEB9C","#B4C6E7","#FF9999","#92D050",
    "#00B0F0","#FF6600","#C5A3FF","#00B050","#FFC000",
]

def hex_to_rgb(hex_str):
    h = hex_str.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))


def generate_pdf(filepath, job_name, groups, stats, stock_len, end_trim, min_offcut):

    PAGE_W, PAGE_H = A4
    MARGIN    = 18 * mm
    CONTENT_W = PAGE_W - 2 * MARGIN

    # Bar row is taller now so labels have more room
    BAR_H   = 20 * mm
    BADGE_W = 18 * mm
    INFO_W  = 18 * mm
    BAR_DRAW_W = CONTENT_W - BADGE_W - INFO_W

    c = pdf_canvas.Canvas(filepath, pagesize=A4)
    c.setTitle(f"Cut List — {job_name}")

    # Assign colours to part names
    part_colours = {}
    idx = 0
    for g in groups:
        for name, _ in g["bar"]:
            if name not in part_colours:
                part_colours[name] = hex_to_rgb(
                    PART_COLOURS_HEX[idx % len(PART_COLOURS_HEX)])
                idx += 1

    # ── Page header ───────────────────────────────────────────────
    def draw_header(page_num):
        c.setFillColorRGB(0.122, 0.220, 0.392)
        c.rect(0, PAGE_H - 28*mm, PAGE_W, 28*mm, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(MARGIN, PAGE_H - 12*mm, "Cut List Optimizer")
        c.setFont("Helvetica", 11)
        c.drawString(MARGIN, PAGE_H - 21*mm, job_name)
        today = datetime.date.today().strftime("%d %B %Y")
        c.setFont("Helvetica", 9)
        c.drawRightString(PAGE_W - MARGIN, PAGE_H - 12*mm, today)
        c.drawRightString(PAGE_W - MARGIN, PAGE_H - 21*mm, f"Page {page_num}")

    # ── Summary box ───────────────────────────────────────────────
    def draw_summary(y):
        box_h = 22 * mm
        c.setFillColorRGB(0.91, 0.96, 0.91)
        c.roundRect(MARGIN, y - box_h, CONTENT_W, box_h, 4*mm, fill=1, stroke=0)
        items = [
            ("Total Bars",      str(stats["total_bars"])),
            ("Unique Patterns", str(stats["unique_patterns"])),
            ("Utilisation",     f"{stats['utilisation']}%"),
            ("Total Waste",     f"{stats['total_waste']:,} mm"),
            ("Stock Length",    f"{stock_len:,} mm"),
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

    # ── Column labels ─────────────────────────────────────────────
    def draw_col_labels(y):
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(MARGIN + BADGE_W / 2, y, "Count")
        bar_centre = MARGIN + BADGE_W + BAR_DRAW_W / 2
        c.drawCentredString(bar_centre, y, "Cutting Pattern")
        c.drawCentredString(PAGE_W - MARGIN - INFO_W / 2, y, "Usage")
        return y - 5*mm

    # ── One bar row ───────────────────────────────────────────────
    def draw_bar_row(y, group):
        bar      = group["bar"]
        count    = group["count"]
        offcut   = group["offcut"]
        usable   = stock_len - 2 * end_trim
        bar_used = sum(length for _, length in bar)
        util_pct = round(bar_used / usable * 100, 1) if usable > 0 else 0
        scale    = BAR_DRAW_W / usable if usable > 0 else 1

        # ── Count badge ───────────────────────────────────────────
        c.setFillColorRGB(0.122, 0.220, 0.392)
        c.roundRect(
            MARGIN, y - BAR_H,
            BADGE_W - 2*mm, BAR_H,
            2*mm, fill=1, stroke=0
        )
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(
            MARGIN + (BADGE_W - 2*mm) / 2,
            y - BAR_H / 2 - 2*mm,
            f"x{count}"
        )

        # ── Piece rectangles ──────────────────────────────────────
        px = MARGIN + BADGE_W
        for name, length in bar:
            piece_w = max(length * scale, 0.5*mm)
            rgb     = part_colours.get(name, (0.9, 0.9, 0.9))

            # Filled rectangle
            c.setFillColorRGB(*rgb)
            c.rect(px, y - BAR_H, piece_w, BAR_H, fill=1, stroke=0)

            # Black border between pieces (thin vertical line on right edge)
            c.setStrokeColorRGB(0, 0, 0)
            c.setLineWidth(0.8)
            c.line(px + piece_w, y - BAR_H, px + piece_w, y)

            # Part name — always attempt to draw, clip if needed
            name_font_size = 7
            c.setFillColorRGB(0.1, 0.1, 0.1)
            c.setFont("Helvetica-Bold", name_font_size)

            # Truncate name to fit width
            max_chars = max(1, int(piece_w / (name_font_size * 0.5)))
            display_name = name if len(name) <= max_chars else name[:max_chars-1] + "…"

            if piece_w > 3*mm:
                c.drawCentredString(
                    px + piece_w / 2,
                    y - BAR_H / 2 + 2*mm,
                    display_name
                )

            # Length label below name
            c.setFont("Helvetica", 6.5)
            c.setFillColorRGB(0.25, 0.25, 0.25)
            length_str = f"{length:,} mm"
            if piece_w > 3*mm:
                c.drawCentredString(
                    px + piece_w / 2,
                    y - BAR_H / 2 - 2*mm,
                    length_str
                )

            px += piece_w

        # ── Off-cut rectangle ─────────────────────────────────────
        offcut_w = BAR_DRAW_W - bar_used * scale
        if offcut_w > 0:
            is_waste = offcut < min_offcut
            if is_waste:
                c.setFillColorRGB(1.0, 0.88, 0.40)
            else:
                c.setFillColorRGB(0.82, 0.82, 0.82)
            c.rect(px, y - BAR_H, offcut_w, BAR_H, fill=1, stroke=0)

            # Label inside off-cut
            c.setFillColorRGB(0.3, 0.3, 0.3)
            c.setFont("Helvetica", 6.5)
            waste_label = "WASTE" if is_waste else "off-cut"
            if offcut_w > 5*mm:
                c.drawCentredString(
                    px + offcut_w / 2,
                    y - BAR_H / 2 + 2*mm,
                    waste_label
                )
            if offcut_w > 5*mm:
                c.drawCentredString(
                    px + offcut_w / 2,
                    y - BAR_H / 2 - 2*mm,
                    f"{offcut:,} mm"
                )

        # ── Outer border — solid black around entire bar ──────────
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(1.2)
        c.rect(
            MARGIN + BADGE_W, y - BAR_H,
            BAR_DRAW_W, BAR_H,
            fill=0, stroke=1
        )

        # ── Utilisation % ─────────────────────────────────────────
        if util_pct >= 85:
            c.setFillColorRGB(0.15, 0.68, 0.38)
        elif util_pct >= 65:
            c.setFillColorRGB(0.90, 0.49, 0.13)
        else:
            c.setFillColorRGB(0.91, 0.30, 0.24)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(
            PAGE_W - MARGIN - INFO_W / 2,
            y - BAR_H / 2 - 2*mm,
            f"{util_pct}%"
        )

        return y - BAR_H - 6*mm   # gap between rows

    # ── Legend ────────────────────────────────────────────────────
    def draw_legend(y):
        c.setFillColorRGB(0.2, 0.2, 0.2)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(MARGIN, y, "Part Legend:")
        y -= 5*mm
        lx  = MARGIN
        sw  = 8*mm
        sh  = 5*mm
        for name, rgb in part_colours.items():
            # Colour swatch with black border
            c.setFillColorRGB(*rgb)
            c.rect(lx, y - sh, sw, sh, fill=1, stroke=0)
            c.setStrokeColorRGB(0, 0, 0)
            c.setLineWidth(0.4)
            c.rect(lx, y - sh, sw, sh, fill=0, stroke=1)
            # Name
            c.setFillColorRGB(0.1, 0.1, 0.1)
            c.setFont("Helvetica", 7.5)
            c.drawString(lx + sw + 2*mm, y - sh/2 - 1*mm, name)
            lx += sw + len(name) * 4 + 10*mm
            if lx > PAGE_W - MARGIN - 35*mm:
                lx  = MARGIN
                y  -= sh + 4*mm
        return y - sh - 8*mm

    # ── Separator line between patterns ───────────────────────────
    def draw_separator(y):
        c.setStrokeColorRGB(0.1, 0.1, 0.1)
        c.setLineWidth(0.6)
        c.line(MARGIN, y, PAGE_W - MARGIN, y)
        return y - 4*mm

    # ═══════════════════════════════════════════════════════════════
    #  RENDER PAGES
    # ═══════════════════════════════════════════════════════════════
    BOTTOM_MARGIN = 24*mm
    page_num = 1

    draw_header(page_num)
    y = PAGE_H - 30*mm - 6*mm
    y = draw_summary(y)
    y -= 4*mm
    y = draw_col_labels(y)

    for gi, g in enumerate(groups):
        # New page if not enough room for the bar row
        if y - BAR_H < BOTTOM_MARGIN:
            c.showPage()
            page_num += 1
            draw_header(page_num)
            y = PAGE_H - 30*mm - 6*mm
            y = draw_col_labels(y)

        y = draw_bar_row(y, g)

        # Draw black separator between every pattern (except after last)
        if gi < len(groups) - 1:
            if y - 2*mm > BOTTOM_MARGIN:
                y = draw_separator(y)

    # Legend
    if y - 35*mm < BOTTOM_MARGIN:
        c.showPage()
        page_num += 1
        draw_header(page_num)
        y = PAGE_H - 30*mm - 10*mm

    y -= 4*mm
    draw_legend(y)

    c.save()
