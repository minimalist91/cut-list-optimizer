# pdf_export.py
# Generates a formatted A4 PDF of the optimized cut plan.
# - Callout labels for narrow pieces
# - Pattern breakdown table below each bar
# - Legend shows part name + length

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdf_canvas
import datetime
from collections import Counter

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
    MARGIN      = 18 * mm
    CONTENT_W   = PAGE_W - 2 * MARGIN

    CALLOUT_THRESHOLD = 18 * mm   # pieces narrower than this get callout labels
    CALLOUT_H   = 14 * mm         # space above bar for callout labels
    BAR_H       = 20 * mm         # height of the coloured bar
    BADGE_W     = 18 * mm         # width of the ×N count badge
    INFO_W      = 18 * mm         # width of the utilisation % column
    BAR_DRAW_W  = CONTENT_W - BADGE_W - INFO_W
    ROW_H       = CALLOUT_H + BAR_H  # total height of bar area per group

    c = pdf_canvas.Canvas(filepath, pagesize=A4)
    c.setTitle(f"Cut List — {job_name}")

    # ── Assign colours keyed by (name, length) ───────────────────
    # Key includes length so same-named parts with different lengths
    # get the same colour family (they're the same part type)
    part_colours = {}   # (name, length) -> rgb tuple
    name_colours = {}   # name -> rgb  (for legend, one entry per name)
    idx = 0
    for g in groups:
        for name, length in g["bar"]:
            if name not in name_colours:
                rgb = hex_to_rgb(PART_COLOURS_HEX[idx % len(PART_COLOURS_HEX)])
                name_colours[name] = rgb
                idx += 1
            part_colours[(name, length)] = name_colours[name]

    # ── Build legend data: name -> list of unique lengths ─────────
    # So the legend can show  "Leg  720 mm"  "Leg  980 mm"  etc.
    from collections import defaultdict
    legend_lengths = defaultdict(set)
    for g in groups:
        for name, length in g["bar"]:
            legend_lengths[name].add(length)

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
        c.drawCentredString(
            MARGIN + BADGE_W + BAR_DRAW_W / 2, y, "Cutting Pattern")
        c.drawCentredString(PAGE_W - MARGIN - INFO_W / 2, y, "Usage")
        return y - 5*mm

    # ── Pattern breakdown table ───────────────────────────────────
    def draw_breakdown(y, group):
        """
        Draws a small table below the bar showing:
          ■ Part Name   Length   × Qty on this bar
        for every unique piece in this pattern.
        Returns new y position.
        """
        bar     = group["bar"]
        count   = group["count"]

        # Count occurrences of each (name, length) in this bar
        piece_counts = Counter((name, length) for name, length in bar)

        TABLE_H    = 5.5 * mm    # height of each table row
        SWATCH_W   = 4  * mm
        COL1_X     = MARGIN + BADGE_W + 2*mm        # name starts here
        COL2_X     = MARGIN + BADGE_W + 60*mm       # length column
        COL3_X     = MARGIN + BADGE_W + 100*mm      # qty column
        COL4_X     = MARGIN + BADGE_W + 130*mm      # total column

        # Light grey background for the breakdown area
        total_table_h = len(piece_counts) * TABLE_H + 4*mm
        c.setFillColorRGB(0.96, 0.96, 0.96)
        c.rect(MARGIN + BADGE_W, y - total_table_h,
               BAR_DRAW_W + INFO_W, total_table_h, fill=1, stroke=0)

        # Header row
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.setFont("Helvetica-Bold", 6)
        c.drawString(COL1_X, y - 3.5*mm, "Part")
        c.drawString(COL2_X, y - 3.5*mm, "Length")
        c.drawString(COL3_X, y - 3.5*mm, "Qty per bar")
        c.drawString(COL4_X, y - 3.5*mm, f"Total cuts (×{count} bars)")

        y -= 4*mm

        for (name, length), qty in sorted(piece_counts.items(),
                                           key=lambda x: -x[1][1] if False else x[0][0]):
            rgb = part_colours.get((name, length), (0.8, 0.8, 0.8))

            # Colour swatch
            c.setFillColorRGB(*rgb)
            c.rect(COL1_X, y - TABLE_H + 1.5*mm,
                   SWATCH_W, TABLE_H - 2*mm, fill=1, stroke=0)
            c.setStrokeColorRGB(0, 0, 0)
            c.setLineWidth(0.3)
            c.rect(COL1_X, y - TABLE_H + 1.5*mm,
                   SWATCH_W, TABLE_H - 2*mm, fill=0, stroke=1)

            # Part name
            c.setFillColorRGB(0.1, 0.1, 0.1)
            c.setFont("Helvetica-Bold", 7)
            c.drawString(COL1_X + SWATCH_W + 2*mm,
                         y - TABLE_H / 2 - 1*mm, name)

            # Length
            c.setFont("Helvetica", 7)
            c.drawString(COL2_X, y - TABLE_H / 2 - 1*mm,
                         f"{length:,} mm")

            # Qty per bar
            c.setFont("Helvetica-Bold", 7)
            c.setFillColorRGB(0.122, 0.220, 0.392)
            c.drawString(COL3_X, y - TABLE_H / 2 - 1*mm, f"× {qty}")

            # Total cuts across all bars of this pattern
            c.setFillColorRGB(0.15, 0.50, 0.15)
            c.drawString(COL4_X, y - TABLE_H / 2 - 1*mm,
                         f"× {qty * count}")

            # Light divider line
            c.setStrokeColorRGB(0.8, 0.8, 0.8)
            c.setLineWidth(0.3)
            c.line(MARGIN + BADGE_W, y - TABLE_H,
                   PAGE_W - MARGIN, y - TABLE_H)

            y -= TABLE_H

        return y - 2*mm

    # ── One bar row ───────────────────────────────────────────────
    def draw_bar_row(y, group):
        bar      = group["bar"]
        count    = group["count"]
        offcut   = group["offcut"]
        usable   = stock_len - 2 * end_trim
        bar_used = sum(length for _, length in bar)
        util_pct = round(bar_used / usable * 100, 1) if usable > 0 else 0
        scale    = BAR_DRAW_W / usable if usable > 0 else 1

        bar_top    = y - CALLOUT_H
        bar_bottom = bar_top - BAR_H

        # ── Count badge ───────────────────────────────────────────
        c.setFillColorRGB(0.122, 0.220, 0.392)
        c.roundRect(
            MARGIN, bar_bottom,
            BADGE_W - 2*mm, ROW_H,
            2*mm, fill=1, stroke=0
        )
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(
            MARGIN + (BADGE_W - 2*mm) / 2,
            bar_bottom + ROW_H / 2 - 2*mm,
            f"x{count}"
        )

        # ── Piece rectangles + inside labels ──────────────────────
        callouts = []
        px = MARGIN + BADGE_W

        for name, length in bar:
            piece_w  = max(length * scale, 0.5*mm)
            rgb      = part_colours.get((name, length), (0.9, 0.9, 0.9))
            centre_x = px + piece_w / 2

            c.setFillColorRGB(*rgb)
            c.rect(px, bar_bottom, piece_w, BAR_H, fill=1, stroke=0)

            # Black divider on right edge
            c.setStrokeColorRGB(0, 0, 0)
            c.setLineWidth(0.6)
            c.line(px + piece_w, bar_bottom, px + piece_w, bar_top)

            if piece_w >= CALLOUT_THRESHOLD:
                c.setFillColorRGB(0.1, 0.1, 0.1)
                c.setFont("Helvetica-Bold", 7)
                c.drawCentredString(
                    centre_x, bar_bottom + BAR_H / 2 + 2*mm, name)
                c.setFont("Helvetica", 6.5)
                c.setFillColorRGB(0.25, 0.25, 0.25)
                c.drawCentredString(
                    centre_x, bar_bottom + BAR_H / 2 - 2*mm,
                    f"{length:,} mm")
            else:
                callouts.append((centre_x, name, f"{length:,} mm"))

            px += piece_w

        # ── Off-cut ───────────────────────────────────────────────
        offcut_w = BAR_DRAW_W - bar_used * scale
        if offcut_w > 0:
            is_waste = offcut < min_offcut
            c.setFillColorRGB(1.0, 0.88, 0.40) if is_waste \
                else c.setFillColorRGB(0.82, 0.82, 0.82)
            c.rect(px, bar_bottom, offcut_w, BAR_H, fill=1, stroke=0)
            c.setFillColorRGB(0.3, 0.3, 0.3)
            c.setFont("Helvetica", 6)
            if offcut_w > 4*mm:
                waste_label = "WASTE" if is_waste else "off-cut"
                c.drawCentredString(
                    px + offcut_w / 2,
                    bar_bottom + BAR_H / 2 + 2*mm, waste_label)
                c.drawCentredString(
                    px + offcut_w / 2,
                    bar_bottom + BAR_H / 2 - 2*mm,
                    f"{offcut:,} mm")

        # ── Outer border ──────────────────────────────────────────
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(1.2)
        c.rect(MARGIN + BADGE_W, bar_bottom,
               BAR_DRAW_W, BAR_H, fill=0, stroke=1)

        # ── Callout labels above bar ──────────────────────────────
        if callouts:
            LEVEL_0_Y = bar_top + 2*mm
            LEVEL_1_Y = bar_top + 7*mm
            levels    = [LEVEL_0_Y, LEVEL_1_Y]
            for ci, (cx, name, length_str) in enumerate(callouts):
                label_y = levels[ci % 2]
                c.setStrokeColorRGB(0.3, 0.3, 0.3)
                c.setLineWidth(0.5)
                c.line(cx, bar_top, cx, label_y)
                c.line(cx - 1.5*mm, label_y, cx + 1.5*mm, label_y)
                c.setFillColorRGB(0.1, 0.1, 0.1)
                c.setFont("Helvetica-Bold", 6)
                c.drawCentredString(cx, label_y + 2.5*mm, name)
                c.setFont("Helvetica", 5.5)
                c.setFillColorRGB(0.3, 0.3, 0.3)
                c.drawCentredString(cx, label_y - 1*mm, length_str)

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
            bar_bottom + BAR_H / 2 - 2*mm,
            f"{util_pct}%"
        )

        return bar_bottom   # return bottom of bar (breakdown goes below this)

    # ── Separator between patterns ────────────────────────────────
    def draw_separator(y):
        c.setStrokeColorRGB(0.1, 0.1, 0.1)
        c.setLineWidth(0.8)
        c.line(MARGIN, y, PAGE_W - MARGIN, y)
        return y - 5*mm

    # ── Legend ────────────────────────────────────────────────────
    def draw_legend(y):
        c.setFillColorRGB(0.2, 0.2, 0.2)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(MARGIN, y, "Part Legend")
        y -= 6*mm

        # Thin separator line under title
        c.setStrokeColorRGB(0.7, 0.7, 0.7)
        c.setLineWidth(0.4)
        c.line(MARGIN, y + 1*mm, PAGE_W - MARGIN, y + 1*mm)

        sw   = 9*mm
        sh   = 5.5*mm
        lx   = MARGIN
        col  = 0
        COLS = 3                          # 3 columns in the legend
        col_w = CONTENT_W / COLS

        for name, rgb in name_colours.items():
            lengths = sorted(legend_lengths[name])
            # One legend entry per unique length of this part
            for length in lengths:
                entry_x = MARGIN + col * col_w

                # Colour swatch
                c.setFillColorRGB(*rgb)
                c.rect(entry_x, y - sh, sw, sh, fill=1, stroke=0)
                c.setStrokeColorRGB(0, 0, 0)
                c.setLineWidth(0.4)
                c.rect(entry_x, y - sh, sw, sh, fill=0, stroke=1)

                # Part name (bold)
                c.setFillColorRGB(0.1, 0.1, 0.1)
                c.setFont("Helvetica-Bold", 7.5)
                c.drawString(entry_x + sw + 2*mm, y - 2*mm, name)

                # Length (normal weight, slightly smaller)
                c.setFont("Helvetica", 7)
                c.setFillColorRGB(0.3, 0.3, 0.3)
                c.drawString(entry_x + sw + 2*mm, y - sh + 1.5*mm,
                             f"{length:,} mm")

                col += 1
                if col >= COLS:
                    col  = 0
                    y   -= sh + 4*mm

        return y - sh - 8*mm

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
        # Estimate height needed: bar row + breakdown table
        piece_counts   = Counter((n, l) for n, l in g["bar"])
        breakdown_h    = len(piece_counts) * 5.5*mm + 6*mm
        needed_h       = ROW_H + breakdown_h + 10*mm

        if y - needed_h < BOTTOM_MARGIN:
            c.showPage()
            page_num += 1
            draw_header(page_num)
            y = PAGE_H - 30*mm - 6*mm
            y = draw_col_labels(y)

        # Draw the bar diagram — returns bottom of bar
        bar_bottom = draw_bar_row(y, g)

        # Draw breakdown table immediately below the bar
        y = draw_breakdown(bar_bottom, g)

        # Black separator between patterns (not after the last one)
        if gi < len(groups) - 1:
            if y - 2*mm > BOTTOM_MARGIN:
                y = draw_separator(y)

    # Legend on final page
    if y - 50*mm < BOTTOM_MARGIN:
        c.showPage()
        page_num += 1
        draw_header(page_num)
        y = PAGE_H - 30*mm - 10*mm

    y -= 6*mm
    draw_legend(y)
    c.save()
