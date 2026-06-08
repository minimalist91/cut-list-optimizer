# main.py
# Cut List Optimizer - Desktop GUI
# Canvas-based rendering for speed. Identical bar patterns grouped with x count.

import customtkinter as ctk
from tkinter import Canvas, Scrollbar
from optimizer import optimize

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

PART_COLOURS = [
    "#BDD7EE","#FCE4D6","#E2EFDA","#FFF2CC","#D6DCE4",
    "#F4CCFF","#D0E0E3","#FFD966","#C9DAF8","#FFD7D7",
    "#C6EFCE","#FFEB9C","#B4C6E7","#FF9999","#92D050",
    "#00B0F0","#FF6600","#C5A3FF","#00B050","#FFC000",
]


class CutListApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("Cut List Optimizer")
        self.geometry("1200x750")
        self.minsize(950, 600)

        self.part_rows    = []
        self.part_colours = {}

        # Storage for last optimizer run (used by PDF)
        self._last_groups     = None
        self._last_stats      = None
        self._last_stock_len  = 3000
        self._last_end_trim   = 5
        self._last_min_offcut = 50

        self._build_header()
        self._build_settings()
        self._build_main_area()
        self._build_footer()

        for _ in range(5):
            self._add_part_row()

    # ── HEADER ────────────────────────────────────────────────────
    def _build_header(self):
        h = ctk.CTkFrame(self, height=55, corner_radius=0)
        h.pack(fill="x")
        h.pack_propagate(False)
        ctk.CTkLabel(
            h, text="✂  Cut List Optimizer",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="white"
        ).pack(side="left", padx=20, pady=10)
        ctk.CTkLabel(
            h, text="Identical bar patterns grouped automatically",
            font=ctk.CTkFont(size=11),
            text_color="#ccddff"
        ).pack(side="left")

    # ── SETTINGS BAR ──────────────────────────────────────────────
    def _build_settings(self):
        bar = ctk.CTkFrame(self, height=65, fg_color="#f0f4f8", corner_radius=0)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        def field(parent, label, default, width=90):
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.pack(side="left", padx=15, pady=8)
            ctk.CTkLabel(
                f, text=label,
                font=ctk.CTkFont(size=11),
                text_color="#555"
            ).pack(anchor="w")
            e = ctk.CTkEntry(f, width=width, height=28)
            e.insert(0, default)
            e.pack()
            return e

        self.input_job_name   = field(bar, "Job Name", "My Cut List Job", width=200)
        self.input_stock_len  = field(bar, "Stock Length (mm)", "3000")
        self.input_kerf       = field(bar, "Blade Kerf (mm)", "3")
        self.input_min_offcut = field(bar, "Min Off-cut (mm)", "50")
        self.input_end_trim   = field(bar, "End Trim (mm)", "5")

    # ── MAIN AREA ─────────────────────────────────────────────────
    def _build_main_area(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=(8, 0))
        self._build_parts_panel(container)
        self._build_results_panel(container)

    # ── LEFT: PARTS TABLE ─────────────────────────────────────────
    def _build_parts_panel(self, parent):
        panel = ctk.CTkFrame(parent, width=400)
        panel.pack(side="left", fill="both", padx=(0, 6))
        panel.pack_propagate(False)

        ctk.CTkLabel(
            panel, text="Parts List",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(10, 0))

        hdr = ctk.CTkFrame(panel, fg_color="transparent")
        hdr.pack(fill="x", padx=10, pady=(4, 0))
        for text, w in [("Part Name", 148), ("Length (mm)", 98), ("Qty", 58)]:
            ctk.CTkLabel(
                hdr, text=text, width=w,
                font=ctk.CTkFont(size=11, weight="bold"),
                anchor="w"
            ).pack(side="left", padx=2)

        self.rows_frame = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        self.rows_frame.pack(fill="both", expand=True, padx=10, pady=4)

        btns = ctk.CTkFrame(panel, fg_color="transparent")
        btns.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(
            btns, text="+ Add Row", width=110,
            command=self._add_part_row
        ).pack(side="left", padx=(0, 5))
        ctk.CTkButton(
            btns, text="✕ Clear All", width=110,
            fg_color="#e74c3c", hover_color="#c0392b",
            command=self._clear_all
        ).pack(side="left")

    def _add_part_row(self):
        row = ctk.CTkFrame(self.rows_frame, fg_color="transparent")
        row.pack(fill="x", pady=2)
        name   = ctk.CTkEntry(row, width=148, placeholder_text="Part name")
        length = ctk.CTkEntry(row, width=98,  placeholder_text="e.g. 720")
        qty    = ctk.CTkEntry(row, width=58,  placeholder_text="1")
        name.pack(side="left", padx=2)
        length.pack(side="left", padx=2)
        qty.pack(side="left", padx=2)
        ctk.CTkButton(
            row, text="✕", width=28, height=28,
            fg_color="#e74c3c", hover_color="#c0392b",
            command=lambda f=row: self._delete_row(f)
        ).pack(side="left", padx=2)
        self.part_rows.append({
            "frame": row, "name": name,
            "length": length, "qty": qty
        })

    def _delete_row(self, frame):
        self.part_rows = [r for r in self.part_rows if r["frame"] != frame]
        frame.destroy()

    def _clear_all(self):
        for r in self.part_rows:
            r["frame"].destroy()
        self.part_rows = []

    # ── RIGHT: RESULTS PANEL ──────────────────────────────────────
    def _build_results_panel(self, parent):
        panel = ctk.CTkFrame(parent)
        panel.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            panel, text="Optimized Cut Plan",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(10, 0))

        # Summary strip
        self.stats_bar = ctk.CTkFrame(
            panel, fg_color="#e8f4e8", corner_radius=8, height=36)
        self.stats_bar.pack(fill="x", padx=10, pady=(4, 0))
        self.stats_bar.pack_propagate(False)

        self.lbl_bars     = ctk.CTkLabel(
            self.stats_bar, text="Bars: —",
            font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_patterns = ctk.CTkLabel(
            self.stats_bar, text="Unique patterns: —",
            font=ctk.CTkFont(size=12))
        self.lbl_util     = ctk.CTkLabel(
            self.stats_bar, text="Utilisation: —",
            font=ctk.CTkFont(size=12))
        self.lbl_waste    = ctk.CTkLabel(
            self.stats_bar, text="Waste: —",
            font=ctk.CTkFont(size=12))

        for lbl in [self.lbl_bars, self.lbl_patterns,
                    self.lbl_util, self.lbl_waste]:
            lbl.pack(side="left", padx=12, pady=6)

        # Canvas + scrollbar
        canvas_frame = ctk.CTkFrame(panel, fg_color="transparent")
        canvas_frame.pack(fill="both", expand=True, padx=10, pady=6)

        self.canvas = Canvas(canvas_frame, bg="#f7f9fb", highlightthickness=0)
        self.scrollbar = Scrollbar(
            canvas_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.canvas.bind(
            "<MouseWheel>",
            lambda e: self.canvas.yview_scroll(-1*(e.delta//120), "units"))
        self.canvas.bind(
            "<Button-4>",
            lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind(
            "<Button-5>",
            lambda e: self.canvas.yview_scroll(1, "units"))

        self._canvas_placeholder()

    def _canvas_placeholder(self):
        self.canvas.delete("all")
        self.canvas.create_text(
            400, 120,
            text="Click  ▶ Run Optimizer  to see results here.",
            fill="#aaaaaa", font=("Arial", 13), anchor="center"
        )

    # ── FOOTER ────────────────────────────────────────────────────
    def _build_footer(self):
        footer = ctk.CTkFrame(self, height=55, corner_radius=0, fg_color="#f0f4f8")
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        self.run_btn = ctk.CTkButton(
            footer, text="▶  Run Optimizer",
            width=200, height=36,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#27ae60", hover_color="#219a52",
            command=self._run
        )
        self.run_btn.pack(side="left", padx=(20, 8), pady=9)

        self.pdf_btn = ctk.CTkButton(
            footer, text="⬇  Export PDF",
            width=150, height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#2980b9", hover_color="#2471a3",
            state="disabled",
            command=self._export_pdf
        )
        self.pdf_btn.pack(side="left", padx=(0, 8), pady=9)


        self.status = ctk.CTkLabel(footer, text="", font=ctk.CTkFont(size=12))
        self.status.pack(side="left", padx=10)

    # ── RUN ───────────────────────────────────────────────────────
    def _run(self):
        self.run_btn.configure(state="disabled", text="Running...")
        self.update()
        try:
            self._do_run()
        finally:
            self.run_btn.configure(state="normal", text="▶  Run Optimizer")

    def _do_run(self):
        # Read settings
        try:
            stock_len  = int(self.input_stock_len.get())
            kerf       = int(self.input_kerf.get())
            end_trim   = int(self.input_end_trim.get())
            min_offcut = int(self.input_min_offcut.get())
        except ValueError:
            self._err("Settings must all be whole numbers.")
            return

        # Read parts
        parts = []
        for row in self.part_rows:
            name   = row["name"].get().strip()
            length = row["length"].get().strip()
            qty    = row["qty"].get().strip()
            if not name and not length and not qty:
                continue
            if not name:
                self._err("A row is missing a part name.")
                return
            try:
                parts.append((name, int(length), int(qty)))
            except ValueError:
                self._err(f"Invalid length or qty for '{name}'.")
                return

        if not parts:
            self._err("Add at least one part.")
            return

        self.status.configure(text="Optimizing...", text_color="#555")
        self.update()

        groups, stats = optimize(parts, stock_len, kerf, end_trim)

        if not groups:
            self._err("No parts could be packed — check lengths vs stock length.")
            return

        # Save results for PDF/Print
        self._last_groups     = groups
        self._last_stats      = stats
        self._last_stock_len  = stock_len
        self._last_end_trim   = end_trim
        self._last_min_offcut = min_offcut

        # Assign colours to part names
        self.part_colours = {}
        idx = 0
        for g in groups:
            for name, _ in g["bar"]:
                if name not in self.part_colours:
                    self.part_colours[name] = PART_COLOURS[idx % len(PART_COLOURS)]
                    idx += 1

        # Update summary labels
        self.lbl_bars.configure(
            text=f"Total bars: {stats['total_bars']}")
        self.lbl_patterns.configure(
            text=f"Unique patterns: {stats['unique_patterns']}")
        self.lbl_util.configure(
            text=f"Utilisation: {stats['utilisation']}%")
        self.lbl_waste.configure(
            text=f"Waste: {stats['total_waste']:,} mm")

        self._draw_results(groups, stats, stock_len, end_trim, min_offcut)

        self.status.configure(
            text=f"✔ Done — {stats['total_bars']} bars in "
                 f"{stats['unique_patterns']} unique pattern(s).",
            text_color="#27ae60")

        # Enable PDF button
        self.pdf_btn.configure(state="normal")

    # ── CANVAS DRAWING ────────────────────────────────────────────
    def _draw_results(self, groups, stats, stock_len, end_trim, min_offcut):
        self.canvas.delete("all")

        PAD_X   = 16
        BAR_H   = 56
        GAP     = 14
        LABEL_W = 70
        INFO_W  = 60

        cw         = max(self.canvas.winfo_width(), 900)
        bar_draw_w = cw - PAD_X*2 - LABEL_W - INFO_W
        usable     = stock_len - 2 * end_trim

        y = 16

        for g in groups:
            bar    = g["bar"]
            count  = g["count"]
            offcut = g["offcut"]

            bar_used = sum(length for _, length in bar)
            util_pct = round(bar_used / usable * 100, 1) if usable > 0 else 0
            scale    = bar_draw_w / usable if usable > 0 else 1

            # Count badge
            bx1 = PAD_X
            bx2 = PAD_X + LABEL_W - 6
            by1 = y + 8
            by2 = y + BAR_H - 8
            self.canvas.create_rectangle(
                bx1, by1, bx2, by2,
                fill="#1F3864", outline="", width=0
            )
            self.canvas.create_text(
                (bx1+bx2)//2, (by1+by2)//2,
                text=f"×{count}",
                font=("Arial", 13, "bold"),
                fill="white", anchor="center"
            )

            # Piece rectangles
            piece_x = PAD_X + LABEL_W
            for name, length in bar:
                piece_w = max(int(length * scale), 2)
                colour  = self.part_colours.get(name, "#DDDDDD")
                self.canvas.create_rectangle(
                    piece_x, y,
                    piece_x + piece_w, y + BAR_H,
                    fill=colour, outline="#ffffff", width=1
                )
                if piece_w > 45:
                    self.canvas.create_text(
                        piece_x + piece_w//2, y + BAR_H//2 - 8,
                        text=name,
                        font=("Arial", 8, "bold"),
                        fill="#222", anchor="center",
                        width=piece_w - 6
                    )
                if piece_w > 30:
                    self.canvas.create_text(
                        piece_x + piece_w//2, y + BAR_H//2 + 9,
                        text=f"{length:,} mm",
                        font=("Arial", 7),
                        fill="#555", anchor="center"
                    )
                piece_x += piece_w

            # Off-cut rectangle
            offcut_w = bar_draw_w - int(bar_used * scale)
            if offcut_w > 0:
                is_waste    = offcut < min_offcut
                offcut_fill = "#FFE082" if is_waste else "#D0D0D0"
                offcut_lbl  = f"waste\n{offcut:,}mm" if is_waste else f"{offcut:,}mm"
                self.canvas.create_rectangle(
                    piece_x, y,
                    piece_x + offcut_w, y + BAR_H,
                    fill=offcut_fill, outline="#ffffff", width=1
                )
                if offcut_w > 24:
                    self.canvas.create_text(
                        piece_x + offcut_w//2, y + BAR_H//2,
                        text=offcut_lbl,
                        font=("Arial", 7),
                        fill="#666", anchor="center"
                    )

            # Utilisation %
            util_colour = (
                "#27ae60" if util_pct >= 85 else
                "#e67e22" if util_pct >= 65 else
                "#e74c3c"
            )
            self.canvas.create_text(
                cw - PAD_X - INFO_W//2, y + BAR_H//2,
                text=f"{util_pct}%",
                font=("Arial", 10, "bold"),
                fill=util_colour, anchor="center"
            )

            if count > 1:
                self.canvas.create_line(
                    PAD_X, y + BAR_H + 4,
                    cw - PAD_X, y + BAR_H + 4,
                    fill="#cccccc", dash=(4, 4)
                )

            y += BAR_H + GAP

        # Column labels at top
        self.canvas.create_text(
            PAD_X + LABEL_W//2, 4,
            text="Count", font=("Arial", 8, "bold"),
            fill="#888", anchor="center"
        )
        self.canvas.create_text(
            cw - PAD_X - INFO_W//2, 4,
            text="Usage", font=("Arial", 8, "bold"),
            fill="#888", anchor="center"
        )

        # Legend
        y += 8
        self.canvas.create_line(PAD_X, y, cw - PAD_X, y, fill="#dddddd")
        y += 10
        self.canvas.create_text(
            PAD_X, y, text="Part legend:",
            font=("Arial", 9, "bold"), fill="#444", anchor="w")
        y += 18

        lx = PAD_X
        for name, colour in self.part_colours.items():
            self.canvas.create_rectangle(
                lx, y, lx+14, y+14,
                fill=colour, outline="#aaa")
            self.canvas.create_text(
                lx+18, y+7, text=name,
                font=("Arial", 9), fill="#333", anchor="w")
            lx += 14 + len(name)*7 + 20
            if lx > cw - 120:
                lx  = PAD_X
                y  += 22

        y += 34
        self.canvas.configure(scrollregion=(0, 0, cw, y))

    # ── EXPORT PDF ────────────────────────────────────────────────
    def _export_pdf(self):
        if not self._last_groups:
            self._err("Run the optimizer first.")
            return

        from tkinter import filedialog
        import os

        filepath = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile=f"{self.input_job_name.get() or 'CutList'}.pdf",
            title="Save Cut List PDF"
        )
        if not filepath:
            return

        try:
            from pdf_export import generate_pdf
            generate_pdf(
                filepath   = filepath,
                job_name   = self.input_job_name.get() or "Cut List",
                groups     = self._last_groups,
                stats      = self._last_stats,
                stock_len  = self._last_stock_len,
                end_trim   = self._last_end_trim,
                min_offcut = self._last_min_offcut,
            )
            self.status.configure(
                text=f"✔ PDF saved: {os.path.basename(filepath)}",
                text_color="#2980b9")

            # Open PDF automatically
            import subprocess, sys
            if sys.platform == "darwin":
                subprocess.run(["open", filepath])
            elif sys.platform == "win32":
                os.startfile(filepath)
            else:
                subprocess.run(["xdg-open", filepath])

        except Exception as e:
            self._err(f"PDF error: {e}")


    # ── ERROR HELPER ──────────────────────────────────────────────
    def _err(self, msg):
        self.status.configure(text=f"⚠  {msg}", text_color="#e74c3c")


# ── Launch ────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = CutListApp()
    app.mainloop()
