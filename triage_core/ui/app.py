try:
    import customtkinter as ctk
    UI_AVAILABLE = True
except ImportError:
    UI_AVAILABLE = False
    class ctk:
        CTk = object

import os
import uuid
import threading
import time
from ..task_ledger import TaskLedger
from ..classifier import DangerDetector, TaskClassifier
from ..sustainability import SustainabilityEstimator, PowerMonitor

# ─── Status color map ────────────────────────────────────────────────────────
_STATUS_FG = {
    "accepted":               "#166534",  # dark green
    "reviewed":               "#166534",
    "local_draft_generated":  "#1e3a5f",  # dark blue
    "handoff_generated":      "#4a1d96",  # dark purple
    "review_needed":          "#7c2d12",  # dark orange
    "blocked":                "#7f1d1d",  # dark red
    "pending":                "#1f2937",  # dark gray
}
_STATUS_BADGE = {
    "accepted":               ("#22c55e", "#000"),
    "reviewed":               ("#22c55e", "#000"),
    "local_draft_generated":  ("#3b82f6", "#fff"),
    "handoff_generated":      ("#a855f7", "#fff"),
    "review_needed":          ("#f97316", "#000"),
    "blocked":                ("#ef4444", "#fff"),
    "pending":                ("#6b7280", "#fff"),
}


def _badge_color(status):
    return _STATUS_BADGE.get(status, ("#6b7280", "#fff"))


def _card_fg(status):
    return _STATUS_FG.get(status, "#1f2937")


# ─── Small helper widgets ─────────────────────────────────────────────────────
class _SectionLabel(ctk.CTkLabel):
    def __init__(self, parent, text, **kw):
        super().__init__(parent, text=text.upper(),
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="#6b7280", **kw)


class _StatRow(ctk.CTkFrame):
    """Icon · value · sub-label on one row, used in ticker and telemetry."""
    def __init__(self, parent, icon, value, sub, **kw):
        super().__init__(parent, fg_color="transparent", **kw)
        self.icon_lbl = ctk.CTkLabel(self, text=icon, width=20,
                                     font=ctk.CTkFont(size=13))
        self.icon_lbl.pack(side="left")
        self.val_lbl = ctk.CTkLabel(self, text=value,
                                    font=ctk.CTkFont(size=13, weight="bold"))
        self.val_lbl.pack(side="left", padx=(4, 0))
        self.sub_lbl = ctk.CTkLabel(self, text=sub,
                                    font=ctk.CTkFont(size=10),
                                    text_color="#9ca3af")
        self.sub_lbl.pack(side="left", padx=(4, 0))

    def set_value(self, value):
        self.val_lbl.configure(text=value)


# ─── Main App ────────────────────────────────────────────────────────────────
class TriageDeskApp(ctk.CTk if UI_AVAILABLE else object):
    def __init__(self):
        if not UI_AVAILABLE:
            print("Error: customtkinter is not installed. Run `pip install triagecore[ui]`")
            return

        super().__init__()
        self.ledger = TaskLedger()
        self.active_backend = None
        self._current_frame = "dispatch"

        self.title("TriageDesk Control Plane")
        self.geometry("1060x680")
        self.minsize(900, 580)

        # Set icon
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(current_dir, "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._build_sidebar()
        self._build_dispatch_frame()
        self._build_ledger_frame()
        self._build_telemetry_frame()

        self.select_frame("dispatch")
        self._check_backends()
        self._start_ticker()

    # ─── Sidebar ──────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=220, corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_rowconfigure(5, weight=1)
        self.sidebar = sb

        ctk.CTkLabel(sb, text="TriageDesk",
                     font=ctk.CTkFont(size=20, weight="bold")
                     ).grid(row=0, column=0, padx=20, pady=(20, 6))

        ctk.CTkLabel(sb, text="Control Plane",
                     font=ctk.CTkFont(size=11), text_color="gray"
                     ).grid(row=1, column=0, padx=20, pady=(0, 16))

        self._nav_btns = {}
        for i, (label, key) in enumerate([("Dispatch Task", "dispatch"),
                                           ("Task Ledger", "ledger"),
                                           ("Telemetry", "telemetry")], start=2):
            btn = ctk.CTkButton(sb, text=label, anchor="w",
                                command=lambda k=key: self.select_frame(k),
                                fg_color="transparent", text_color=("gray10", "gray90"),
                                hover_color=("gray70", "gray30"))
            btn.grid(row=i, column=0, padx=12, pady=4, sticky="ew")
            self._nav_btns[key] = btn

        # ── Live Resource Ticker (bottom of sidebar) ──────────────────────────
        ticker = ctk.CTkFrame(sb, corner_radius=10, fg_color=("gray85", "gray20"))
        ticker.grid(row=6, column=0, padx=12, pady=12, sticky="sew")
        sb.grid_rowconfigure(6, weight=0)

        _SectionLabel(ticker, "Live Session").pack(anchor="w", padx=10, pady=(8, 2))

        self._t_energy   = _StatRow(ticker, "⚡", "0.000000 kWh", "energy")
        self._t_emissions = _StatRow(ticker, "💨", "0.000 gCO₂e",  "emissions")
        self._t_water    = _StatRow(ticker, "💧", "0.000 L",      "water")
        self._t_embodied = _StatRow(ticker, "🔩", "0.000 gCO₂e",  "embodied")
        for w in [self._t_energy, self._t_emissions, self._t_water, self._t_embodied]:
            w.pack(anchor="w", padx=10, pady=1)

        ctk.CTkFrame(ticker, height=1, fg_color="gray50"
                     ).pack(fill="x", padx=10, pady=4)

        self._t_backend = ctk.CTkLabel(ticker, text="Engine: checking…",
                                       font=ctk.CTkFont(size=11), text_color="gray")
        self._t_backend.pack(anchor="w", padx=10, pady=(0, 2))
        self._t_model = ctk.CTkLabel(ticker, text="Model: —",
                                     font=ctk.CTkFont(size=10), text_color="gray",
                                     wraplength=180)
        self._t_model.pack(anchor="w", padx=10, pady=(0, 8))

    # ─── Dispatch Frame ───────────────────────────────────────────────────────
    def _build_dispatch_frame(self):
        f = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(6, weight=1)
        self.dispatch_frame = f

        ctk.CTkLabel(f, text="Dispatch Task",
                     font=ctk.CTkFont(size=22, weight="bold")
                     ).grid(row=0, column=0, padx=24, pady=(20, 4), sticky="w")

        self.backend_status_label = ctk.CTkLabel(
            f, text="Checking local engines…", text_color="gray",
            font=ctk.CTkFont(size=12))
        self.backend_status_label.grid(row=1, column=0, padx=24, pady=(0, 8), sticky="w")

        self.prompt_box = ctk.CTkTextbox(f, height=120)
        self.prompt_box.grid(row=2, column=0, padx=24, pady=(0, 6), sticky="ew")
        self.prompt_box.insert("0.0", "Describe your task here…")

        self.files_entry = ctk.CTkEntry(
            f, placeholder_text="Target files (comma separated, optional)")
        self.files_entry.grid(row=3, column=0, padx=24, pady=(0, 10), sticky="ew")

        # ── 4 Dispatch Buttons ───────────────────────────────────────────────
        btn_row = ctk.CTkFrame(f, fg_color="transparent")
        btn_row.grid(row=4, column=0, padx=24, pady=(0, 6), sticky="w")

        self.btn_local = ctk.CTkButton(
            btn_row, text="⚡ Local Draft", width=140,
            command=lambda: self._handle_task("local"), fg_color="#166534")
        self.btn_local.pack(side="left", padx=(0, 8))

        self.btn_council = ctk.CTkButton(
            btn_row, text="🏭 Worker Council", width=160,
            command=lambda: self._handle_task("council"), fg_color="#0e4f6b")
        self.btn_council.pack(side="left", padx=(0, 8))

        self.btn_codex = ctk.CTkButton(
            btn_row, text="📦 Codex Packet", width=140,
            command=lambda: self._handle_task("codex"), fg_color="#7c2d12")
        self.btn_codex.pack(side="left", padx=(0, 8))

        self.btn_anti = ctk.CTkButton(
            btn_row, text="🚀 Antigravity", width=140,
            command=lambda: self._handle_task("antigravity"), fg_color="#4a1d96")
        self.btn_anti.pack(side="left")

        self.status_label = ctk.CTkLabel(f, text="", text_color="gray",
                                         font=ctk.CTkFont(size=12))
        self.status_label.grid(row=5, column=0, padx=24, pady=(0, 4), sticky="w")

        # ── Result Area ──────────────────────────────────────────────────────
        result_outer = ctk.CTkScrollableFrame(f, corner_radius=8,
                                               label_text="Result",
                                               label_font=ctk.CTkFont(size=12, weight="bold"))
        result_outer.grid(row=6, column=0, padx=24, pady=(0, 20), sticky="nsew")
        result_outer.grid_columnconfigure(0, weight=1)
        self._result_outer = result_outer

        # Metric chips row (hidden until a run completes)
        self._result_metrics = ctk.CTkFrame(result_outer, fg_color="transparent")
        self._result_metrics.grid(row=0, column=0, sticky="ew", pady=(4, 8))
        self._result_metrics.grid_remove()

        self.output_box = ctk.CTkTextbox(result_outer, height=180, state="disabled",
                                         font=ctk.CTkFont(family="Courier", size=12))
        self.output_box.grid(row=1, column=0, sticky="nsew")

    def _show_result_metrics(self, model, backend, tokens_in, tokens_out,
                              duration, energy, emissions, water, embodied):
        """Populate and show the metric chip row after a run."""
        for w in self._result_metrics.winfo_children():
            w.destroy()

        chips = [
            ("🧠", model or "—",     "model"),
            ("🖥",  backend or "—",  "backend"),
            ("🎫", f"{tokens_in}→{tokens_out}", "tokens in→out"),
            ("⏱",  f"{duration:.1f}s",   "duration"),
            ("⚡", f"{energy:.6f}",   "kWh"),
            ("💨", f"{emissions:.4f}", "gCO₂e"),
            ("💧", f"{water:.4f}",    "L water"),
            ("🔩", f"{embodied:.5f}", "gCO₂e emb."),
        ]
        for col, (icon, val, lbl) in enumerate(chips):
            chip = ctk.CTkFrame(self._result_metrics, corner_radius=8,
                                fg_color=("gray85", "gray20"))
            chip.grid(row=0, column=col, padx=4, pady=2)
            ctk.CTkLabel(chip, text=f"{icon} {val}",
                         font=ctk.CTkFont(size=12, weight="bold")
                         ).pack(padx=10, pady=(6, 0))
            ctk.CTkLabel(chip, text=lbl,
                         font=ctk.CTkFont(size=9), text_color="gray"
                         ).pack(padx=10, pady=(0, 6))

        self._result_metrics.grid()

    # ─── Ledger Frame ─────────────────────────────────────────────────────────
    def _build_ledger_frame(self):
        f = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(1, weight=1)
        self.ledger_frame = f

        hdr = ctk.CTkFrame(f, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=24, pady=(20, 8), sticky="ew")
        ctk.CTkLabel(hdr, text="Task Ledger",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")
        ctk.CTkButton(hdr, text="↻ Refresh", width=90,
                      command=self._refresh_ledger,
                      fg_color="transparent",
                      border_width=1).pack(side="right")

        self.ledger_scroll = ctk.CTkScrollableFrame(f, corner_radius=0,
                                                     fg_color="transparent")
        self.ledger_scroll.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        self.ledger_scroll.grid_columnconfigure(0, weight=1)

    def _refresh_ledger(self):
        for w in self.ledger_scroll.winfo_children():
            w.destroy()

        tasks = self.ledger.get_all_tasks()
        if not tasks:
            ctk.CTkLabel(self.ledger_scroll,
                         text="No tasks in ledger yet.",
                         text_color="gray").grid(row=0, column=0, pady=40)
            return

        for i, t in enumerate(tasks):
            status = t.status or "pending"
            fg = _card_fg(status)
            badge_bg, badge_fg = _badge_color(status)

            card = ctk.CTkFrame(self.ledger_scroll, corner_radius=10, fg_color=fg)
            card.grid(row=i, column=0, padx=4, pady=5, sticky="ew")
            card.grid_columnconfigure(1, weight=1)

            # Status badge
            badge = ctk.CTkLabel(card, text=f" {status.replace('_', ' ')} ",
                                  fg_color=badge_bg, text_color=badge_fg,
                                  corner_radius=6, font=ctk.CTkFont(size=10, weight="bold"))
            badge.grid(row=0, column=0, padx=(10, 6), pady=(8, 2), sticky="w")

            # Title
            ctk.CTkLabel(card, text=t.title or t.task_id[:12],
                         font=ctk.CTkFont(size=13, weight="bold"),
                         anchor="w").grid(row=0, column=1, pady=(8, 2), sticky="w")

            # ID chip
            ctk.CTkLabel(card, text=f"#{t.task_id[:8]}",
                         font=ctk.CTkFont(size=10), text_color="#9ca3af",
                         anchor="e").grid(row=0, column=2, padx=10, pady=(8, 2), sticky="e")

            # Meta row
            meta_parts = []
            if t.risk_level:   meta_parts.append(f"Risk: {t.risk_level}")
            if t.runner:       meta_parts.append(f"Runner: {t.runner}")
            if t.model:        meta_parts.append(f"Model: {t.model}")
            if t.backend:      meta_parts.append(f"Backend: {t.backend}")
            if meta_parts:
                ctk.CTkLabel(card, text="  ·  ".join(meta_parts),
                             font=ctk.CTkFont(size=11), text_color="#9ca3af",
                             anchor="w").grid(row=1, column=0, columnspan=3,
                                              padx=10, pady=(0, 4), sticky="w")

            # Metric strip
            total_tok = (t.estimated_input_tokens or 0) + (t.estimated_output_tokens or 0)
            metrics = [
                f"⚡ {t.energy_kwh_estimate:.6f} kWh",
                f"💨 {t.emissions_gco2e_estimate:.4f} gCO₂e",
                f"💧 {t.water_liters_estimate:.4f} L",
                f"🔩 {t.embodied_gco2e_allocated:.5f} gCO₂e emb.",
                f"🎫 {total_tok} tok",
            ]
            ctk.CTkLabel(card, text="   ".join(metrics),
                         font=ctk.CTkFont(family="Courier", size=11),
                         text_color="#d1d5db", anchor="w"
                         ).grid(row=2, column=0, columnspan=3,
                                padx=10, pady=(0, 8), sticky="w")

    # ─── Telemetry Frame ──────────────────────────────────────────────────────
    def _build_telemetry_frame(self):
        f = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        self.telemetry_frame = f

        ctk.CTkLabel(f, text="Telemetry",
                     font=ctk.CTkFont(size=22, weight="bold")
                     ).grid(row=0, column=0, padx=24, pady=(20, 4), sticky="w")

        # Session totals card
        self._telem_card = ctk.CTkFrame(f, corner_radius=12)
        self._telem_card.grid(row=1, column=0, padx=24, pady=8, sticky="ew")
        self._telem_card.grid_columnconfigure((0, 1), weight=1)

        # Per-accepted-task card
        self._per_task_card = ctk.CTkFrame(f, corner_radius=12)
        self._per_task_card.grid(row=2, column=0, padx=24, pady=8, sticky="ew")
        self._per_task_card.grid_columnconfigure((0, 1, 2), weight=1)

        # Power card
        self._power_card = ctk.CTkFrame(f, corner_radius=12)
        self._power_card.grid(row=3, column=0, padx=24, pady=(8, 24), sticky="ew")

    def _refresh_telemetry(self):
        tasks = self.ledger.get_all_tasks()
        accepted  = [t for t in tasks if t.accepted]
        n_local   = sum(1 for t in tasks if t.runner == "local_llm")
        n_codex   = sum(1 for t in tasks if t.runner == "codex")
        n_anti    = sum(1 for t in tasks if t.runner == "antigravity")
        n_council = sum(1 for t in tasks if t.runner == "worker_council")

        total_kwh      = sum(t.energy_kwh_estimate       for t in tasks)
        total_gco2     = sum(t.emissions_gco2e_estimate  for t in tasks)
        total_water    = sum(t.water_liters_estimate     for t in tasks)
        total_embodied = sum(t.embodied_gco2e_allocated  for t in tasks)
        total_tok_in   = sum(t.estimated_input_tokens    for t in tasks)
        total_tok_out  = sum(t.estimated_output_tokens   for t in tasks)
        total_review   = sum(t.human_review_minutes      for t in tasks)

        n_acc = len(accepted) or 1  # avoid div/0

        # ── Rebuild session card ──────────────────────────────────────────────
        for w in self._telem_card.winfo_children():
            w.destroy()

        _SectionLabel(self._telem_card, "Session Summary"
                      ).grid(row=0, column=0, columnspan=2, padx=16, pady=(12, 6), sticky="w")

        rows_left = [
            ("📋 Tasks",         f"{len(tasks)} total / {len(accepted)} accepted"),
            ("⚡ Energy",        f"{total_kwh:.6f} kWh"),
            ("💧 Water",         f"{total_water:.4f} L"),
            ("🔩 Embodied",      f"{total_embodied:.4f} gCO₂e"),
        ]
        rows_right = [
            ("🏃 Runners",       f"local {n_local} · council {n_council} · codex {n_codex} · anti {n_anti}"),
            ("💨 Emissions",     f"{total_gco2:.4f} gCO₂e"),
            ("🎫 Tokens",        f"{total_tok_in} in / {total_tok_out} out"),
            ("🕐 Review",        f"{total_review:.1f} min"),
        ]
        for r, (lbl, val) in enumerate(rows_left):
            ctk.CTkLabel(self._telem_card, text=lbl,
                         font=ctk.CTkFont(size=12), text_color="gray"
                         ).grid(row=r+1, column=0, padx=(16, 4), pady=3, sticky="w")
            ctk.CTkLabel(self._telem_card, text=val,
                         font=ctk.CTkFont(size=12, weight="bold")
                         ).grid(row=r+1, column=0, padx=(120, 4), pady=3, sticky="w")
        for r, (lbl, val) in enumerate(rows_right):
            ctk.CTkLabel(self._telem_card, text=lbl,
                         font=ctk.CTkFont(size=12), text_color="gray"
                         ).grid(row=r+1, column=1, padx=(16, 4), pady=3, sticky="w")
            ctk.CTkLabel(self._telem_card, text=val,
                         font=ctk.CTkFont(size=12, weight="bold")
                         ).grid(row=r+1, column=1, padx=(130, 16), pady=3, sticky="w")

        ctk.CTkFrame(self._telem_card, height=1, fg_color="gray40"
                     ).grid(row=6, column=0, columnspan=2, padx=16, pady=6, sticky="ew")

        # ── Per-accepted-task card ────────────────────────────────────────────
        for w in self._per_task_card.winfo_children():
            w.destroy()

        _SectionLabel(self._per_task_card, "Per Accepted Task (Scientific Metric)"
                      ).grid(row=0, column=0, columnspan=3, padx=16, pady=(12, 8), sticky="w")

        per_metrics = [
            ("⚡", f"{total_kwh/n_acc:.6f}", "kWh / accepted"),
            ("💨", f"{total_gco2/n_acc:.4f}", "gCO₂e / accepted"),
            ("🎫", f"{(total_tok_in+total_tok_out)//n_acc}", "tokens / accepted"),
            ("💧", f"{total_water/n_acc:.4f}", "L / accepted"),
            ("🔩", f"{total_embodied/n_acc:.5f}", "gCO₂e emb. / accepted"),
            ("🕐", f"{total_review/n_acc:.1f}", "review min / accepted"),
        ]
        for col, (icon, val, lbl) in enumerate(per_metrics):
            chip = ctk.CTkFrame(self._per_task_card, corner_radius=8,
                                fg_color=("gray85", "gray22"))
            chip.grid(row=1, column=col % 3, padx=10, pady=(0, 12), sticky="ew")
            self._per_task_card.grid_columnconfigure(col % 3, weight=1)
            ctk.CTkLabel(chip, text=f"{icon} {val}",
                         font=ctk.CTkFont(size=15, weight="bold")
                         ).pack(padx=10, pady=(8, 0))
            ctk.CTkLabel(chip, text=lbl,
                         font=ctk.CTkFont(size=10), text_color="gray"
                         ).pack(padx=10, pady=(0, 8))
            if col == 2:  # wrap to next row
                self._per_task_card.grid_rowconfigure(2, weight=0)
                for c2, (icon2, val2, lbl2) in enumerate(per_metrics[3:]):
                    chip2 = ctk.CTkFrame(self._per_task_card, corner_radius=8,
                                         fg_color=("gray85", "gray22"))
                    chip2.grid(row=2, column=c2, padx=10, pady=(0, 12), sticky="ew")
                    ctk.CTkLabel(chip2, text=f"{icon2} {val2}",
                                 font=ctk.CTkFont(size=15, weight="bold")
                                 ).pack(padx=10, pady=(8, 0))
                    ctk.CTkLabel(chip2, text=lbl2,
                                 font=ctk.CTkFont(size=10), text_color="gray"
                                 ).pack(padx=10, pady=(0, 8))
                break

        # ── Power card ────────────────────────────────────────────────────────
        for w in self._power_card.winfo_children():
            w.destroy()

        _SectionLabel(self._power_card, "Power & Hardware Status"
                      ).grid(row=0, column=0, padx=16, pady=(12, 6), sticky="w")

        power = PowerMonitor.get_status()
        if power["has_battery"]:
            plug = "AC ⚡" if power["power_plugged"] else "Battery 🔋"
            pct  = f"{power['percent']:.0f}%"
            p_str = f"{pct} · {plug}"
            color = "#22c55e" if power["power_plugged"] else (
                "#f97316" if power["percent"] > 20 else "#ef4444")
        else:
            p_str = "AC Power · No Battery Sensor"
            color = "#22c55e"

        ctk.CTkLabel(self._power_card, text=p_str,
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=color
                     ).grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

    # ─── Frame Navigation ─────────────────────────────────────────────────────
    def select_frame(self, name):
        if not UI_AVAILABLE:
            return
        self.dispatch_frame.grid_forget()
        self.ledger_frame.grid_forget()
        self.telemetry_frame.grid_forget()
        self._current_frame = name

        # Highlight active nav button
        for key, btn in self._nav_btns.items():
            if key == name:
                btn.configure(fg_color=("gray70", "gray30"))
            else:
                btn.configure(fg_color="transparent")

        if name == "dispatch":
            self.dispatch_frame.grid(row=0, column=1, sticky="nsew")
        elif name == "ledger":
            self.ledger_frame.grid(row=0, column=1, sticky="nsew")
            self._refresh_ledger()
        elif name == "telemetry":
            self.telemetry_frame.grid(row=0, column=1, sticky="nsew")
            self._refresh_telemetry()

    # ─── Live Ticker ─────────────────────────────────────────────────────────
    def _start_ticker(self):
        self._update_ticker()

    def _update_ticker(self):
        try:
            tasks = self.ledger.get_all_tasks()
            kwh      = sum(t.energy_kwh_estimate      for t in tasks)
            gco2     = sum(t.emissions_gco2e_estimate for t in tasks)
            water    = sum(t.water_liters_estimate    for t in tasks)
            embodied = sum(t.embodied_gco2e_allocated for t in tasks)

            self._t_energy.set_value(f"{kwh:.6f} kWh")
            self._t_emissions.set_value(f"{gco2:.4f} gCO₂e")
            self._t_water.set_value(f"{water:.4f} L")
            self._t_embodied.set_value(f"{embodied:.4f} gCO₂e")
        except Exception:
            pass

        self.after(5000, self._update_ticker)

    # ─── Backend Check ────────────────────────────────────────────────────────
    def _check_backends(self):
        from ..backends import create_backend
        from ..config import default_config

        def _check():
            model = default_config.get_global("backend", "default_model", "qwen2.5-coder:7b-triagecore")
            ollama = create_backend("ollama", model=model)
            if ollama.ping():
                self.active_backend = ollama
                self.backend_status_label.configure(
                    text=f"Engine: Ollama 🟢  ·  {model}", text_color="#22c55e")
                self._t_backend.configure(text="Ollama 🟢", text_color="#22c55e")
                self._t_model.configure(text=model, text_color="#93c5fd")
                return

            lmstudio = create_backend("custom", base_url="http://localhost:1234/v1", model=model)
            if lmstudio.ping():
                self.active_backend = lmstudio
                self.backend_status_label.configure(
                    text=f"Engine: LM Studio 🟢  ·  {model}", text_color="#22c55e")
                self._t_backend.configure(text="LM Studio 🟢", text_color="#22c55e")
                self._t_model.configure(text=model, text_color="#93c5fd")
                return

            self.active_backend = None
            self.backend_status_label.configure(
                text="Engine: Offline 🔴  (Start Ollama or LM Studio)", text_color="#ef4444")
            self._t_backend.configure(text="Offline 🔴", text_color="#ef4444")
            self._t_model.configure(text="—")

        threading.Thread(target=_check, daemon=True).start()

    # ─── Task Dispatch ────────────────────────────────────────────────────────
    def _handle_task(self, runner_type):
        prompt = self.prompt_box.get("0.0", "end").strip()
        files_str = self.files_entry.get().strip()
        files = [f.strip() for f in files_str.split(",") if f.strip()]

        if not prompt or prompt == "Describe your task here…":
            self.status_label.configure(text="Error: Prompt is required.", text_color="#ef4444")
            return

        task_id = str(uuid.uuid4())
        self.ledger.append_event(task_id, "task_created", {
            "title": prompt[:40] + ("…" if len(prompt) > 40 else ""),
            "description": prompt, "target_files": files
        })

        cat    = TaskClassifier.classify(prompt)
        danger = DangerDetector.analyze(prompt, files)
        self.ledger.append_event(task_id, "task_classified", {
            "category": cat, "risk_level": danger.risk_level,
            "recommended_profile": danger.recommended_profile,
            "reasons": danger.reasons
        })

        power = PowerMonitor.get_status()
        is_heavy = danger.risk_level in ["medium", "high"] or runner_type in ["local", "council"]
        if power["has_battery"] and not power["power_plugged"] and power["percent"] < 20 and is_heavy:
            self.ledger.append_event(task_id, "task_blocked", {
                "reason": f"Low battery ({power['percent']}%) without AC power."})
            self.status_label.configure(
                text=f"⚠ Deferred: Battery {power['percent']:.0f}% — plug in before heavy tasks.",
                text_color="#f97316")
            return

        if runner_type == "local":
            self._dispatch_local(task_id, prompt, files, danger)

        elif runner_type == "council":
            self._dispatch_council(task_id, prompt, files, danger)

        elif runner_type == "codex":
            self._dispatch_codex(task_id, prompt, files, danger)

        elif runner_type == "antigravity":
            self._dispatch_antigravity(task_id, prompt, files, danger)

    # -- Local --
    def _dispatch_local(self, task_id, prompt, files, danger):
        if not self.active_backend:
            self.status_label.configure(text="Error: No local engine active.", text_color="#ef4444")
            return

        self.ledger.append_event(task_id, "runner_selected", {"runner": "local_llm"})
        self.status_label.configure(
            text=f"Drafting locally via {self.active_backend.name}…", text_color="#93c5fd")
        self.btn_local.configure(state="disabled")
        self._clear_output("Sending to local model…")

        def _run():
            t0 = time.time()
            try:
                messages = [
                    {"role": "system", "content": "You are a local coding assistant. Output minimal, correct code."},
                    {"role": "user",   "content": f"Task: {prompt}\nTarget Files: {files}"}
                ]
                resp     = self.active_backend.generate(messages)
                duration = time.time() - t0
                metrics  = SustainabilityEstimator.estimate(duration_seconds=duration)

                tokens_in  = resp.usage.get("prompt_tokens",     0)
                tokens_out = resp.usage.get("completion_tokens", 0)

                self.ledger.append_event(task_id, "local_draft_generated", {
                    "status": "success", "duration_seconds": duration,
                    "backend": self.active_backend.name,
                    "model": self.active_backend.model,
                    "input_tokens": tokens_in, "output_tokens": tokens_out,
                    **metrics
                })
                self.ledger.append_event(task_id, "energy_estimated", metrics)

                self._show_result_metrics(
                    self.active_backend.model, self.active_backend.name,
                    tokens_in, tokens_out, duration,
                    metrics["energy_kwh"], metrics["emissions_gco2e"],
                    metrics["water_liters_estimate"], metrics["embodied_gco2e_allocated"])

                self._append_output("\n" + resp.text)
                self.status_label.configure(
                    text=f"✓ Draft in {duration:.1f}s · Risk: {danger.risk_level}",
                    text_color="#22c55e")
            except Exception as e:
                self.status_label.configure(text=f"Error: {e}", text_color="#ef4444")
            finally:
                self.btn_local.configure(state="normal")
                self._update_ticker()

        threading.Thread(target=_run, daemon=True).start()

    # -- Worker Council --
    def _dispatch_council(self, task_id, prompt, files, danger):
        if not self.active_backend:
            self.status_label.configure(text="Error: No local engine active.", text_color="#ef4444")
            return

        self.ledger.append_event(task_id, "runner_selected", {"runner": "worker_council"})
        self.status_label.configure(text="🏭 Dispatching to Worker Council…", text_color="#38bdf8")
        self.btn_council.configure(state="disabled")
        self._clear_output("Worker Council initialising…\n")

        def _run():
            t0 = time.time()
            try:
                from ..orchestration import ProjectManager
                pm = ProjectManager()
                self._append_output("  → RepoMapper, Validator dispatched\n")
                result = pm.dispatch_task(
                    prompt=prompt,
                    target_files=files,
                    required_roles=["repo_mapper", "validator"]
                )
                duration = time.time() - t0
                metrics  = SustainabilityEstimator.estimate(duration_seconds=duration)

                eval_data = result.get("evaluation", {})
                local_status = eval_data.get("local_result_status", "unknown")
                summary = eval_data.get("handoff_summary", "")
                packet_path = result.get("escalation_packet")

                self.ledger.append_event(task_id, "council_completed", {
                    "local_result_status": local_status,
                    "escalation_packet": packet_path,
                    "duration_seconds": duration,
                    **metrics
                })
                self.ledger.append_event(task_id, "energy_estimated", metrics)

                self._show_result_metrics(
                    self.active_backend.model if self.active_backend else "—",
                    "ollama (council)",
                    0, 0, duration,
                    metrics["energy_kwh"], metrics["emissions_gco2e"],
                    metrics["water_liters_estimate"], metrics["embodied_gco2e_allocated"])

                out = f"\nCouncil Result: {local_status.upper()}\n\n{summary}"
                if packet_path:
                    out += f"\n\n📦 Escalation packet: {packet_path}"
                self._append_output(out)

                color = "#22c55e" if local_status == "sufficient" else "#f97316"
                self.status_label.configure(
                    text=f"🏭 Council: {local_status} · {duration:.1f}s", text_color=color)
            except Exception as e:
                self.status_label.configure(text=f"Council error: {e}", text_color="#ef4444")
                self._append_output(f"\nError: {e}")
            finally:
                self.btn_council.configure(state="normal")
                self._update_ticker()

        threading.Thread(target=_run, daemon=True).start()

    # -- Codex --
    def _dispatch_codex(self, task_id, prompt, files, danger):
        from ..handoff import HandoffPacket
        from ..classifier import DangerDetector, TaskClassifier
        self.ledger.append_event(task_id, "runner_selected", {"runner": "codex"})
        os.makedirs("triage_tasks", exist_ok=True)
        filename = f"triage_tasks/codex_task_{task_id[:8]}.md"
        packet = HandoffPacket(
            title=f"Task: {prompt[:30]}", summary=prompt, context="",
            target_files=files, constraints=["Follow local codebase styling."],
            acceptance_criteria=["Tests pass."], test_commands=["pytest tests/"],
            safety_notes=danger.reasons,
            recommended_backend="Codex",
            recommended_permission_profile=danger.recommended_profile,
            risk_level=danger.risk_level)
        with open(filename, "w", encoding="utf-8") as fh:
            fh.write(packet.to_markdown())
        self.ledger.append_event(task_id, "handoff_generated", {"artifact_path": filename})
        self._clear_output(f"📦 Codex packet saved to:\n{filename}\n\nProfile: {danger.recommended_profile}")
        self.status_label.configure(
            text=f"📦 Codex packet saved · {danger.recommended_profile}", text_color="#f97316")

    # -- Antigravity --
    def _dispatch_antigravity(self, task_id, prompt, files, danger):
        from ..handoff import HandoffPacket
        self.ledger.append_event(task_id, "runner_selected", {"runner": "antigravity"})
        task_dir = f".agent_tasks/{task_id[:8]}"
        os.makedirs(task_dir, exist_ok=True)
        packet = HandoffPacket(
            title=f"Task: {prompt[:30]}", summary=prompt, context="",
            target_files=files, constraints=["Follow local codebase styling."],
            acceptance_criteria=["Tests pass."], test_commands=["pytest tests/"],
            safety_notes=danger.reasons,
            recommended_backend="Antigravity",
            recommended_permission_profile=danger.recommended_profile,
            risk_level=danger.risk_level)
        task_file = f"{task_dir}/TASK.md"
        with open(task_file, "w", encoding="utf-8") as fh:
            fh.write(packet.to_markdown())
        self.ledger.append_event(task_id, "handoff_generated", {"artifact_path": task_file})
        self._clear_output(f"🚀 Antigravity bundle saved to:\n{task_dir}/\n\nProfile: {danger.recommended_profile}")
        self.status_label.configure(
            text=f"🚀 Antigravity bundle saved · {danger.recommended_profile}", text_color="#a855f7")

    # ─── Output Box Helpers ───────────────────────────────────────────────────
    def _clear_output(self, text=""):
        self.output_box.configure(state="normal")
        self.output_box.delete("0.0", "end")
        if text:
            self.output_box.insert("0.0", text)
        self.output_box.configure(state="disabled")

    def _append_output(self, text):
        self.output_box.configure(state="normal")
        self.output_box.insert("end", text)
        self.output_box.see("end")
        self.output_box.configure(state="disabled")


# ─── Entry Point ──────────────────────────────────────────────────────────────
def run_app():
    if not UI_AVAILABLE:
        print("Error: customtkinter is not installed. Run `pip install triagecore[ui]`")
        return
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    app = TriageDeskApp()
    app.mainloop()
