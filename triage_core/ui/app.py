"""
TriageDesk GUI Application

This module provides the read-only operator console for TriageCore.
To ensure safety and prevent the GUI from becoming a hidden automation surface,
all data flow follows this strict pattern:

TriageCore modules -> triagedesk_adapter.py -> TriageDesk UI

The GUI relies on `triagedesk_adapter.py` to fetch state and perform dry-runs.
It does not execute tasks, call LLMs directly, write files, or mutate ledgers.
"""

try:
    import customtkinter as ctk

    UI_AVAILABLE = True
except ImportError:
    UI_AVAILABLE = False

    class MockBase:
        def __init__(self, *args, **kwargs):
            pass

        def pack(self, *args, **kwargs):
            pass

        def grid(self, *args, **kwargs):
            pass

    class ctk:
        CTk = MockBase
        CTkLabel = MockBase
        CTkFrame = MockBase
        CTkButton = MockBase
        CTkTextbox = MockBase
        CTkEntry = MockBase
        CTkOptionMenu = MockBase
        CTkScrollableFrame = MockBase
        CTkCanvas = MockBase
        CTkFont = MockBase

        @staticmethod
        def get_appearance_mode():
            return "Dark"

        @staticmethod
        def set_appearance_mode(mode):
            pass

        @staticmethod
        def set_default_color_theme(theme):
            pass


import os
import csv
import uuid
import threading
import time
from typing import Optional
from datetime import datetime, timezone
from ..config import default_config
from ..task_ledger import TaskLedger
from ..classifier import DangerDetector, TaskClassifier
from ..sustainability import SustainabilityEstimator, PowerMonitor
from ..context_budget import create_context_pack_artifact
from .. import token_budget

try:
    from .. import triagedesk_adapter as _td_adapter
    _TD_ADAPTER_AVAILABLE = True
except ImportError:
    _td_adapter = None
    _TD_ADAPTER_AVAILABLE = False

# ─── Status color map ────────────────────────────────────────────────────────
_STATUS_FG = {
    "accepted": "#166534",  # dark green
    "reviewed": "#166534",
    "rejected": "#7f1d1d",  # dark red
    "local_draft_generated": "#1e3a5f",  # dark blue
    "handoff_generated": "#4a1d96",  # dark purple
    "review_needed": "#7c2d12",  # dark orange
    "blocked": "#7f1d1d",  # dark red
    "pending": "#1f2937",  # dark gray
}
_STATUS_BADGE = {
    "accepted": ("#22c55e", "#000"),
    "reviewed": ("#22c55e", "#000"),
    "rejected": ("#ef4444", "#fff"),
    "local_draft_generated": ("#3b82f6", "#fff"),
    "handoff_generated": ("#a855f7", "#fff"),
    "review_needed": ("#f97316", "#000"),
    "blocked": ("#ef4444", "#fff"),
    "pending": ("#6b7280", "#fff"),
}
_LOCAL_FIRST_RUNNERS = {"local_llm", "worker_council", "pipeline"}


def _badge_color(status):
    return _STATUS_BADGE.get(status, ("#6b7280", "#fff"))


def _card_fg(status):
    return _STATUS_FG.get(status, "#1f2937")


def _ledger_dir() -> str:
    return default_config.get_ledger_dir()


def _log_file_path() -> str:
    return os.path.join(_ledger_dir(), "triagecore.log")


def _ledger_file_path() -> str:
    return os.path.join(_ledger_dir(), "ledger.jsonl")


def _ipc_inbox_path() -> str:
    return os.path.join(_ledger_dir(), "ipc_inbox.json")


def _codex_task_path(task_id: str) -> str:
    return os.path.join(default_config.get_codex_tasks_dir(), f"codex_task_{task_id[:8]}.md")


def _antigravity_task_dir(task_id: str) -> str:
    return os.path.join(default_config.get_tasks_dir(), task_id[:8])


def _telemetry_local_benefit_metrics(tasks) -> dict[str, float | int]:
    total_tasks = len(tasks)
    local_tasks = [task for task in tasks if task.runner in _LOCAL_FIRST_RUNNERS]
    accepted = [task for task in tasks if task.accepted]
    local_accepted = [task for task in local_tasks if task.accepted]
    review_light = [task for task in tasks if not task.human_review_required]
    local_tokens = sum(
        task.total_tokens
        or (
            (task.estimated_input_tokens or task.input_tokens or 0)
            + (task.estimated_output_tokens or task.output_tokens or 0)
        )
        for task in local_tasks
    )

    if total_tasks == 0:
        return {
            "accepted_yield_pct": 0.0,
            "local_first_pct": 0.0,
            "review_light_pct": 0.0,
            "local_tokens": 0,
            "local_accepted": 0,
        }

    return {
        "accepted_yield_pct": (len(accepted) / total_tasks) * 100.0,
        "local_first_pct": (len(local_tasks) / total_tasks) * 100.0,
        "review_light_pct": (len(review_light) / total_tasks) * 100.0,
        "local_tokens": local_tokens,
        "local_accepted": len(local_accepted),
    }


def _task_token_total(task) -> int:
    return task.total_tokens or (
        (task.estimated_input_tokens or task.input_tokens or 0)
        + (task.estimated_output_tokens or task.output_tokens or 0)
    )


def _telemetry_control_summary(tasks, log_tail: str = "", token_credit_allowance: int = 0) -> dict[str, dict[str, object]]:
    def _latest(records):
        if not records:
            return None
        return max(records, key=lambda task: task.updated_at or task.created_at or "")

    def _trim(text: str, limit: int = 90) -> str:
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."

    early_stop_tasks = [task for task in tasks if getattr(task, "early_stopped", False)]
    latest_early = _latest(early_stop_tasks)
    early_reason = getattr(latest_early, "early_stop_reason", "") if latest_early else ""

    firewall_tasks = [task for task in tasks if getattr(task, "firewall_triggered", False)]
    latest_firewall = _latest(firewall_tasks)
    firewall_reason = getattr(latest_firewall, "firewall_reason", "") if latest_firewall else ""

    configured_allowance = int(token_credit_allowance or 0)
    ledger_allowance = max((getattr(task, "credit_allowance_total", 0) or 0) for task in tasks) if tasks else 0
    effective_allowance = max(configured_allowance, ledger_allowance)
    credit_used = max(
        sum(_task_token_total(task) for task in tasks),
        max((getattr(task, "credit_allowance_used", 0) or 0) for task in tasks) if tasks else 0,
    )
    credit_remaining = max(effective_allowance - credit_used, 0) if effective_allowance else 0
    credit_exhausted = any(getattr(task, "credit_allowance_exhausted", False) for task in tasks)
    if effective_allowance:
        credit_exhausted = credit_exhausted or credit_used >= effective_allowance

    stability_tasks = [
        task
        for task in tasks
        if task.runner == "stability_pass" or task.study_id == "stability_pass"
    ]
    latest_stability = _latest(stability_tasks)
    if latest_stability and latest_stability.run_id:
        stability_scope = [
            task for task in stability_tasks if task.run_id == latest_stability.run_id
        ]
    else:
        stability_scope = stability_tasks

    stability_matches = sum(
        1
        for task in stability_scope
        if task.expected_status and task.observed_status == task.expected_status
    )
    stability_total = len(stability_scope)
    success_idx = log_tail.rfind("stability-pass completed status=success")
    failed_idx = log_tail.rfind("stability-pass completed status=failed")
    if success_idx == -1 and failed_idx == -1:
        stability_state = "ok" if stability_total and stability_matches == stability_total else "warn"
    else:
        stability_state = "ok" if success_idx > failed_idx else "alert"

    return {
        "early_stop": {
            "title": "Early Stopping",
            "value": "Clear" if not early_stop_tasks else f"{len(early_stop_tasks)} event(s)",
            "detail": (
                "No energy overrun stops recorded."
                if not latest_early
                else _trim(early_reason or "Energy overrun stop recorded.")
            ),
            "tone": "ok" if not early_stop_tasks else "alert",
        },
        "firewall": {
            "title": "Firewall Triggers",
            "value": "Clear" if not firewall_tasks else f"{len(firewall_tasks)} trigger(s)",
            "detail": (
                "No ethical boundary blocks recorded."
                if not latest_firewall
                else _trim(firewall_reason or "Ethical boundary block recorded.")
            ),
            "tone": "ok" if not firewall_tasks else "alert",
        },
        "credit": {
            "title": "Credit Status",
            "value": (
                "No cap"
                if not effective_allowance
                else ("Exhausted" if credit_exhausted else f"{credit_remaining} left")
            ),
            "detail": (
                "Token credit allowance not configured."
                if not effective_allowance
                else f"{credit_used}/{effective_allowance} tokens used"
            ),
            "tone": "ok" if not credit_exhausted else "alert",
        },
        "stability": {
            "title": "Stability Pass",
            "value": (
                "Not run"
                if not stability_total
                else ("PASS" if stability_state == "ok" else "FAIL")
            ),
            "detail": (
                "No stability pass evidence recorded yet."
                if not stability_total
                else f"{stability_matches}/{stability_total} fixtures matched expected outcomes"
            ),
            "tone": "ok" if stability_state == "ok" and stability_total else ("warn" if not stability_total else "alert"),
        },
    }


def _ledger_detail_lines(task) -> list[str]:
    lines = [
        f"Task ID: {task.task_id}",
        f"Created: {task.created_at or 'unknown'}",
        f"Updated: {task.updated_at or 'unknown'}",
    ]

    if task.completed_at:
        lines.append(f"Completed: {task.completed_at}")
    if task.description:
        lines.append(f"Prompt: {task.description}")
    if task.target_files:
        lines.append(f"Target files: {', '.join(task.target_files)}")
    if task.context_pack_path:
        lines.append(
            "Context budget: "
            f"{task.context_estimated_tokens}/{task.context_budget_tokens} tokens "
            f"({task.context_budget_status})"
        )
        lines.append(f"Context pack: {task.context_pack_path}")

    review_bits = []
    if task.status == "reviewed":
        review_bits.append("accepted" if task.accepted else "rejected")
    if task.human_review_minutes:
        review_bits.append(f"{task.human_review_minutes:.2f} review min")
    if task.human_review_required:
        review_bits.append("review required")
    if review_bits:
        lines.append(f"Review: {', '.join(review_bits)}")

    supervisor_bits = []
    if task.supervisor_tool:
        supervisor_bits.append(f"tool={task.supervisor_tool}")
    if task.supervisor_decision:
        supervisor_bits.append(f"decision={task.supervisor_decision}")
    if task.supervisor_model:
        supervisor_bits.append(f"model={task.supervisor_model}")
    if task.supervisor_profile:
        supervisor_bits.append(f"profile={task.supervisor_profile}")
    supervisor_tokens = task.supervisor_input_tokens_est + task.supervisor_output_tokens_est
    if supervisor_tokens:
        supervisor_bits.append(
            f"tokens_est={task.supervisor_input_tokens_est} in/{task.supervisor_output_tokens_est} out"
        )
    if task.supervisor_token_source:
        supervisor_bits.append(f"token_source={task.supervisor_token_source}")
    if supervisor_bits:
        lines.append(f"Supervisor: {', '.join(supervisor_bits)}")
    if task.supervisor_notes:
        lines.append(f"Supervisor notes: {task.supervisor_notes}")

    routing_bits = []
    if task.risk_level:
        routing_bits.append(f"risk={task.risk_level}")
    if task.permission_profile:
        routing_bits.append(f"profile={task.permission_profile}")
    if task.runner:
        routing_bits.append(f"runner={task.runner}")
    if routing_bits:
        lines.append(f"Routing: {', '.join(routing_bits)}")

    model_bits = []
    backend = task.backend_name or task.backend
    if backend:
        model_bits.append(f"backend={backend}")
    if task.model:
        model_bits.append(f"model={task.model}")
    if task.timeout_seconds:
        model_bits.append(f"timeout={task.timeout_seconds}s")
    if model_bits:
        lines.append(f"Model: {', '.join(model_bits)}")

    benchmark_bits = []
    if task.study_id:
        benchmark_bits.append(f"study={task.study_id}")
    if task.run_id:
        benchmark_bits.append(f"run={task.run_id}")
    if task.benchmark_task_id:
        benchmark_bits.append(f"fixture={task.benchmark_task_id}")
    if task.benchmark_category:
        benchmark_bits.append(f"category={task.benchmark_category}")
    if task.expected_status:
        benchmark_bits.append(f"expected={task.expected_status}")
    if task.observed_status:
        benchmark_bits.append(f"observed={task.observed_status}")
    if task.validator_passed is not None:
        benchmark_bits.append(f"validator_passed={task.validator_passed}")
    if benchmark_bits:
        lines.append(f"Benchmark: {', '.join(benchmark_bits)}")

    if task.handoff_reason:
        lines.append(f"Handoff reason: {task.handoff_reason}")
    if task.early_stopped and task.early_stop_reason:
        lines.append(f"Early stop: {task.early_stop_reason}")
    if task.firewall_triggered:
        lines.append(f"Firewall: {task.firewall_reason or 'triggered'}")
    if task.credit_allowance_total:
        credit_state = (
            "exhausted"
            if task.credit_allowance_exhausted
            else f"{task.credit_allowance_remaining} remaining"
        )
        lines.append(
            "Credit: "
            f"{task.credit_allowance_used}/{task.credit_allowance_total} used ({credit_state})"
        )
    if task.artifact_paths:
        lines.append(f"Artifacts: {', '.join(task.artifact_paths)}")

    return lines


def _ledger_detail_text(task) -> str:
    return "\n".join(_ledger_detail_lines(task))


def _review_assessment_lines(task) -> list[str]:
    status = task.status or "pending"
    if status == "reviewed":
        decision = "approved" if task.accepted else "denied"
        lines = [f"Decision recorded: {decision}"]
    elif task.human_review_required:
        lines = ["Decision needed: review required before adoption"]
    elif status in ["local_draft_generated", "handoff_generated", "council_completed"]:
        lines = ["Decision needed: draft is ready for review"]
    else:
        lines = [f"Current state: {status.replace('_', ' ')}"]

    runner_bits = []
    if task.runner:
        runner_bits.append(task.runner)
    backend = task.backend_name or task.backend
    if backend:
        runner_bits.append(backend)
    if task.model:
        runner_bits.append(task.model)
    if runner_bits:
        lines.append(f"Path: {' / '.join(runner_bits)}")

    if task.supervisor_tool or task.supervisor_decision:
        supervisor_label = task.supervisor_tool or "supervisor"
        supervisor_decision = task.supervisor_decision or "reviewed"
        lines.append(
            f"Supervisor: {supervisor_label} · {supervisor_decision.replace('_', ' ')}"
        )

    if task.handoff_reason:
        lines.append(f"Reason: {task.handoff_reason}")
    elif task.observed_status or task.expected_status:
        lines.append(
            f"Benchmark: expected {task.expected_status or 'n/a'}, observed {task.observed_status or 'n/a'}"
        )

    cost_bits = []
    total_tok = task.total_tokens or (
        (task.estimated_input_tokens or 0) + (task.estimated_output_tokens or 0)
    )
    if total_tok:
        cost_bits.append(f"{total_tok} tokens")
    if task.duration_seconds:
        cost_bits.append(f"{task.duration_seconds:.1f}s")
    if task.energy_kwh_estimate:
        cost_bits.append(f"{task.energy_kwh_estimate:.6f} kWh")
    if cost_bits:
        lines.append(f"Cost: {', '.join(cost_bits)}")

    if getattr(task, "review_workload", ""):
        lines.append(f"Review load: {task.review_workload.replace('_', ' ')}")

    if task.artifact_paths:
        lines.append(f"Artifact: {task.artifact_paths[-1]}")

    return lines[:5]


def _review_assessment_text(task) -> str:
    return "\n".join(f"- {line}" for line in _review_assessment_lines(task))


def _compact_ledger_line(task) -> str:
    status = task.status or "pending"
    if status == "reviewed":
        status = "accepted" if task.accepted else "rejected"

    title = task.title or task.description or task.task_id[:12]
    if len(title) > 70:
        title = title[:67] + "..."

    timestamp = task.updated_at or task.created_at or "no timestamp"
    meta = [f"#{task.task_id[:8]}", status.replace("_", " ")]
    if task.runner:
        meta.append(f"runner: {task.runner}")
    model = task.model or task.backend_name or task.backend
    if model:
        meta.append(f"model: {model}")
    if task.human_review_required and task.status != "reviewed":
        meta.append("review required")
    if task.supervisor_tool:
        supervisor_status = task.supervisor_decision or "reviewed"
        meta.append(f"supervisor: {task.supervisor_tool}/{supervisor_status}")

    return f"{timestamp} | {title} | {' · '.join(meta)}"


def _review_workload_value(label: str) -> str:
    values = {
        "Not set": "not_recorded",
        "Low": "low",
        "Medium": "medium",
        "High": "high",
    }
    return values.get(label, "not_recorded")


def _read_text_tail(path: str, max_lines: int = 400) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return "".join(lines[-max_lines:])


def _agent_display_name(role: str) -> str:
    return role.replace("_", " ").title()


def _agent_state_style(state: str) -> tuple[str, str]:
    styles = {
        "idle": ("#6b7280", "Idle"),
        "queued": ("#f59e0b", "Queued"),
        "running": ("#22c55e", "Running"),
        "completed": ("#38bdf8", "Complete"),
        "failed": ("#ef4444", "Issue"),
    }
    return styles.get(state, styles["idle"])


# ─── Small helper widgets ─────────────────────────────────────────────────────
class _SectionLabel(ctk.CTkLabel):
    def __init__(self, parent, text, **kw):
        super().__init__(
            parent,
            text=text.upper(),
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#6b7280",
            **kw,
        )


class _StatRow(ctk.CTkFrame):
    """Icon · value · sub-label on one row, used in ticker and telemetry."""

    def __init__(self, parent, icon, value, sub, **kw):
        super().__init__(parent, fg_color="transparent", **kw)
        self.icon_lbl = ctk.CTkLabel(
            self, text=icon, width=20, font=ctk.CTkFont(size=13)
        )
        self.icon_lbl.pack(side="left")
        self.val_lbl = ctk.CTkLabel(
            self, text=value, font=ctk.CTkFont(size=13, weight="bold")
        )
        self.val_lbl.pack(side="left", padx=(4, 0))
        self.sub_lbl = ctk.CTkLabel(
            self, text=sub, font=ctk.CTkFont(size=10), text_color="#9ca3af"
        )
        self.sub_lbl.pack(side="left", padx=(4, 0))

    def set_value(self, value):
        self.val_lbl.configure(text=value)


class CTkCircularGauge(ctk.CTkFrame):
    def __init__(self, parent, title, icon, unit, target_value, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.title = title
        self.icon = icon
        self.unit = unit
        self.target_value = float(target_value)
        self.current_value = 0.0

        # Title Label
        self.title_lbl = ctk.CTkLabel(
            self,
            text=title.upper(),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#9ca3af",
        )
        self.title_lbl.pack(pady=(5, 2))

        # Canvas for the Ring
        self.canvas_size = 120
        self.canvas = ctk.CTkCanvas(
            self, width=self.canvas_size, height=self.canvas_size, highlightthickness=0
        )
        self.canvas.pack(pady=5, fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_resize)

        self.draw_gauge()

    def _on_resize(self, event):
        size = min(event.width, event.height) - 10
        if size > 10:
            self.canvas_size = size
            self.draw_gauge()

    def set_value(self, value):
        try:
            self.current_value = float(value)
        except Exception:
            self.current_value = 0.0
        self.draw_gauge()

    def draw_gauge(self):
        self.canvas.delete("all")
        bg_color = self._get_canvas_bg()
        self.canvas.configure(bg=bg_color)

        is_dark = ctk.get_appearance_mode() == "Dark"
        bg_circle_color = "#2d3748" if is_dark else "#e2e8f0"
        text_color = "#f7fafc" if is_dark else "#1a202c"

        gauge_color = "#3b82f6"
        if "energy" in self.title.lower():
            gauge_color = "#eab308"
        elif "emission" in self.title.lower() or "co2" in self.title.lower():
            gauge_color = "#f97316"
        elif "water" in self.title.lower():
            gauge_color = "#06b6d4"
        elif "embodied" in self.title.lower():
            gauge_color = "#a855f7"

        padding = max(10, int(self.canvas_size * 0.05))
        thickness = max(8, int(self.canvas_size * 0.08))

        cx = self.canvas.winfo_width() / 2
        cy = self.canvas.winfo_height() / 2
        if cx <= 10 or cy <= 10:
            cx = self.canvas_size / 2
            cy = self.canvas_size / 2

        radius = (self.canvas_size - padding * 2) / 2
        if radius < 5:
            return

        x0 = cx - radius
        y0 = cy - radius
        x1 = cx + radius
        y1 = cy + radius

        # Draw background track
        self.canvas.create_oval(
            x0, y0, x1, y1, outline=bg_circle_color, width=thickness
        )

        # Calculate percentage
        if self.target_value > 0:
            pct = min(1.0, max(0.0, self.current_value / self.target_value))
        else:
            pct = 0.0

        start_angle = 90
        extent_angle = -int(pct * 359.9)

        if pct > 0:
            self.canvas.create_arc(
                x0,
                y0,
                x1,
                y1,
                start=start_angle,
                extent=extent_angle,
                outline=gauge_color,
                width=thickness,
                style="arc",
            )

        font_size_val = max(13, int(self.canvas_size * 0.15))
        font_size_icon = max(14, int(self.canvas_size * 0.18))
        font_size_unit = max(9, int(self.canvas_size * 0.08))

        # Show value formatted beautifully
        if self.current_value < 0.0001 and self.current_value > 0:
            val_str = f"{self.current_value:.6f}"
        elif self.current_value < 0.01 and self.current_value > 0:
            val_str = f"{self.current_value:.4f}"
        else:
            val_str = f"{self.current_value:.2f}"

        self.canvas.create_text(
            cx,
            cy - int(self.canvas_size * 0.18),
            text=self.icon,
            font=("Courier", font_size_icon),
            fill=gauge_color,
        )
        self.canvas.create_text(
            cx,
            cy + int(self.canvas_size * 0.05),
            text=val_str,
            font=("Outfit", font_size_val, "bold"),
            fill=text_color,
        )
        self.canvas.create_text(
            cx,
            cy + int(self.canvas_size * 0.25),
            text=self.unit,
            font=("Outfit", font_size_unit),
            fill="#9ca3af",
        )

    def _get_canvas_bg(self):
        color = self.cget("fg_color")
        if isinstance(color, (list, tuple)) and len(color) == 2:
            return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]
        elif color == "transparent" or color is None:
            curr = self.master
            while curr:
                try:
                    p_color = curr.cget("fg_color")
                    if p_color != "transparent" and p_color is not None:
                        if isinstance(p_color, (list, tuple)) and len(p_color) == 2:
                            return (
                                p_color[1]
                                if ctk.get_appearance_mode() == "Dark"
                                else p_color[0]
                            )
                        return p_color
                except Exception:
                    pass
                curr = curr.master
        return "#2b2b2b" if ctk.get_appearance_mode() == "Dark" else "#dbdbdb"


class CTkBatteryGauge(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self.title_lbl = ctk.CTkLabel(
            self,
            text="BATTERY / POWER STATUS",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#9ca3af",
        )
        self.title_lbl.pack(pady=(5, 2))

        self.canvas_width = 160
        self.canvas_height = 80
        self.canvas = ctk.CTkCanvas(
            self,
            width=self.canvas_width,
            height=self.canvas_height,
            highlightthickness=0,
        )
        self.canvas.pack(pady=5, fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_resize)

        self.status_lbl = ctk.CTkLabel(
            self, text="Checking status…", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.status_lbl.pack(pady=2)

        self.percent = 100.0
        self.plugged = True
        self.has_battery = False

        self.draw_battery()

    def _on_resize(self, event):
        if event.width > 10 and event.height > 10:
            self.canvas_width = event.width
            self.canvas_height = event.height
            self.draw_battery()

    def set_status(self, percent, plugged, has_battery):
        self.percent = float(percent) if percent is not None else 100.0
        self.plugged = bool(plugged)
        self.has_battery = bool(has_battery)
        self.draw_battery()

    def draw_battery(self):
        self.canvas.delete("all")
        bg_color = self._get_canvas_bg()
        self.canvas.configure(bg=bg_color)

        is_dark = ctk.get_appearance_mode() == "Dark"
        outline_color = "#4a5568" if is_dark else "#cbd5e1"
        text_color = "#f7fafc" if is_dark else "#1a202c"

        if not self.has_battery:
            self.canvas.create_text(
                self.canvas_width / 2,
                self.canvas_height / 2,
                text="🔌 AC DIRECT\nNo Battery",
                font=("Outfit", max(12, int(self.canvas_height * 0.15)), "bold"),
                fill="#22c55e",
                justify="center",
            )
            self.status_lbl.configure(text="System running on stable grid power")
            return

        cx = self.canvas_width / 2
        cy = self.canvas_height / 2
        bw = min(150, self.canvas_width * 0.8)
        bh = min(60, self.canvas_height * 0.6)

        b_x0 = cx - bw / 2
        b_y0 = cy - bh / 2
        b_x1 = cx + bw / 2
        b_y1 = cy + bh / 2

        self.canvas.create_rectangle(
            b_x0, b_y0, b_x1, b_y1, outline=outline_color, width=max(3, int(bh * 0.05))
        )
        self.canvas.create_rectangle(
            b_x1,
            b_y0 + bh * 0.2,
            b_x1 + bw * 0.05,
            b_y1 - bh * 0.2,
            fill=outline_color,
            outline=outline_color,
        )

        pct = min(1.0, max(0.0, self.percent / 100.0))
        fill_width = (bw - 8) * pct

        if self.plugged:
            fill_color = "#22c55e"
        elif self.percent > 50:
            fill_color = "#3b82f6"
        elif self.percent > 20:
            fill_color = "#f97316"
        else:
            fill_color = "#ef4444"

        if fill_width > 0:
            self.canvas.create_rectangle(
                b_x0 + 4,
                b_y0 + 4,
                b_x0 + 4 + fill_width,
                b_y1 - 4,
                fill=fill_color,
                outline="",
            )

        self.canvas.create_text(
            cx,
            cy,
            text=f"{self.percent:.0f}%",
            font=("Outfit", max(12, int(bh * 0.25)), "bold"),
            fill=text_color,
        )

        status_text = "Charging ⚡" if self.plugged else "Discharging 🔋"
        self.status_lbl.configure(text=f"{status_text} · Level: {self.percent:.0f}%")

    def _get_canvas_bg(self):
        color = self.cget("fg_color")
        if isinstance(color, (list, tuple)) and len(color) == 2:
            return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]
        elif color == "transparent" or color is None:
            curr = self.master
            while curr:
                try:
                    p_color = curr.cget("fg_color")
                    if p_color != "transparent" and p_color is not None:
                        if isinstance(p_color, (list, tuple)) and len(p_color) == 2:
                            return (
                                p_color[1]
                                if ctk.get_appearance_mode() == "Dark"
                                else p_color[0]
                            )
                        return p_color
                except Exception:
                    pass
                curr = curr.master
        return "#2b2b2b" if ctk.get_appearance_mode() == "Dark" else "#dbdbdb"


class CTkDispatchShare(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self.title_lbl = ctk.CTkLabel(
            self,
            text="RUNNER SHARE PROFILE",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#9ca3af",
        )
        self.title_lbl.pack(pady=(5, 2))

        self.canvas_width = 240
        self.canvas_height = 80
        self.canvas = ctk.CTkCanvas(
            self,
            width=self.canvas_width,
            height=self.canvas_height,
            highlightthickness=0,
        )
        self.canvas.pack(pady=5, fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_resize)

        self.shares = (0, 0, 0, 0)
        self.draw_shares(*self.shares)

    def _on_resize(self, event):
        if event.width > 10 and event.height > 10:
            self.canvas_width = event.width
            self.canvas_height = event.height
            self.draw_shares(*self.shares)

    def draw_shares(self, local, council, codex, anti):
        self.shares = (local, council, codex, anti)
        self.canvas.delete("all")
        bg_color = self._get_canvas_bg()
        self.canvas.configure(bg=bg_color)

        total = local + council + codex + anti
        if total == 0:
            self.canvas.create_text(
                self.canvas_width / 2,
                self.canvas_height / 2,
                text="No tasks dispatched yet",
                font=("Outfit", max(11, int(self.canvas_height * 0.15))),
                fill="gray",
            )
            return

        p_local = local / total
        p_council = council / total
        p_codex = codex / total
        p_anti = anti / total

        cx = self.canvas_width / 2
        cy = self.canvas_height / 2
        width = min(self.canvas_width * 0.9, 400)
        height = max(16, int(self.canvas_height * 0.2))
        x0 = cx - width / 2
        y0 = cy - height / 2 - 5

        w_local = width * p_local
        w_council = width * p_council
        w_codex = width * p_codex
        w_anti = width * p_anti

        curr_x = x0
        colors = ["#166534", "#0e4f6b", "#7c2d12", "#4a1d96"]

        for w, col in zip([w_local, w_council, w_codex, w_anti], colors):
            if w > 0:
                self.canvas.create_rectangle(
                    curr_x, y0, curr_x + w, y0 + height, fill=col, outline=""
                )
                curr_x += w

        curr_x = x0
        font_size = max(8, int(self.canvas_height * 0.12))
        for val, p, col, label in zip(
            [local, council, codex, anti],
            [p_local, p_council, p_codex, p_anti],
            colors,
            ["LCL", "CNC", "CDX", "ANT"],
        ):
            if val > 0:
                text_x = curr_x + (width * p) / 2
                self.canvas.create_text(
                    text_x,
                    y0 - int(font_size * 1.2),
                    text=f"{p*100:.0f}%",
                    font=("Outfit", font_size, "bold"),
                    fill=col,
                )
                self.canvas.create_text(
                    text_x,
                    y0 + height + int(font_size * 1.2),
                    text=label,
                    font=("Outfit", font_size, "bold"),
                    fill="#9ca3af",
                )
                curr_x += width * p

    def _get_canvas_bg(self):
        color = self.cget("fg_color")
        if isinstance(color, (list, tuple)) and len(color) == 2:
            return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]
        elif color == "transparent" or color is None:
            curr = self.master
            while curr:
                try:
                    p_color = curr.cget("fg_color")
                    if p_color != "transparent" and p_color is not None:
                        if isinstance(p_color, (list, tuple)) and len(p_color) == 2:
                            return (
                                p_color[1]
                                if ctk.get_appearance_mode() == "Dark"
                                else p_color[0]
                            )
                        return p_color
                except Exception:
                    pass
                curr = curr.master
        return "#2b2b2b" if ctk.get_appearance_mode() == "Dark" else "#dbdbdb"


# ─── Main App ────────────────────────────────────────────────────────────────
class TriageDeskApp(ctk.CTk if UI_AVAILABLE else object):
    def _add_focus_ring(self, widget, active_border_color="#2563eb"):
        if not hasattr(widget, "cget"):
            return
        orig_width = widget.cget("border_width")

        def on_focus_in(event):
            try:
                widget.configure(border_width=2, border_color=active_border_color)
            except Exception:
                pass

        def on_focus_out(event):
            try:
                widget.configure(border_width=orig_width)
            except Exception:
                pass

        widget.bind("<FocusIn>", on_focus_in, add="+")
        widget.bind("<FocusOut>", on_focus_out, add="+")

    def __init__(self):
        if not UI_AVAILABLE:
            print(
                "Error: customtkinter is not installed. Run `pip install triagecore[ui]`"
            )
            return

        super().__init__()
        self.ledger = TaskLedger(ledger_dir=default_config.get_ledger_dir())
        self.active_backend = None
        self._current_frame = "dispatch"
        self.review_timers = {}
        self.timer_labels = {}
        self.review_workload_vars = {}
        self.expanded_ledger_task_ids = set()
        self.agent_status = {}
        self._last_logs_render = None
        self._last_inline_logs_render = None
        self._last_ledger_feed_render = None
        self.current_loaded_task_id = None

        # Setup runtime file logger
        import logging

        log_dir = _ledger_dir()
        os.makedirs(log_dir, exist_ok=True)
        log_file = _log_file_path()
        logging.basicConfig(
            filename=log_file,
            filemode="a",
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            level=logging.INFO,
        )
        logging.info("TriageDesk Control Plane initialized.")

        self.title("TriageDesk Control Plane")
        self.geometry("1280x820")
        self.minsize(1050, 680)

        # Set icon
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(current_dir, "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        self.attributes("-fullscreen", False)
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self.exit_fullscreen)

        # Dashboard is split into a primary workbench and a secondary telemetry band.
        # The generated artifact needs visual priority during review.
        self.grid_rowconfigure(0, weight=4)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._build_sidebar()
        self._build_dispatch_frame()
        self._build_planner_frame()
        self._build_ledger_frame()
        self._build_telemetry_frame()
        self._build_status_panel()
        self._build_review_queue_panel()
        self._build_logs_frame()
        self._build_rules_frame()

        self.state("zoomed")
        self.select_frame("dashboard")
        self._check_backends()
        self._start_ticker()
        self._start_live_logs()
        self._start_ipc_watcher()
        self.after(1000, self._update_active_timers)

    def toggle_fullscreen(self, event=None):
        self.attributes("-fullscreen", not self.attributes("-fullscreen"))

    def exit_fullscreen(self, event=None):
        self.attributes("-fullscreen", False)

    # ─── Sidebar ──────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=220, corner_radius=0)
        sb.grid(row=0, column=0, rowspan=2, sticky="nsew")
        sb.grid_rowconfigure(8, weight=1)
        self.sidebar = sb

        ctk.CTkLabel(
            sb, text="TriageDesk", font=ctk.CTkFont(size=20, weight="bold")
        ).grid(row=0, column=0, padx=20, pady=(20, 6))

        ctk.CTkLabel(
            sb, text="Control Plane", font=ctk.CTkFont(size=11), text_color="gray"
        ).grid(row=1, column=0, padx=20, pady=(0, 16))

        self._nav_btns = {}

        # Dashboard
        btn_dash = ctk.CTkButton(
            sb,
            text="Dashboard",
            anchor="w",
            command=lambda: self.select_frame("dashboard"),
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
        )
        btn_dash.grid(row=2, column=0, padx=12, pady=4, sticky="ew")
        self._nav_btns["dashboard"] = btn_dash

        # Context Planner
        btn_planner = ctk.CTkButton(
            sb,
            text="Context Planner",
            anchor="w",
            command=lambda: self.select_frame("planner"),
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
        )
        btn_planner.grid(row=3, column=0, padx=12, pady=4, sticky="ew")
        self._nav_btns["planner"] = btn_planner

        # Task Ledger
        btn_ledger = ctk.CTkButton(
            sb,
            text="Task Ledger",
            anchor="w",
            command=lambda: self.select_frame("ledger"),
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
        )
        btn_ledger.grid(row=4, column=0, padx=12, pady=4, sticky="ew")
        self._nav_btns["ledger"] = btn_ledger

        # Link to Log Repository under the Task Ledger button
        self.link_log = ctk.CTkButton(
            sb,
            text="  ↳ Log Repository",
            anchor="w",
            command=lambda: self.select_frame("logs"),
            fg_color="transparent",
            text_color=("#38bdf8", "#0284c7"),
            hover_color=("gray70", "gray30"),
            font=ctk.CTkFont(size=11, underline=True),
        )
        self.link_log.grid(row=5, column=0, padx=12, pady=(0, 4), sticky="ew")

        # System Logs
        btn_logs = ctk.CTkButton(
            sb,
            text="System Logs",
            anchor="w",
            command=lambda: self.select_frame("logs"),
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
        )
        btn_logs.grid(row=6, column=0, padx=12, pady=4, sticky="ew")
        self._nav_btns["logs"] = btn_logs

        # Council Rules
        btn_rules = ctk.CTkButton(
            sb,
            text="Council Rules",
            anchor="w",
            command=lambda: self.select_frame("rules"),
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
        )
        btn_rules.grid(row=7, column=0, padx=12, pady=4, sticky="ew")
        self._nav_btns["rules"] = btn_rules

        for btn in [btn_dash, btn_planner, btn_ledger, self.link_log, btn_logs, btn_rules]:
            self._add_focus_ring(btn)

        # ── Agent Status Panel ─────────────────────────
        self.agent_panel = ctk.CTkFrame(sb, corner_radius=10, fg_color="transparent")
        self.agent_panel.grid(row=8, column=0, padx=12, pady=(10, 0), sticky="sew")

        _SectionLabel(self.agent_panel, "Agent Status").pack(
            anchor="w", padx=10, pady=(0, 8)
        )

        self.agent_indicators = {}
        self.agent_status_labels = {}
        self.agent_meta_labels = {}
        agents = ["repo_mapper", "code_repair", "validator", "test_stubber"]
        for agent in agents:
            row = ctk.CTkFrame(self.agent_panel, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=3)

            indicator = ctk.CTkFrame(
                row, width=12, height=12, corner_radius=2, fg_color="#ef4444"
            )
            indicator.pack(side="left", padx=(0, 8), pady=2)
            indicator.pack_propagate(False)

            text_col = ctk.CTkFrame(row, fg_color="transparent")
            text_col.pack(side="left", fill="x", expand=True)

            lbl = ctk.CTkLabel(
                text_col,
                text=_agent_display_name(agent),
                font=ctk.CTkFont(size=11, weight="bold"),
                anchor="w",
            )
            lbl.pack(anchor="w")

            meta = ctk.CTkLabel(
                text_col,
                text="Idle · awaiting task",
                font=ctk.CTkFont(size=10),
                text_color="#9ca3af",
                anchor="w",
            )
            meta.pack(anchor="w")

            state_lbl = ctk.CTkLabel(
                row,
                text="Idle",
                width=58,
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color="#9ca3af",
                anchor="e",
            )
            state_lbl.pack(side="right")

            self.agent_status[agent] = "idle"
            self.agent_indicators[agent] = indicator
            self.agent_status_labels[agent] = state_lbl
            self.agent_meta_labels[agent] = meta

        # ── Live Resource Ticker (bottom of sidebar) ──────────────────────────
        ticker = ctk.CTkFrame(sb, corner_radius=10, fg_color=("gray85", "gray20"))
        ticker.grid(row=9, column=0, padx=12, pady=12, sticky="sew")
        sb.grid_rowconfigure(9, weight=0)
        sb.grid_rowconfigure(8, weight=1)

        _SectionLabel(ticker, "Live Session").pack(anchor="w", padx=10, pady=(8, 2))

        self._t_energy = _StatRow(ticker, "⚡", "0.000000 kWh", "energy")
        self._t_emissions = _StatRow(ticker, "💨", "0.000 gCO₂e", "emissions")
        self._t_water = _StatRow(ticker, "💧", "0.000 L", "water")
        self._t_embodied = _StatRow(ticker, "🔩", "0.000 gCO₂e", "embodied")
        for w in [self._t_energy, self._t_emissions, self._t_water, self._t_embodied]:
            w.pack(anchor="w", padx=10, pady=1)

        ctk.CTkFrame(ticker, height=1, fg_color="gray50").pack(
            fill="x", padx=10, pady=4
        )

        fs_btn = ctk.CTkButton(
            ticker,
            text="⛶ Fullscreen (F11)",
            width=120,
            height=24,
            command=self.toggle_fullscreen,
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40"),
            text_color=("gray10", "gray90"),
        )
        fs_btn.pack(pady=(2, 6))

        self._t_backend = ctk.CTkLabel(
            ticker,
            text="Engine: checking…",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self._t_backend.pack(anchor="w", padx=10, pady=(0, 2))
        self._t_model = ctk.CTkLabel(
            ticker,
            text="Model: —",
            font=ctk.CTkFont(size=10),
            text_color="gray",
            wraplength=180,
        )
        self._t_model.pack(anchor="w", padx=10, pady=(0, 8))

    # ─── Dispatch Frame ───────────────────────────────────────────────────────
    def _build_dispatch_frame(self):
        f = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(6, weight=1)
        self.dispatch_frame = f

        ctk.CTkLabel(
            f, text="Dispatch Task", font=ctk.CTkFont(size=22, weight="bold")
        ).grid(row=0, column=0, padx=24, pady=(20, 4), sticky="w")

        self.backend_status_label = ctk.CTkLabel(
            f,
            text="Checking local engines…",
            text_color="gray",
            font=ctk.CTkFont(size=12),
        )
        self.backend_status_label.grid(
            row=1, column=0, padx=24, pady=(0, 8), sticky="w"
        )

        self.prompt_box = ctk.CTkTextbox(f, height=90, text_color=("gray52", "gray62"))
        self.prompt_box.grid(row=2, column=0, padx=24, pady=(0, 6), sticky="ew")
        self.prompt_box.insert("0.0", "Describe your task here…")

        def on_focus_in(event):
            try:
                current_text = self.prompt_box.get("0.0", "end-1c").strip()
                if current_text == "Describe your task here…":
                    self.prompt_box.delete("0.0", "end")
                    self.prompt_box.configure(text_color=("gray10", "#DCE4EE"))
            except Exception:
                pass

        def on_focus_out(event):
            try:
                current_text = self.prompt_box.get("0.0", "end-1c").strip()
                if not current_text:
                    self.prompt_box.delete("0.0", "end")
                    self.prompt_box.insert("0.0", "Describe your task here…")
                    self.prompt_box.configure(text_color=("gray52", "gray62"))
            except Exception:
                pass

        self.prompt_box.bind("<FocusIn>", on_focus_in)
        self.prompt_box.bind("<FocusOut>", on_focus_out)

        self.files_entry = ctk.CTkEntry(
            f, placeholder_text="Target files (comma separated, optional)"
        )
        self.files_entry.grid(row=3, column=0, padx=24, pady=(0, 10), sticky="ew")

        self._add_focus_ring(self.prompt_box)
        self._add_focus_ring(self.files_entry)

        # ── 4 Dispatch Buttons ───────────────────────────────────────────────
        btn_row = ctk.CTkFrame(f, fg_color="transparent")
        btn_row.grid(row=4, column=0, padx=24, pady=(0, 8), sticky="ew")
        btn_row.grid_columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="dispatch")

        # Glow frames for workflow sequence
        self.glow_local = ctk.CTkFrame(btn_row, corner_radius=8, border_width=0, fg_color="transparent")
        self.glow_local.grid(row=0, column=0, padx=(0, 4), sticky="ew")
        self.btn_local = ctk.CTkButton(
            self.glow_local,
            text="1. Local Draft\nRun with active local model",
            height=56,
            command=lambda: self._handle_task("local"),
            fg_color="#166534",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.btn_local.pack(padx=3, pady=3, fill="both", expand=True)

        self.glow_council = ctk.CTkFrame(btn_row, corner_radius=8, border_width=0, fg_color="transparent")
        self.glow_council.grid(row=0, column=1, padx=(4, 4), sticky="ew")
        self.btn_council = ctk.CTkButton(
            self.glow_council,
            text="2. Worker Council\nCross-check with agents",
            height=56,
            command=lambda: self._handle_task("council"),
            fg_color="#0e4f6b",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.btn_council.pack(padx=3, pady=3, fill="both", expand=True)

        self.glow_codex = ctk.CTkFrame(btn_row, corner_radius=8, border_width=0, fg_color="transparent")
        self.glow_codex.grid(row=0, column=2, padx=(4, 4), sticky="ew")
        self.btn_codex = ctk.CTkButton(
            self.glow_codex,
            text="3. Codex Handoff\nWrite review packet",
            height=56,
            command=lambda: self._handle_task("codex"),
            fg_color="#7c2d12",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.btn_codex.pack(padx=3, pady=3, fill="both", expand=True)

        self.glow_anti = ctk.CTkFrame(btn_row, corner_radius=8, border_width=0, fg_color="transparent")
        self.glow_anti.grid(row=0, column=3, padx=(4, 4), sticky="ew")
        self.btn_anti = ctk.CTkButton(
            self.glow_anti,
            text="4. Antigravity Handoff\nCreate IDE task bundle",
            height=56,
            command=lambda: self._handle_task("antigravity"),
            fg_color="#4a1d96",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.btn_anti.pack(padx=3, pady=3, fill="both", expand=True)

        self.glow_pipeline = ctk.CTkFrame(btn_row, corner_radius=8, border_width=0, fg_color="transparent")
        self.glow_pipeline.grid(row=0, column=4, padx=(4, 0), sticky="ew")
        self.btn_pipeline = ctk.CTkButton(
            self.glow_pipeline,
            text="5. Auto Pipeline\nRun Sequential Chain",
            height=56,
            command=lambda: self._handle_task("pipeline"),
            fg_color="#b45309",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.btn_pipeline.pack(padx=3, pady=3, fill="both", expand=True)

        for btn in [self.btn_local, self.btn_council, self.btn_codex, self.btn_anti, self.btn_pipeline]:
            self._add_focus_ring(btn)

        self.status_label = ctk.CTkLabel(
            f, text="", text_color="gray", font=ctk.CTkFont(size=12)
        )
        self.status_label.grid(row=5, column=0, padx=24, pady=(0, 4), sticky="w")

        # ── Result Area ──────────────────────────────────────────────────────
        result_outer = ctk.CTkScrollableFrame(
            f,
            corner_radius=8,
            label_text="Generated Artifact",
            label_font=ctk.CTkFont(size=12, weight="bold"),
        )
        result_outer.grid(row=6, column=0, padx=24, pady=(0, 20), sticky="nsew")
        result_outer.grid_columnconfigure(0, weight=1)
        self._result_outer = result_outer

        # Metric chips row (hidden until a run completes)
        self._result_metrics = ctk.CTkFrame(result_outer, fg_color="transparent")
        self._result_metrics.grid(row=0, column=0, sticky="ew", pady=(4, 8))
        self._result_metrics.grid_remove()

        self.output_box = ctk.CTkTextbox(
            result_outer,
            height=390,
            state="disabled",
            font=ctk.CTkFont(family="Consolas", size=13),
        )
        self.output_box.grid(row=1, column=0, sticky="nsew", pady=(0, 8))

        self.inline_log_label = ctk.CTkLabel(
            result_outer,
            text="Route Trace & System Log",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#9ca3af",
            anchor="w",
        )
        self.inline_log_label.grid(row=2, column=0, sticky="ew", pady=(0, 4))

        self.inline_log_box = ctk.CTkTextbox(
            result_outer,
            height=72,
            state="disabled",
            font=ctk.CTkFont(family="Consolas", size=10),
        )
        self.inline_log_box.grid(row=3, column=0, sticky="ew")

        feed_hdr = ctk.CTkFrame(result_outer, fg_color="transparent")
        feed_hdr.grid(row=4, column=0, sticky="ew", pady=(12, 4))
        feed_hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            feed_hdr,
            text="Recent task ledger",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#9ca3af",
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            feed_hdr,
            text="Open Ledger",
            width=96,
            height=24,
            fg_color="transparent",
            border_width=1,
            command=lambda: self.select_frame("ledger"),
        ).grid(row=0, column=1, padx=(6, 0), sticky="e")
        ctk.CTkButton(
            feed_hdr,
            text="Export CSV",
            width=96,
            height=24,
            fg_color="transparent",
            border_width=1,
            command=lambda: self._export_ledger("csv"),
        ).grid(row=0, column=2, padx=(6, 0), sticky="e")
        ctk.CTkButton(
            feed_hdr,
            text="Export JSON",
            width=104,
            height=24,
            fg_color="transparent",
            border_width=1,
            command=lambda: self._export_ledger("json"),
        ).grid(row=0, column=3, padx=(6, 0), sticky="e")

        self.ledger_feed_frame = ctk.CTkScrollableFrame(
            result_outer,
            height=82,
            corner_radius=8,
            fg_color=("gray88", "gray18"),
        )
        self.ledger_feed_frame.grid(row=5, column=0, sticky="ew")
        self.ledger_feed_frame.grid_columnconfigure(0, weight=1)

    def _show_result_metrics(
        self,
        model,
        backend,
        tokens_in,
        tokens_out,
        duration,
        energy,
        emissions,
        water,
        embodied,
    ):
        """Populate and show the metric chip row after a run."""
        for w in self._result_metrics.winfo_children():
            w.destroy()

        chips = [
            ("🧠", model or "—", "model"),
            ("🖥", backend or "—", "backend"),
            ("🎫", f"{tokens_in}→{tokens_out}", "tokens in→out"),
            ("⏱", f"{duration:.1f}s", "duration"),
            ("⚡", f"{energy:.6f}", "kWh"),
            ("💨", f"{emissions:.4f}", "gCO₂e"),
            ("💧", f"{water:.4f}", "L water"),
            ("🔩", f"{embodied:.5f}", "gCO₂e emb."),
        ]
        for col, (icon, val, lbl) in enumerate(chips):
            chip = ctk.CTkFrame(
                self._result_metrics, corner_radius=8, fg_color=("gray85", "gray20")
            )
            chip.grid(row=0, column=col, padx=4, pady=2)
            ctk.CTkLabel(
                chip, text=f"{icon} {val}", font=ctk.CTkFont(size=12, weight="bold")
            ).pack(padx=10, pady=(6, 0))
            ctk.CTkLabel(
                chip, text=lbl, font=ctk.CTkFont(size=9), text_color="gray"
            ).pack(padx=10, pady=(0, 6))

        self._result_metrics.grid()

    # ─── Context Planner Frame ──────────────────────────────────────────────────
    def _build_planner_frame(self):
        f = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(2, weight=1)
        self.planner_frame = f

        ctk.CTkLabel(
            f, text="Context Planner", font=ctk.CTkFont(size=22, weight="bold")
        ).grid(row=0, column=0, padx=24, pady=(20, 4), sticky="w")

        ctk.CTkLabel(
            f, text="Dry-run resource planning and packet previews.", text_color="gray", font=ctk.CTkFont(size=12)
        ).grid(row=1, column=0, padx=24, pady=(0, 16), sticky="w")

        self.planner_tabview = ctk.CTkTabview(f)
        self.planner_tabview.grid(row=2, column=0, padx=24, pady=(0, 24), sticky="nsew")

        self.planner_tabview.add("Context Planner")
        self.planner_tabview.add("Packet Preview")

        self._build_context_planner_tab(self.planner_tabview.tab("Context Planner"))
        self._build_packet_preview_tab(self.planner_tabview.tab("Packet Preview"))

    def _build_context_planner_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(5, weight=1)

        # Input file
        ctk.CTkLabel(parent, text="Input file:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=12, pady=(12, 0), sticky="w")
        self._planner_file_entry = ctk.CTkEntry(parent, placeholder_text="e.g. triage_core/tc_cli.py")
        self._planner_file_entry.grid(row=1, column=0, padx=12, pady=(4, 16), sticky="ew")

        # Model profile
        ctk.CTkLabel(parent, text="Model profile:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=2, column=0, padx=12, sticky="w")

        # Read available profiles
        profiles = list(token_budget.MODEL_PROFILES.keys()) if hasattr(token_budget, 'MODEL_PROFILES') else ["generic-8k", "generic-32k"]
        self._planner_model_var = ctk.StringVar(value=profiles[0])
        self._planner_model_menu = ctk.CTkOptionMenu(parent, values=profiles, variable=self._planner_model_var)
        self._planner_model_menu.grid(row=3, column=0, padx=12, pady=(4, 24), sticky="w")

        # Button
        self._planner_btn = ctk.CTkButton(
            parent, text="Run Dry-Run Plan", font=ctk.CTkFont(size=13, weight="bold"),
            command=self._run_context_plan, fg_color="#1e3a8a", hover_color="#1e40af"
        )
        self._planner_btn.grid(row=4, column=0, padx=12, pady=(0, 24), sticky="w")

        # Results area
        res_card = ctk.CTkFrame(parent, corner_radius=8, fg_color=("gray85", "gray17"))
        res_card.grid(row=5, column=0, padx=12, pady=(0, 12), sticky="nsew")
        res_card.grid_columnconfigure(1, weight=1)

        _SectionLabel(res_card, "Results").grid(row=0, column=0, columnspan=2, padx=16, pady=(12, 12), sticky="w")

        self._planner_res_tokens = ctk.CTkLabel(res_card, text="—", font=ctk.CTkFont(size=13, weight="bold"))
        self._planner_res_budget = ctk.CTkLabel(res_card, text="—", font=ctk.CTkFont(size=13, weight="bold"))
        self._planner_res_status = ctk.CTkLabel(res_card, text="—", font=ctk.CTkFont(size=13, weight="bold"))
        self._planner_res_action = ctk.CTkLabel(res_card, text="—", font=ctk.CTkFont(size=13, weight="bold"))

        labels = ["Estimated input tokens:", "Usable budget:", "Status:", "Recommended action:"]
        vals = [self._planner_res_tokens, self._planner_res_budget, self._planner_res_status, self._planner_res_action]
        for i, (lbl, val_widget) in enumerate(zip(labels, vals)):
            ctk.CTkLabel(res_card, text=lbl, text_color="gray", font=ctk.CTkFont(size=12)).grid(row=i+1, column=0, padx=16, pady=4, sticky="w")
            val_widget.grid(row=i+1, column=1, padx=16, pady=4, sticky="w")

    def _build_packet_preview_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(7, weight=1)

        # Task file
        ctk.CTkLabel(parent, text="Task file:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=12, pady=(12, 0), sticky="w")
        self._preview_task_entry = ctk.CTkEntry(parent, placeholder_text="e.g. docs/triagedesk_gui_plan.md")
        self._preview_task_entry.grid(row=1, column=0, padx=12, pady=(4, 16), sticky="ew")

        # Include files
        ctk.CTkLabel(parent, text="Include files (comma or newline separated):", font=ctk.CTkFont(size=12, weight="bold")).grid(row=2, column=0, padx=12, sticky="w")
        self._preview_includes_text = ctk.CTkTextbox(parent, height=60)
        self._preview_includes_text.grid(row=3, column=0, padx=12, pady=(4, 16), sticky="ew")

        # Model profile
        ctk.CTkLabel(parent, text="Model profile:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=4, column=0, padx=12, sticky="w")
        profiles = list(token_budget.MODEL_PROFILES.keys()) if hasattr(token_budget, 'MODEL_PROFILES') else ["generic-8k", "generic-32k"]
        self._preview_model_var = ctk.StringVar(value=profiles[0])
        self._preview_model_menu = ctk.CTkOptionMenu(parent, values=profiles, variable=self._preview_model_var)
        self._preview_model_menu.grid(row=5, column=0, padx=12, pady=(4, 24), sticky="w")

        # Button
        self._preview_btn = ctk.CTkButton(
            parent, text="Preview Packet", font=ctk.CTkFont(size=13, weight="bold"),
            command=self._run_packet_preview, fg_color="#1e3a8a", hover_color="#1e40af"
        )
        self._preview_btn.grid(row=6, column=0, padx=12, pady=(0, 24), sticky="w")

        # Results area
        res_card = ctk.CTkFrame(parent, corner_radius=8, fg_color=("gray85", "gray17"))
        res_card.grid(row=7, column=0, padx=12, pady=(0, 12), sticky="nsew")
        res_card.grid_columnconfigure(0, weight=1)
        res_card.grid_rowconfigure(2, weight=1)

        hdr_frame = ctk.CTkFrame(res_card, fg_color="transparent")
        hdr_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 8))
        self._preview_res_status = ctk.CTkLabel(hdr_frame, text="—", font=ctk.CTkFont(size=13, weight="bold"))
        self._preview_res_status.pack(side="left")

        self._preview_res_budget = ctk.CTkLabel(hdr_frame, text="—", font=ctk.CTkFont(size=12), text_color="gray")
        self._preview_res_budget.pack(side="right")

        self._preview_res_tokens = ctk.CTkLabel(hdr_frame, text="—", font=ctk.CTkFont(size=12), text_color="gray")
        self._preview_res_tokens.pack(side="right", padx=10)

        self._preview_textbox = ctk.CTkTextbox(res_card, state="disabled", wrap="word", font=ctk.CTkFont(family="Consolas", size=11))
        self._preview_textbox.grid(row=2, column=0, padx=16, pady=(0, 16), sticky="nsew")

    def _run_context_plan(self):
        input_file = self._planner_file_entry.get().strip()
        model_profile = self._planner_model_var.get()

        if not input_file:
            self._planner_res_status.configure(text="Error: Missing file path", text_color="#ef4444")
            return

        if not _TD_ADAPTER_AVAILABLE or _td_adapter is None:
            self._planner_res_status.configure(text="Error: Adapter unavailable", text_color="#ef4444")
            return

        self._planner_res_status.configure(text="Planning...", text_color="gray")
        self.update_idletasks()

        try:
            snapshot = _td_adapter.plan_context_file(input_file, model_profile)
            self._planner_res_tokens.configure(text=str(snapshot.estimated_input_tokens), text_color=("gray10", "gray90"))
            self._planner_res_budget.configure(text=str(snapshot.usable_input_budget), text_color=("gray10", "gray90"))

            # Status colors
            status_text = snapshot.status
            status_color = ("gray10", "gray90")
            if "fits" in status_text.lower():
                status_color = "#22c55e" # green
            elif "over budget" in status_text.lower():
                status_color = "#ef4444" # red

            self._planner_res_status.configure(text=status_text, text_color=status_color)

            # Action (handling if it's a list)
            action = snapshot.recommended_action
            if isinstance(action, list):
                action = " · ".join(action)
            self._planner_res_action.configure(text=str(action), text_color=("gray10", "gray90"))
        except FileNotFoundError:
            self._planner_res_status.configure(text="Error: File not found", text_color="#ef4444")
            self._planner_res_tokens.configure(text="—")
            self._planner_res_budget.configure(text="—")
            self._planner_res_action.configure(text="—")
        except KeyError:
            self._planner_res_status.configure(text="Error: Unknown model profile", text_color="#ef4444")
        except Exception as e:
            self._planner_res_status.configure(text=f"Error: {e}", text_color="#ef4444")

    def _run_packet_preview(self):
        task_file = self._preview_task_entry.get().strip()

        raw_includes = self._preview_includes_text.get("0.0", "end").strip()
        include_paths = []
        if raw_includes:
            import re
            parts = re.split(r'[,\n]+', raw_includes)
            include_paths = [p.strip() for p in parts if p.strip()]

        model_profile = self._preview_model_var.get()

        def _clear_preview(error_msg):
            self._preview_res_status.configure(text=error_msg, text_color="#ef4444")
            self._preview_res_tokens.configure(text="—")
            self._preview_res_budget.configure(text="—")
            self._preview_textbox.configure(state="normal")
            self._preview_textbox.delete("0.0", "end")
            self._preview_textbox.configure(state="disabled")

        if not task_file:
            _clear_preview("Error: Missing task file path")
            return

        if not _TD_ADAPTER_AVAILABLE or _td_adapter is None:
            _clear_preview("Error: Adapter unavailable")
            return

        self._preview_res_status.configure(text="Previewing...", text_color="gray")
        self.update_idletasks()

        try:
            snapshot = _td_adapter.preview_packet(task_file, model_profile, include_paths)
            self._preview_res_tokens.configure(text=f"Tokens: {snapshot.estimated_tokens}")
            self._preview_res_budget.configure(text=f"Budget: {snapshot.budget.usable_input_tokens}")

            status_text = "Fits Budget" if snapshot.fits_budget else "Over Budget"
            status_color = "#22c55e" if snapshot.fits_budget else "#ef4444"
            self._preview_res_status.configure(text=status_text, text_color=status_color)

            self._preview_textbox.configure(state="normal")
            self._preview_textbox.delete("0.0", "end")
            self._preview_textbox.insert("0.0", snapshot.content)
            self._preview_textbox.configure(state="disabled")

        except FileNotFoundError as e:
            _clear_preview(f"Error: {e}")
        except KeyError:
            _clear_preview("Error: Unknown model profile")
        except Exception as e:
            _clear_preview(f"Error: {e}")

    # ─── Ledger Frame ─────────────────────────────────────────────────────────
    def _build_ledger_frame(self):
        f = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1, minsize=350)
        f.grid_columnconfigure(1, weight=3)
        f.grid_rowconfigure(1, weight=1)
        self.ledger_frame = f

        # Header spans both columns
        hdr = ctk.CTkFrame(f, fg_color="transparent")
        hdr.grid(row=0, column=0, columnspan=2, padx=24, pady=(20, 8), sticky="ew")
        ctk.CTkLabel(
            hdr, text="Task Ledger & Inspector", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(side="left")
        ctk.CTkButton(
            hdr,
            text="↻ Refresh",
            width=90,
            command=self._refresh_ledger,
            fg_color="transparent",
            border_width=1,
        ).pack(side="right")

        # Left pane (Task list)
        self.ledger_scroll = ctk.CTkScrollableFrame(
            f, corner_radius=8, fg_color=("gray85", "gray15")
        )
        self.ledger_scroll.grid(row=1, column=0, padx=(12, 6), pady=(0, 12), sticky="nsew")
        self.ledger_scroll.grid_columnconfigure(0, weight=1)

        # Right pane (Context inspector)
        self.context_inspector = ctk.CTkFrame(
            f, corner_radius=8, fg_color=("gray85", "gray20")
        )
        self.context_inspector.grid(row=1, column=1, padx=(6, 12), pady=(0, 12), sticky="nsew")
        self.context_inspector.grid_columnconfigure(0, weight=1)
        self.context_inspector.grid_rowconfigure(1, weight=1)

        # Tabs for inspector
        self.inspector_tabs = ctk.CTkSegmentedButton(
            self.context_inspector,
            values=["Summary", "Artifacts", "Telemetry", "Timeline", "Review"],
            command=self._on_inspector_tab_change
        )
        self.inspector_tabs.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.inspector_tabs.set("Summary")
        self.current_inspector_tab = "Summary"

        self.inspector_content = ctk.CTkScrollableFrame(
            self.context_inspector, fg_color="transparent", corner_radius=0
        )
        self.inspector_content.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.inspector_content.grid_columnconfigure(0, weight=1)

    def _on_inspector_tab_change(self, value):
        self.current_inspector_tab = value
        if self.current_loaded_task_id:
            self._render_context_inspector(self.current_loaded_task_id)

    def _select_ledger_task(self, task_id):
        self.current_loaded_task_id = task_id
        self._render_context_inspector(task_id)

    def _render_context_inspector(self, task_id):
        for w in self.inspector_content.winfo_children():
            w.destroy()

        ctx = self.ledger.get_task_context(task_id)
        if not ctx:
            ctk.CTkLabel(self.inspector_content, text="Task not found.", text_color="gray").pack(pady=40)
            return

        if self.current_inspector_tab == "Summary":
            self._render_inspector_summary(ctx)
        elif self.current_inspector_tab == "Artifacts":
            self._render_inspector_artifacts(ctx)
        elif self.current_inspector_tab == "Telemetry":
            self._render_inspector_telemetry(ctx)
        elif self.current_inspector_tab == "Timeline":
            self._render_inspector_timeline(ctx)
        elif self.current_inspector_tab == "Review":
            self._render_inspector_review(ctx)

    def _render_inspector_summary(self, ctx):
        t = ctx.record
        _SectionLabel(self.inspector_content, "Task Details").pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(self.inspector_content, text=t.title or t.task_id[:12], font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(self.inspector_content, text=f"ID: {t.task_id}").pack(anchor="w")
        ctk.CTkLabel(self.inspector_content, text=f"Status: {t.status}").pack(anchor="w")
        ctk.CTkLabel(self.inspector_content, text=f"Runner: {t.runner or 'None'}").pack(anchor="w")
        ctk.CTkLabel(self.inspector_content, text=f"Risk Level: {t.risk_level or 'None'}").pack(anchor="w")
        ctk.CTkLabel(self.inspector_content, text=f"Profile: {t.permission_profile or 'None'}").pack(anchor="w")
        if t.description:
            ctk.CTkLabel(self.inspector_content, text="Prompt:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(10, 0))
            box = ctk.CTkTextbox(self.inspector_content, height=100)
            box.pack(fill="x", pady=4)
            box.insert("0.0", t.description)
            box.configure(state="disabled")

    def _render_inspector_artifacts(self, ctx):
        _SectionLabel(self.inspector_content, "Generated Artifacts").pack(anchor="w", pady=(0, 4))
        if not ctx.artifact_paths:
            ctk.CTkLabel(self.inspector_content, text="No artifacts generated yet.", text_color="gray").pack(anchor="w", pady=10)
            return

        for path in ctx.artifact_paths:
            ctk.CTkLabel(self.inspector_content, text=path, font=ctk.CTkFont(size=11, family="Courier")).pack(anchor="w", pady=2)

        if ctx.latest_artifact_text:
            ctk.CTkLabel(self.inspector_content, text="Latest Artifact Preview:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(10, 4))
            box = ctk.CTkTextbox(self.inspector_content, height=300, font=ctk.CTkFont(size=11, family="Courier"))
            box.pack(fill="both", expand=True, pady=4)
            box.insert("0.0", ctx.latest_artifact_text)
            box.configure(state="disabled")

    def _render_inspector_telemetry(self, ctx):
        _SectionLabel(self.inspector_content, "Resource Consumption").pack(anchor="w", pady=(0, 4))
        tel = ctx.telemetry_summary
        grid = ctk.CTkFrame(self.inspector_content, fg_color="transparent")
        grid.pack(fill="x", pady=10)
        grid.grid_columnconfigure((0,1), weight=1)

        ctk.CTkLabel(grid, text=f"⏱ Duration: {tel.get('duration_seconds', 0):.2f}s", font=ctk.CTkFont(size=13)).grid(row=0, column=0, sticky="w", pady=4)
        ctk.CTkLabel(grid, text=f"🎫 Tokens: {tel.get('total_tokens', 0)}", font=ctk.CTkFont(size=13)).grid(row=0, column=1, sticky="w", pady=4)
        ctk.CTkLabel(grid, text=f"⚡ Energy: {tel.get('energy_kwh', 0):.6f} kWh", font=ctk.CTkFont(size=13)).grid(row=1, column=0, sticky="w", pady=4)
        ctk.CTkLabel(grid, text=f"💨 Emissions: {tel.get('emissions_gco2e', 0):.4f} gCO₂e", font=ctk.CTkFont(size=13)).grid(row=1, column=1, sticky="w", pady=4)
        ctk.CTkLabel(grid, text=f"💧 Water: {tel.get('water_liters', 0):.4f} L", font=ctk.CTkFont(size=13)).grid(row=2, column=0, sticky="w", pady=4)
        ctk.CTkLabel(grid, text=f"🔩 Embodied: {tel.get('embodied_gco2e', 0):.5f} gCO₂e", font=ctk.CTkFont(size=13)).grid(row=2, column=1, sticky="w", pady=4)
        if tel.get("context_budget_tokens"):
            ctk.CTkLabel(
                grid,
                text=(
                    "🧠 Context: "
                    f"{tel.get('context_estimated_tokens', 0)}/"
                    f"{tel.get('context_budget_tokens', 0)} "
                    f"({tel.get('context_budget_status', 'unknown')})"
                ),
                font=ctk.CTkFont(size=13),
            ).grid(row=3, column=0, columnspan=2, sticky="w", pady=4)

    def _render_inspector_timeline(self, ctx):
        _SectionLabel(self.inspector_content, "Event Timeline").pack(anchor="w", pady=(0, 4))
        if not ctx.events:
            ctk.CTkLabel(self.inspector_content, text="No events recorded.", text_color="gray").pack(anchor="w", pady=10)
            return

        for ev in ctx.events:
            frame = ctk.CTkFrame(self.inspector_content, fg_color=("gray90", "gray10"), corner_radius=4)
            frame.pack(fill="x", pady=2)
            ts = ev.get('timestamp', '')[:19].replace('T', ' ')
            etype = ev.get('event_type', 'unknown')
            ctk.CTkLabel(frame, text=f"{ts} | {etype}", font=ctk.CTkFont(size=11, family="Courier", weight="bold")).pack(anchor="w", padx=10, pady=4)

    def _render_inspector_review(self, ctx):
        _SectionLabel(self.inspector_content, "Review & Action").pack(anchor="w", pady=(0, 4))
        rev = ctx.review_summary
        t = ctx.record

        ctk.CTkLabel(self.inspector_content, text=f"Human Review Required: {rev.get('human_review_required', False)}").pack(anchor="w", pady=2)
        ctk.CTkLabel(self.inspector_content, text=f"Accepted: {rev.get('accepted', False)}").pack(anchor="w", pady=2)
        if rev.get("supervisor_decision"):
            ctk.CTkLabel(self.inspector_content, text=f"Supervisor Decision: {rev.get('supervisor_decision')}").pack(anchor="w", pady=2)

        if t.status in ["local_draft_generated", "handoff_generated", "council_completed", "pending"]:
            actions = ctk.CTkFrame(self.inspector_content, fg_color="transparent")
            actions.pack(fill="x", pady=20)

            accept_btn = ctk.CTkButton(actions, text="Approve & Load", fg_color="#166534", hover_color="#15803d", command=lambda: self._execute_context_review(t.task_id, True))
            accept_btn.pack(side="left", padx=(0, 10))

            reject_btn = ctk.CTkButton(actions, text="Deny", fg_color="#7f1d1d", hover_color="#991b1b", command=lambda: self._execute_context_review(t.task_id, False))
            reject_btn.pack(side="left", padx=(0, 10))

            needs_rev_btn = ctk.CTkButton(actions, text="Needs Revision", fg_color="#b45309", hover_color="#92400e", command=lambda: self._execute_context_review(t.task_id, False, "needs_revision"))
            needs_rev_btn.pack(side="left")

    def _execute_context_review(self, task_id: str, accepted: bool, decision_override: str = None):
        payload = {
            "accepted": accepted,
            "human_review_minutes": 1.0,
            "review_workload": "medium"
        }
        if decision_override:
            payload["decision"] = decision_override

        self.ledger.append_event(task_id, "review_completed", payload)

        if accepted:
            task = self.ledger.get_task(task_id)
            if task:
                self.prompt_box.delete("0.0", "end")
                self.prompt_box.insert("0.0", task.description or "")
                self.prompt_box.configure(text_color=("gray10", "#DCE4EE"))
                self.files_entry.delete(0, "end")
                if task.target_files:
                    self.files_entry.insert(0, ", ".join(task.target_files))
                self.select_frame("dashboard")
                self.status_label.configure(
                    text=f"✓ Loaded task #{task_id[:8]} details. Ready to execute locally.",
                    text_color="#22c55e",
                )

        self._refresh_ledger()
        self._refresh_compact_ledger_feed()
        self._update_ticker()
        self._refresh_telemetry()

    def _refresh_ledger(self):
        self.timer_labels = {}
        for w in self.ledger_scroll.winfo_children():
            w.destroy()

        tasks = self.ledger.get_recent_tasks(50)
        if not tasks:
            ctk.CTkLabel(
                self.ledger_scroll, text="No tasks in ledger yet.", text_color="gray"
            ).grid(row=0, column=0, pady=40)
            return

        for i, t in enumerate(tasks):
            status = t.status or "pending"
            if status == "reviewed":
                status = "accepted" if t.accepted else "rejected"
            fg = _card_fg(status)
            badge_bg, badge_fg = _badge_color(status)

            card = ctk.CTkFrame(self.ledger_scroll, corner_radius=6, fg_color=fg, cursor="hand2")
            card.grid(row=i, column=0, padx=4, pady=4, sticky="ew")
            card.grid_columnconfigure(1, weight=1)

            # Make card elements clickable
            def make_handler(tid=t.task_id):
                return lambda e, task_id=tid: self._select_ledger_task(task_id)

            handler = make_handler()
            card.bind("<Button-1>", handler)

            # Status badge
            badge = ctk.CTkLabel(
                card,
                text=f" {status.replace('_', ' ')} ",
                fg_color=badge_bg,
                text_color=badge_fg,
                corner_radius=4,
                font=ctk.CTkFont(size=9, weight="bold"),
            )
            badge.grid(row=0, column=0, padx=(8, 6), pady=(6, 2), sticky="w")
            badge.bind("<Button-1>", handler)

            # Title
            title_lbl = ctk.CTkLabel(
                card,
                text=t.title or t.task_id[:12],
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w",
            )
            title_lbl.grid(row=0, column=1, pady=(6, 2), sticky="w")
            title_lbl.bind("<Button-1>", handler)

            # ID chip
            id_lbl = ctk.CTkLabel(
                card,
                text=f"#{t.task_id[:8]}",
                font=ctk.CTkFont(size=9),
                text_color="#9ca3af",
                anchor="e",
            )
            id_lbl.grid(row=0, column=2, padx=(8, 6), pady=(6, 2), sticky="e")
            id_lbl.bind("<Button-1>", handler)

            meta_parts = []
            if t.risk_level: meta_parts.append(f"Risk: {t.risk_level}")
            if t.runner: meta_parts.append(f"Runner: {t.runner}")

            meta_lbl = ctk.CTkLabel(
                card,
                text=" · ".join(meta_parts),
                font=ctk.CTkFont(size=10),
                text_color="#9ca3af",
                anchor="w",
            )
            meta_lbl.grid(row=1, column=0, columnspan=3, padx=8, pady=(0, 6), sticky="w")
            meta_lbl.bind("<Button-1>", handler)

        if not self.current_loaded_task_id and tasks:
            self._select_ledger_task(tasks[0].task_id)
        elif self.current_loaded_task_id:
            self._render_context_inspector(self.current_loaded_task_id)

    def _refresh_compact_ledger_feed(self, force=True):
        if not hasattr(self, "ledger_feed_frame"):
            return

        tasks = self.ledger.get_all_tasks()[:6]
        render_key = "\n".join(_compact_ledger_line(t) for t in tasks)
        if not force and render_key == self._last_ledger_feed_render:
            return

        for w in self.ledger_feed_frame.winfo_children():
            w.destroy()

        if not tasks:
            ctk.CTkLabel(
                self.ledger_feed_frame,
                text="No ledger activity yet.",
                text_color="#9ca3af",
                font=ctk.CTkFont(size=11),
            ).grid(row=0, column=0, padx=10, pady=14, sticky="w")
            self._last_ledger_feed_render = render_key
            return

        for i, task in enumerate(tasks):
            status = task.status or "pending"
            if status == "reviewed":
                status = "accepted" if task.accepted else "rejected"
            badge_bg, badge_fg = _badge_color(status)

            row = ctk.CTkFrame(
                self.ledger_feed_frame,
                corner_radius=8,
                fg_color=("gray82", "gray22"),
            )
            row.grid(row=i, column=0, padx=6, pady=4, sticky="ew")
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                row,
                text=f" {status.replace('_', ' ')} ",
                fg_color=badge_bg,
                text_color=badge_fg,
                corner_radius=6,
                font=ctk.CTkFont(size=9, weight="bold"),
            ).grid(row=0, column=0, padx=(8, 6), pady=(6, 2), sticky="w")

            ctk.CTkLabel(
                row,
                text=task.title or task.task_id[:12],
                font=ctk.CTkFont(size=11, weight="bold"),
                anchor="w",
            ).grid(row=0, column=1, padx=(0, 8), pady=(6, 2), sticky="ew")

            ctk.CTkLabel(
                row,
                text=f"#{task.task_id[:8]}",
                font=ctk.CTkFont(size=9),
                text_color="#9ca3af",
                anchor="e",
            ).grid(row=0, column=2, padx=(0, 8), pady=(6, 2), sticky="e")

            ctk.CTkLabel(
                row,
                text=_compact_ledger_line(task),
                font=ctk.CTkFont(size=10),
                text_color="#9ca3af",
                anchor="w",
                wraplength=760,
            ).grid(row=1, column=0, columnspan=3, padx=8, pady=(0, 6), sticky="ew")

        self._last_ledger_feed_render = render_key

    def _toggle_ledger_details(self, task_id):
        if task_id in self.expanded_ledger_task_ids:
            self.expanded_ledger_task_ids.remove(task_id)
        else:
            self.expanded_ledger_task_ids.add(task_id)
        self._refresh_ledger()

    def _review_task(self, task_id, accepted):
        self.current_loaded_task_id = task_id
        start_time = self.review_timers.pop(task_id, None)
        elapsed_mins = 0.0
        task = self.ledger.get_task(task_id)
        if start_time is not None:
            elapsed_mins = (time.time() - start_time) / 60.0
        elif task:
            completed_at_str = getattr(task, "completed_at", "") or task.created_at
            if completed_at_str:
                try:
                    completed_dt = datetime.fromisoformat(completed_at_str)
                    now_dt = datetime.now(timezone.utc)
                    elapsed_mins = (now_dt - completed_dt).total_seconds() / 60.0
                except Exception:
                    pass

        if elapsed_mins < 0:
            elapsed_mins = 0.0

        workload_var = self.review_workload_vars.get(task_id)
        workload_label = workload_var.get() if workload_var else "Not set"

        self.ledger.append_event(
            task_id,
            "review_completed",
            {
                "accepted": accepted,
                "human_review_minutes": elapsed_mins,
                "review_workload": _review_workload_value(workload_label),
            },
        )

        if accepted and task:
            self.prompt_box.delete("0.0", "end")
            self.prompt_box.insert("0.0", task.description or "")
            self.prompt_box.configure(text_color=("gray10", "#DCE4EE"))

            self.files_entry.delete(0, "end")
            if task.target_files:
                self.files_entry.insert(0, ", ".join(task.target_files))

            self.select_frame("dashboard")
            self.status_label.configure(
                text=f"✓ Loaded task #{task_id[:8]} details. Ready to execute locally.",
                text_color="#22c55e",
            )

        self._refresh_ledger()
        self._refresh_compact_ledger_feed()
        self._update_ticker()
        self._refresh_telemetry()
        self._update_workflow_glow()

    def _update_active_timers(self):
        if self._current_frame == "ledger":
            now = time.time()
            to_remove = []
            for task_id, (label, task) in self.timer_labels.items():
                try:
                    if not label.winfo_exists():
                        to_remove.append(task_id)
                        continue

                    start_time = self.review_timers.get(task_id)
                    if start_time is None:
                        completed_at_str = (
                            getattr(task, "completed_at", "") or task.created_at
                        )
                        if completed_at_str:
                            try:
                                completed_dt = datetime.fromisoformat(completed_at_str)
                                now_dt = datetime.now(timezone.utc)
                                elapsed_sec = (now_dt - completed_dt).total_seconds()
                            except Exception:
                                elapsed_sec = 0.0
                        else:
                            elapsed_sec = 0.0
                    else:
                        elapsed_sec = now - start_time

                    if elapsed_sec < 0:
                        elapsed_sec = 0.0

                    if elapsed_sec >= 60:
                        mins = int(elapsed_sec // 60)
                        secs = int(elapsed_sec % 60)
                        label.configure(text=f"🕐 {mins}m {secs}s elapsed")
                    else:
                        label.configure(text=f"🕐 {int(elapsed_sec)}s elapsed")
                except Exception:
                    pass
            for task_id in to_remove:
                self.timer_labels.pop(task_id, None)

        self.after(1000, self._update_active_timers)

    # ─── Logs Frame ───────────────────────────────────────────────────────────
    def _build_logs_frame(self):
        f = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(1, weight=1)
        self.logs_frame = f

        hdr = ctk.CTkFrame(f, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=24, pady=(20, 8), sticky="ew")

        ctk.CTkLabel(
            hdr, text="Log Repository", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(side="left")

        self._log_view_mode = "system"

        self.btn_toggle_ledger = ctk.CTkButton(
            hdr,
            text="📄 Raw Ledger",
            width=110,
            height=28,
            command=lambda: self._set_log_view("ledger"),
            fg_color="transparent",
            border_width=1,
        )
        self.btn_toggle_ledger.pack(side="right", padx=(8, 0))

        self.btn_toggle_sys = ctk.CTkButton(
            hdr,
            text="🖥 System Logs",
            width=110,
            height=28,
            command=lambda: self._set_log_view("system"),
            fg_color=("gray70", "gray30"),
        )
        self.btn_toggle_sys.pack(side="right")

        self.live_log_status = ctk.CTkLabel(
            f,
            text="Live tail enabled · system logs",
            font=ctk.CTkFont(size=11),
            text_color="#9ca3af",
            anchor="w",
        )
        self.live_log_status.grid(row=2, column=0, padx=24, pady=(0, 8), sticky="w")

        self.logs_box = ctk.CTkTextbox(f, font=ctk.CTkFont(family="Courier", size=12))
        self.logs_box.grid(row=1, column=0, padx=24, pady=(0, 8), sticky="nsew")

    def _set_log_view(self, mode):
        self._log_view_mode = mode
        self._last_logs_render = None
        if mode == "system":
            self.btn_toggle_sys.configure(fg_color=("gray70", "gray30"))
            self.btn_toggle_ledger.configure(fg_color="transparent")
        else:
            self.btn_toggle_sys.configure(fg_color="transparent")
            self.btn_toggle_ledger.configure(fg_color=("gray70", "gray30"))
        self._refresh_logs()

    def _refresh_logs(self, force=True):
        self.logs_box.configure(state="normal")

        if self._log_view_mode == "system":
            log_file = _log_file_path()
            if os.path.exists(log_file):
                try:
                    content = _read_text_tail(log_file)
                except Exception as e:
                    content = f"Error reading log file: {e}"
            else:
                content = "No system logs generated yet."
            self.live_log_status.configure(text="Live tail enabled · system logs")
        else:
            ledger_file = _ledger_file_path()
            if os.path.exists(ledger_file):
                try:
                    content = _read_text_tail(ledger_file)
                except Exception as e:
                    content = f"Error reading ledger file: {e}"
            else:
                content = "No ledger records found."
            self.live_log_status.configure(text="Live tail enabled · raw ledger")

        if force or content != self._last_logs_render:
            self.logs_box.delete("0.0", "end")
            self.logs_box.insert("0.0", content)
            self._last_logs_render = content
            self.logs_box.see("end")

        self.logs_box.configure(state="disabled")

    def _start_live_logs(self):
        self._update_live_logs()

    def _update_live_logs(self):
        self._refresh_inline_logs(force=False)
        if getattr(self, "_current_frame", None) == "logs":
            self._refresh_logs(force=False)
        self.after(1000, self._update_live_logs)

    def _inline_log_content(self) -> str:
        control = getattr(self, "control_plane_backend", None) or self.active_backend
        control_name = self._backend_label(control) if hasattr(self, "_backend_label") else (
            control.name if control else "none"
        )
        control_model = self._model_label(control) if hasattr(self, "_model_label") else (
            getattr(control, "model", None) or "none"
        )
        worker_pool = self._worker_pool_label() if hasattr(self, "_worker_pool_label") else "unknown"
        route_trace = getattr(self, "last_route_trace", "none recorded this session")
        header = [
            f"Control plane: {control_name}",
            f"Control model: {control_model}",
            f"Worker pool: {worker_pool}",
            f"Last route: {route_trace}",
            "Source: TriageCore backend/activity events",
            "",
        ]
        tail = _read_text_tail(_log_file_path(), max_lines=80)
        if not tail.strip():
            tail = "No backend activity logged yet."
        return "\n".join(header) + tail

    def _refresh_inline_logs(self, force=True):
        if not hasattr(self, "inline_log_box"):
            return
        content = self._inline_log_content()
        if not force and content == self._last_inline_logs_render:
            return
        self.inline_log_box.configure(state="normal")
        self.inline_log_box.delete("0.0", "end")
        self.inline_log_box.insert("0.0", content)
        self.inline_log_box.see("end")
        self.inline_log_box.configure(state="disabled")
        self._last_inline_logs_render = content

    def _log_activity(self, message, level="info"):
        import logging

        logger = logging.getLogger("triage_core.ui")
        if level == "error":
            logger.error(message)
        elif level == "warning":
            logger.warning(message)
        else:
            logger.info(message)
        self._last_inline_logs_render = None

    def _build_rules_frame(self):
        f = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        self.rules_frame = f

        ctk.CTkLabel(
            f,
            text="Council Configuration Panel",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, padx=24, pady=(20, 10), sticky="w")

        ctk.CTkLabel(
            f,
            text="Configure specialized local models and backend engines for each Worker Council role.",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        ).grid(row=1, column=0, padx=24, pady=(0, 20), sticky="w")

        roles = ["repo_mapper", "code_repair", "validator", "test_stubber", "union_rep"]
        self.rules_inputs = {}

        current_row = 2
        for role in roles:
            card = ctk.CTkFrame(f, corner_radius=12)
            card.grid(row=current_row, column=0, padx=24, pady=8, sticky="ew")
            card.grid_columnconfigure((0, 1, 2), weight=1)

            ctk.CTkLabel(
                card,
                text=role.replace("_", " ").upper(),
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color="#93c5fd",
            ).grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")

            ctk.CTkLabel(
                card,
                text="Backend Engine:",
                font=ctk.CTkFont(size=11),
                text_color="gray",
            ).grid(row=1, column=0, padx=16, pady=2, sticky="w")
            backend_var = ctk.StringVar(value="ollama")
            backend_entry = ctk.CTkEntry(card, textvariable=backend_var, width=150)
            backend_entry.grid(row=2, column=0, padx=16, pady=(0, 12), sticky="w")

            ctk.CTkLabel(
                card,
                text="Model Identifier:",
                font=ctk.CTkFont(size=11),
                text_color="gray",
            ).grid(row=1, column=1, padx=16, pady=2, sticky="w")
            model_var = ctk.StringVar(value="qwen2.5-coder:7b-triagecore")
            model_entry = ctk.CTkEntry(card, textvariable=model_var, width=220)
            model_entry.grid(row=2, column=1, padx=16, pady=(0, 12), sticky="w")

            ctk.CTkLabel(
                card,
                text="Max Tokens Limit:",
                font=ctk.CTkFont(size=11),
                text_color="gray",
            ).grid(row=1, column=2, padx=16, pady=2, sticky="w")
            tokens_var = ctk.StringVar(value="800")
            tokens_entry = ctk.CTkEntry(card, textvariable=tokens_var, width=100)
            tokens_entry.grid(row=2, column=2, padx=16, pady=(0, 12), sticky="w")

            for entry in [backend_entry, model_entry, tokens_entry]:
                self._add_focus_ring(entry)

            self.rules_inputs[role] = {
                "backend": backend_var,
                "model": model_var,
                "max_tokens": tokens_var,
            }
            current_row += 1

        btn_save = ctk.CTkButton(
            f,
            text="💾 Save Council Configurations",
            width=250,
            height=36,
            command=self._save_rules_toml,
            fg_color="#1e3a5f",
            hover_color="#2b4c7e",
        )
        btn_save.grid(row=current_row, column=0, padx=24, pady=24, sticky="w")

        self.rules_frame.grid_forget()

    def _load_rules_toml(self):
        from ..config import default_config

        default_config.__init__()

        for role, inputs in self.rules_inputs.items():
            worker_cfg = default_config.get_worker_config(role)
            inputs["backend"].set(worker_cfg.get("backend", "ollama"))

            global_model = default_config.get_global(
                "backend", "default_model", "qwen2.5-coder:7b-triagecore"
            )
            inputs["model"].set(worker_cfg.get("model", global_model))
            inputs["max_tokens"].set(str(worker_cfg.get("max_tokens", 800)))

    def _save_rules_toml(self):
        from ..config import default_config

        rules_path = default_config.work_rules_path
        lines = []
        if os.path.exists(rules_path):
            try:
                with open(rules_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except Exception:
                pass

        new_lines = []
        for line in lines:
            if line.strip().startswith("[workers."):
                break
            new_lines.append(line)

        while new_lines and not new_lines[-1].strip():
            new_lines.pop()

        new_lines.append("\n")
        for role, inputs in self.rules_inputs.items():
            new_lines.append(f"[workers.{role}]\n")
            new_lines.append(f'backend = "{inputs["backend"].get()}"\n')
            new_lines.append(f'model = "{inputs["model"].get()}"\n')
            try:
                max_tok = int(inputs["max_tokens"].get())
            except ValueError:
                max_tok = 800
            new_lines.append(f"max_tokens = {max_tok}\n\n")

        try:
            with open(rules_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            self.status_label.configure(
                text="✓ Council rules updated successfully.", text_color="#22c55e"
            )
        except Exception as e:
            self.status_label.configure(
                text=f"Error saving rules: {e}", text_color="#ef4444"
            )

        default_config.__init__()

    # ─── Export Helpers ───────────────────────────────────────────────────────
    def _export_safe_value(self, value):
        import json

        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)

    def _task_export_row(self, task):
        if hasattr(task, "__dict__"):
            raw = dict(task.__dict__)
        else:
            raw = {}
            for name in dir(task):
                if name.startswith("_"):
                    continue
                try:
                    value = getattr(task, name)
                except Exception:
                    continue
                if callable(value):
                    continue
                raw[name] = value

        row = {}
        for key, value in raw.items():
            if key.startswith("_"):
                continue
            row[key] = self._export_safe_value(value)
        return row

    def _export_ledger(self, fmt):
        import csv
        import json

        fmt = (fmt or "").lower().strip()
        if fmt not in {"csv", "json"}:
            self.status_label.configure(
                text=f"Export error: unsupported format {fmt}",
                text_color="#ef4444",
            )
            return

        try:
            tasks = self.ledger.get_all_tasks()
            rows = [self._task_export_row(task) for task in tasks]
            export_dir = os.path.join(default_config.get_ledger_dir(), "exports")
            os.makedirs(export_dir, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(export_dir, f"triagedesk_ledger_{timestamp}.{fmt}")

            if fmt == "json":
                payload = {
                    "schema": "triagedesk.ledger.export.v1",
                    "exported_at": datetime.now(timezone.utc).isoformat(),
                    "task_count": len(rows),
                    "tasks": rows,
                }
                with open(output_path, "w", encoding="utf-8") as fh:
                    json.dump(payload, fh, indent=2, ensure_ascii=False)
            else:
                fieldnames = sorted({key for row in rows for key in row.keys()})
                with open(output_path, "w", encoding="utf-8", newline="") as fh:
                    writer = csv.DictWriter(fh, fieldnames=fieldnames)
                    writer.writeheader()
                    for row in rows:
                        writer.writerow(row)

            self.status_label.configure(
                text=f"✓ Exported {len(rows)} ledger task(s) to {output_path}",
                text_color="#22c55e",
            )
            self._log_activity(f"Ledger exported as {fmt}: {output_path}")

            if getattr(self, "current_loaded_task_id", None):
                self.ledger.append_event(
                    self.current_loaded_task_id,
                    "ledger_exported",
                    {
                        "format": fmt,
                        "artifact_path": output_path,
                        "task_count": len(rows),
                    },
                )

            self._refresh_inline_logs(force=True)
        except Exception as exc:
            self.status_label.configure(
                text=f"Export error: {exc}",
                text_color="#ef4444",
            )
            self._log_activity(f"Ledger export error ({fmt}): {exc}", level="error")


    # ─── Telemetry Frame ──────────────────────────────────────────────────────
    def _build_telemetry_frame(self):
        f = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        self.telemetry_frame = f

        # Row 0 is reserved for the Operator Status panel (built separately)
        # Row 1 is reserved for the Review Queue panel (built separately)

        ctk.CTkLabel(
            f,
            text="Savings & Telemetry Dashboard",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=2, column=0, padx=24, pady=(20, 4), sticky="w")

        # Row 1: Savings / avoidance signals from existing ledger evidence.
        self._savings_card = ctk.CTkFrame(f, corner_radius=12)
        self._savings_card.grid(row=3, column=0, padx=24, pady=8, sticky="ew")
        self._savings_card.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Row 2: Sustainability Vector Gauges (Session Totals)
        self._gauges_card = ctk.CTkFrame(f, corner_radius=12)
        self._gauges_card.grid(row=4, column=0, padx=24, pady=8, sticky="ew")
        self._gauges_card.grid_columnconfigure((0, 1, 2, 3), weight=1)

        _SectionLabel(self._gauges_card, "Tracked Resource Context").grid(
            row=0, column=0, columnspan=4, padx=16, pady=(12, 4), sticky="w"
        )

        self.gauge_energy = CTkCircularGauge(
            self._gauges_card, "Energy", "⚡", "kWh", target_value=1.0
        )
        self.gauge_energy.grid(row=1, column=0, padx=10, pady=(0, 12), sticky="nsew")

        self.gauge_emissions = CTkCircularGauge(
            self._gauges_card, "Emissions", "💨", "gCO₂e", target_value=400.0
        )
        self.gauge_emissions.grid(row=1, column=1, padx=10, pady=(0, 12), sticky="nsew")

        self.gauge_water = CTkCircularGauge(
            self._gauges_card, "Water Use", "💧", "L", target_value=2.0
        )
        self.gauge_water.grid(row=1, column=2, padx=10, pady=(0, 12), sticky="nsew")

        self.gauge_embodied = CTkCircularGauge(
            self._gauges_card, "Embodied", "🔩", "gCO₂e", target_value=5.0
        )
        self.gauge_embodied.grid(row=1, column=3, padx=10, pady=(0, 12), sticky="nsew")

        # Row 3: Status & Shares
        self._status_row = ctk.CTkFrame(f, fg_color="transparent")
        self._status_row.grid(row=5, column=0, padx=24, pady=8, sticky="ew")
        self._status_row.grid_columnconfigure((0, 1), weight=1)

        self._power_card = ctk.CTkFrame(self._status_row, corner_radius=12)
        self._power_card.grid(row=0, column=0, padx=(0, 8), pady=0, sticky="nsew")
        self._power_card.grid_columnconfigure(0, weight=1)

        self.battery_gauge = CTkBatteryGauge(self._power_card)
        self.battery_gauge.pack(padx=16, pady=12, fill="both", expand=True)

        self._share_card = ctk.CTkFrame(self._status_row, corner_radius=12)
        self._share_card.grid(row=0, column=1, padx=(8, 0), pady=0, sticky="nsew")
        self._share_card.grid_columnconfigure(0, weight=1)

        self.share_gauge = CTkDispatchShare(self._share_card)
        self.share_gauge.pack(padx=16, pady=12, fill="both", expand=True)

        # Row 4: Session Summary Text Details
        self._telem_card = ctk.CTkFrame(f, corner_radius=12)
        self._telem_card.grid(row=6, column=0, padx=24, pady=8, sticky="ew")
        self._telem_card.grid_columnconfigure((0, 1), weight=1)

        # Row 5: Per Accepted Task ratio KPIs
        self._controls_card = ctk.CTkFrame(f, corner_radius=12)
        self._controls_card.grid(row=7, column=0, padx=24, pady=8, sticky="ew")
        self._controls_card.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Row 6: Per Accepted Task ratio KPIs
        self._per_task_card = ctk.CTkFrame(f, corner_radius=12)
        self._per_task_card.grid(row=8, column=0, padx=24, pady=(8, 24), sticky="ew")
        self._per_task_card.grid_columnconfigure((0, 1, 2), weight=1)

    # ─── Operator Status Panel (TD-003) ────────────────────────────────────────
    def _build_status_panel(self):
        """Build a read-only operator status card at the top of the telemetry frame.
        Powered by the triagedesk_adapter — no direct ledger mutation."""
        f = self.telemetry_frame

        card = ctk.CTkFrame(f, corner_radius=12)
        card.grid(row=0, column=0, padx=24, pady=(12, 4), sticky="ew")
        card.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        self._op_status_card = card

        _SectionLabel(card, "Operator Status").grid(
            row=0, column=0, columnspan=5, padx=16, pady=(12, 8), sticky="w"
        )

        # Create label pairs: (header, value)
        self._op_repo_lbl = self._op_status_chip(card, "Repo", "…", 0)
        self._op_ledger_lbl = self._op_status_chip(card, "Ledger", "…", 1)
        self._op_last_event_lbl = self._op_status_chip(card, "Last Event", "…", 2)
        self._op_reviews_lbl = self._op_status_chip(card, "Pending Reviews", "…", 3)
        self._op_adapter_lbl = self._op_status_chip(card, "Adapter", "…", 4)

    def _op_status_chip(self, parent, header, initial_value, col):
        """Create a small header+value chip in the status card. Returns the value label."""
        chip = ctk.CTkFrame(parent, corner_radius=8, fg_color=("gray85", "gray22"))
        chip.grid(row=1, column=col, padx=6, pady=(0, 12), sticky="nsew")

        ctk.CTkLabel(
            chip, text=header,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#9ca3af", anchor="w",
        ).pack(anchor="w", padx=10, pady=(8, 0))

        val_lbl = ctk.CTkLabel(
            chip, text=initial_value,
            font=ctk.CTkFont(size=12),
            anchor="w",
        )
        val_lbl.pack(anchor="w", padx=10, pady=(2, 8))
        return val_lbl

    def _refresh_status_panel(self):
        """Update the operator status panel from the adapter. Read-only, no mutation."""
        if not _TD_ADAPTER_AVAILABLE or _td_adapter is None:
            self._op_adapter_lbl.configure(text="unavailable")
            return

        try:
            snap = _td_adapter.get_status_snapshot()
            self._op_repo_lbl.configure(text=snap.git_status)
            ledger_text = "exists" if snap.ledger_exists else "missing"
            if snap.ledger_exists and not snap.ledger_writable:
                ledger_text = "read-only"
            self._op_ledger_lbl.configure(text=ledger_text)
            self._op_last_event_lbl.configure(text=snap.last_event_timestamp)
        except Exception:
            self._op_repo_lbl.configure(text="error")
            self._op_ledger_lbl.configure(text="error")
            self._op_last_event_lbl.configure(text="error")

        try:
            rq = _td_adapter.get_review_queue_snapshot()
            count = len(rq.pending_tasks)
            self._op_reviews_lbl.configure(text=str(count) if count > 0 else "none")
        except Exception:
            self._op_reviews_lbl.configure(text="error")

        self._op_adapter_lbl.configure(text="connected")

    # ─── Review Queue Panel (TD-004) ───────────────────────────────────────────
    def _build_review_queue_panel(self):
        """Build a read-only review queue panel at row 1 of the telemetry frame."""
        f = self.telemetry_frame

        card = ctk.CTkFrame(f, corner_radius=12)
        card.grid(row=1, column=0, padx=24, pady=8, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        self._review_queue_card = card

        _SectionLabel(card, "Review Queue").grid(
            row=0, column=0, padx=16, pady=(12, 4), sticky="w"
        )

        self._review_queue_summary_lbl = ctk.CTkLabel(
            card,
            text="Status: checking…",
            text_color="gray",
            font=ctk.CTkFont(size=12),
            anchor="w",
        )
        self._review_queue_summary_lbl.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="w")

        self._review_list_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._review_list_frame.grid(row=2, column=0, padx=16, pady=(0, 12), sticky="ew")
        self._review_list_frame.grid_columnconfigure(0, weight=1)

    def _refresh_review_queue_panel(self):
        """Update the review queue panel from the adapter."""
        # Clear existing items
        for w in self._review_list_frame.winfo_children():
            w.destroy()

        if not _TD_ADAPTER_AVAILABLE or _td_adapter is None:
            self._review_queue_summary_lbl.configure(text="Status: unavailable")
            ctk.CTkLabel(
                self._review_list_frame, text="Adapter unavailable. Cannot fetch reviews.",
                text_color="gray", font=ctk.CTkFont(size=12)
            ).pack(anchor="w", pady=4)
            return

        try:
            rq = _td_adapter.get_review_queue_snapshot()
            pending = rq.pending_tasks
        except Exception as e:
            self._review_queue_summary_lbl.configure(text="Status: error")
            ctk.CTkLabel(
                self._review_list_frame, text=f"Error fetching reviews: {e}",
                text_color="#ef4444", font=ctk.CTkFont(size=12)
            ).pack(anchor="w", pady=4)
            return

        if not pending:
            self._review_queue_summary_lbl.configure(
                text="Status: available · 0 pending reviews detected"
            )
            ctk.CTkLabel(
                self._review_list_frame, text="Queue empty. No pending reviews.",
                text_color="gray", font=ctk.CTkFont(size=12)
            ).pack(anchor="w", pady=4)
            return

        self._review_queue_summary_lbl.configure(
            text=f"Status: available · {len(pending)} pending review(s) detected"
        )

        for idx, task in enumerate(pending[:100]):
            row = ctk.CTkFrame(self._review_list_frame, corner_radius=6, fg_color=("gray85", "gray22"))
            row.pack(fill="x", pady=2)

            info = f"[{task.task_id[:8]}] {task.title}  ·  Source: {task.runner}  ·  Status: {task.status}"
            if getattr(task, "updated_at", None):
                info += f"  ·  {task.updated_at}"

            ctk.CTkLabel(
                row, text=info, font=ctk.CTkFont(size=11), anchor="w"
            ).pack(side="left", padx=10, pady=6)

    def _refresh_telemetry(self):
        self._refresh_status_panel()
        self._refresh_review_queue_panel()
        tasks = self.ledger.get_all_tasks()
        accepted = [t for t in tasks if t.accepted]
        n_local = sum(1 for t in tasks if t.runner == "local_llm")
        n_codex = sum(1 for t in tasks if t.runner == "codex")
        n_anti = sum(1 for t in tasks if t.runner == "antigravity")
        n_council = sum(1 for t in tasks if t.runner == "worker_council")

        total_kwh = sum(t.energy_kwh_estimate for t in tasks)
        total_gco2 = sum(t.emissions_gco2e_estimate for t in tasks)
        total_water = sum(t.water_liters_estimate for t in tasks)
        total_embodied = sum(t.embodied_gco2e_allocated for t in tasks)
        total_tok_in = sum(t.estimated_input_tokens for t in tasks)
        total_tok_out = sum(t.estimated_output_tokens for t in tasks)
        total_review = sum(t.human_review_minutes for t in tasks)

        local_benefits = _telemetry_local_benefit_metrics(tasks)

        n_acc = len(accepted) or 1  # avoid div/0

        # Update dynamic visual gauges
        self.gauge_energy.set_value(total_kwh)
        self.gauge_emissions.set_value(total_gco2)
        self.gauge_water.set_value(total_water)
        self.gauge_embodied.set_value(total_embodied)

        self.share_gauge.draw_shares(n_local, n_council, n_codex, n_anti)

        power = PowerMonitor.get_status()
        self.battery_gauge.set_status(
            power.get("percent", 100.0),
            power.get("power_plugged", True),
            power.get("has_battery", False),
        )

        # ── Rebuild savings / avoidance card ─────────────────────────────────
        for w in self._savings_card.winfo_children():
            w.destroy()

        _SectionLabel(self._savings_card, "Local-First Benefits").grid(
            row=0, column=0, columnspan=4, padx=16, pady=(12, 8), sticky="w"
        )

        savings_metrics = [
            ("✓", f"{local_benefits['accepted_yield_pct']:.0f}%", "accepted yield"),
            ("⌂", f"{local_benefits['local_first_pct']:.0f}%", "kept local"),
            ("◆", f"{local_benefits['local_accepted']}", "local accepted work"),
            ("◌", f"{local_benefits['review_light_pct']:.0f}%", "review-light tasks"),
        ]
        for col, (icon, value, label) in enumerate(savings_metrics):
            chip = ctk.CTkFrame(
                self._savings_card, corner_radius=12, fg_color=("gray85", "gray22")
            )
            chip.grid(row=1, column=col, padx=12, pady=(0, 16), sticky="nsew")
            ctk.CTkLabel(
                chip,
                text=f"{icon} {value}",
                font=ctk.CTkFont(size=24, weight="bold"),
            ).pack(padx=18, pady=(16, 4))
            ctk.CTkLabel(
                chip, text=label, font=ctk.CTkFont(size=14), text_color="gray"
            ).pack(padx=18, pady=(0, 16))

        # ── Rebuild session card ──────────────────────────────────────────────
        for w in self._telem_card.winfo_children():
            w.destroy()

        _SectionLabel(self._telem_card, "Resource Ledger Details").grid(
            row=0, column=0, columnspan=2, padx=16, pady=(12, 6), sticky="w"
        )

        rows_left = [
            ("📋 Tasks", f"{len(tasks)} total / {len(accepted)} accepted"),
            ("⚡ Energy", f"{total_kwh:.6f} kWh"),
            ("💧 Water", f"{total_water:.4f} L"),
            ("🔩 Embodied", f"{total_embodied:.4f} gCO₂e"),
        ]
        rows_right = [
            (
                "🏃 Runners",
                f"local {n_local} · council {n_council} · codex {n_codex} · anti {n_anti}",
            ),
            ("💨 Emissions", f"{total_gco2:.4f} gCO₂e"),
            ("🎫 Tokens", f"{total_tok_in} in / {total_tok_out} out"),
            ("🕐 Review", f"{total_review:.1f} min"),
        ]
        for r, (lbl, val) in enumerate(rows_left):
            ctk.CTkLabel(
                self._telem_card, text=lbl, font=ctk.CTkFont(size=12), text_color="gray"
            ).grid(row=r + 1, column=0, padx=(16, 4), pady=3, sticky="w")
            ctk.CTkLabel(
                self._telem_card, text=val, font=ctk.CTkFont(size=12, weight="bold")
            ).grid(row=r + 1, column=0, padx=(120, 4), pady=3, sticky="w")
        for r, (lbl, val) in enumerate(rows_right):
            ctk.CTkLabel(
                self._telem_card, text=lbl, font=ctk.CTkFont(size=12), text_color="gray"
            ).grid(row=r + 1, column=1, padx=(16, 4), pady=3, sticky="w")
            ctk.CTkLabel(
                self._telem_card, text=val, font=ctk.CTkFont(size=12, weight="bold")
            ).grid(row=r + 1, column=1, padx=(130, 16), pady=3, sticky="w")

        ctk.CTkFrame(self._telem_card, height=1, fg_color="gray40").grid(
            row=6, column=0, columnspan=2, padx=16, pady=6, sticky="ew"
        )

        # ── Integrated telemetry controls ────────────────────────────────────
        for w in self._controls_card.winfo_children():
            w.destroy()

        _SectionLabel(self._controls_card, "Integrated Controls").grid(
            row=0, column=0, columnspan=4, padx=16, pady=(12, 8), sticky="w"
        )

        control_summary = _telemetry_control_summary(
            tasks,
            log_tail=_read_text_tail(_log_file_path(), max_lines=200),
            token_credit_allowance=default_config.get_global(
                "budgets", "token_credit_allowance", 0
            ),
        )
        tone_map = {
            "ok": ("#22c55e", "#0b1f14"),
            "warn": ("#f59e0b", "#2f1d04"),
            "alert": ("#ef4444", "#341111"),
        }
        for col, key in enumerate(["early_stop", "firewall", "credit", "stability"]):
            card = control_summary[key]
            accent, fg = tone_map[card["tone"]]
            chip = ctk.CTkFrame(self._controls_card, corner_radius=12, fg_color=fg)
            chip.grid(row=1, column=col, padx=12, pady=(0, 16), sticky="nsew")
            ctk.CTkLabel(
                chip,
                text=card["title"],
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=accent,
            ).pack(anchor="w", padx=16, pady=(14, 4))
            ctk.CTkLabel(
                chip,
                text=card["value"],
                font=ctk.CTkFont(size=24, weight="bold"),
            ).pack(anchor="w", padx=16, pady=(0, 4))
            ctk.CTkLabel(
                chip,
                text=card["detail"],
                justify="left",
                wraplength=210,
                text_color="#cbd5e1",
                font=ctk.CTkFont(size=12),
            ).pack(anchor="w", padx=16, pady=(0, 14))

        # ── Per-accepted-task card ────────────────────────────────────────────
        for w in self._per_task_card.winfo_children():
            w.destroy()

        _SectionLabel(
            self._per_task_card, "Efficiency Per Accepted Task"
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
            chip = ctk.CTkFrame(
                self._per_task_card, corner_radius=12, fg_color=("gray85", "gray22")
            )
            chip.grid(row=1, column=col % 3, padx=12, pady=(0, 16), sticky="nsew")
            self._per_task_card.grid_columnconfigure(col % 3, weight=1)
            ctk.CTkLabel(
                chip, text=f"{icon} {val}", font=ctk.CTkFont(size=24, weight="bold")
            ).pack(padx=20, pady=(16, 4))
            ctk.CTkLabel(
                chip, text=lbl, font=ctk.CTkFont(size=14), text_color="gray"
            ).pack(padx=20, pady=(0, 16))
            if col == 2:  # wrap to next row
                self._per_task_card.grid_rowconfigure(2, weight=0)
                for c2, (icon2, val2, lbl2) in enumerate(per_metrics[3:]):
                    chip2 = ctk.CTkFrame(
                        self._per_task_card,
                        corner_radius=12,
                        fg_color=("gray85", "gray22"),
                    )
                    chip2.grid(row=2, column=c2, padx=12, pady=(0, 16), sticky="nsew")
                    ctk.CTkLabel(
                        chip2,
                        text=f"{icon2} {val2}",
                        font=ctk.CTkFont(size=24, weight="bold"),
                    ).pack(padx=20, pady=(16, 4))
                    ctk.CTkLabel(
                        chip2, text=lbl2, font=ctk.CTkFont(size=14), text_color="gray"
                    ).pack(padx=20, pady=(0, 16))
                break

    # ─── Frame Navigation ─────────────────────────────────────────────────────
    def select_frame(self, name):
        if not UI_AVAILABLE:
            return
        self.dispatch_frame.grid_forget()
        self.planner_frame.grid_forget()
        self.ledger_frame.grid_forget()
        self.telemetry_frame.grid_forget()
        self.logs_frame.grid_forget()
        self.rules_frame.grid_forget()
        self._current_frame = name

        # Highlight active nav button
        for key, btn in self._nav_btns.items():
            if key == name:
                btn.configure(fg_color=("gray70", "gray30"))
            else:
                btn.configure(fg_color="transparent")

        if name == "dashboard":
            self.dispatch_frame.grid(row=0, column=1, sticky="nsew")
            self.telemetry_frame.grid(row=1, column=1, sticky="nsew")
            self._refresh_telemetry()
            self._refresh_compact_ledger_feed()
            self._update_workflow_glow()
        elif name == "ledger":
            self.ledger_frame.grid(row=0, column=1, rowspan=2, sticky="nsew")
            self._refresh_ledger()
        elif name == "planner":
            self.planner_frame.grid(row=0, column=1, rowspan=2, sticky="nsew")
        elif name == "logs":
            self.logs_frame.grid(row=0, column=1, rowspan=2, sticky="nsew")
            self._refresh_logs()
        elif name == "rules":
            self.rules_frame.grid(row=0, column=1, rowspan=2, sticky="nsew")
            self._load_rules_toml()

    # ─── Live Ticker ─────────────────────────────────────────────────────────
    def _start_ticker(self):
        self._update_ticker()

    def _update_ticker(self):
        try:
            tasks = self.ledger.get_all_tasks()
            kwh = sum(t.energy_kwh_estimate for t in tasks)
            gco2 = sum(t.emissions_gco2e_estimate for t in tasks)
            water = sum(t.water_liters_estimate for t in tasks)
            embodied = sum(t.embodied_gco2e_allocated for t in tasks)

            self._t_energy.set_value(f"{kwh:.6f} kWh")
            self._t_emissions.set_value(f"{gco2:.4f} gCO₂e")
            self._t_water.set_value(f"{water:.4f} L")
            self._t_embodied.set_value(f"{embodied:.4f} gCO₂e")
            if getattr(self, "_current_frame", None) == "dashboard":
                self._refresh_compact_ledger_feed(force=False)
        except Exception:
            pass

        self.after(5000, self._update_ticker)

    # ─── Backend Check / Runtime Observability ────────────────────────────────
    def _backend_label(self, backend):
        if not backend:
            return "none"
        name = getattr(backend, "name", None) or "unknown"
        if name == "lmstudio":
            return "LM Studio"
        if name == "ollama":
            return "Ollama"
        return name

    def _model_label(self, backend):
        if not backend:
            return "none"
        model = getattr(backend, "model", None) or "auto"
        if (
            getattr(backend, "name", "") == "lmstudio"
            and model in {"", "auto", "loaded-model", "local-model"}
        ):
            return "auto (loaded in LM Studio)"
        return model

    def _lmstudio_runtime_status(self, base_url=None, timeout=0.75):
        import requests

        base_url = (base_url or os.getenv("TRIAGE_SUPERVISOR_BASE_URL", "http://localhost:1234/v1")).rstrip("/")
        root_url = base_url[:-3] if base_url.endswith("/v1") else base_url
        candidates = [
            f"{root_url}/api/v1/models",
            f"{base_url}/models",
        ]
        info = {
            "provider": "lmstudio",
            "online": False,
            "base_url": base_url,
            "models": [],
            "display": "LM Studio inventory unknown",
        }

        for url in candidates:
            try:
                response = requests.get(url, timeout=timeout)
                if response.status_code != 200:
                    continue
                data = response.json()
                models = []
                raw_models = data.get("data") if isinstance(data, dict) else None
                if raw_models is None and isinstance(data, dict):
                    raw_models = data.get("models")
                if raw_models is None and isinstance(data, list):
                    raw_models = data
                for item in raw_models or []:
                    if isinstance(item, dict):
                        model_id = item.get("id") or item.get("model") or item.get("name") or item.get("path")
                        state = item.get("state") or item.get("status")
                        if model_id:
                            models.append(f"{model_id} ({state})" if state else str(model_id))
                    elif item:
                        models.append(str(item))
                info["online"] = True
                info["models"] = models
                if models:
                    shown = ", ".join(models[:2])
                    if len(models) > 2:
                        shown += f", +{len(models) - 2} more"
                    info["display"] = f"LM Studio inventory: {shown}"
                else:
                    info["display"] = "LM Studio online, no models listed"
                return info
            except Exception:
                continue

        return info

    def _lmstudio_runtime_label(self):
        info = getattr(self, "lmstudio_runtime_status", None) or {}
        return info.get("display", "LM Studio inventory unknown")

    def _native_ollama_status(self, timeout=0.75):
        import requests

        base_url = os.getenv("TRIAGE_OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        info = {
            "provider": "ollama",
            "online": False,
            "base_url": base_url,
            "models": [],
            "display": "Ollama offline",
        }
        try:
            response = requests.get(f"{base_url}/api/tags", timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                models = []
                for item in data.get("models", []) or []:
                    if isinstance(item, dict):
                        name = item.get("name") or item.get("model")
                        if name:
                            models.append(name)
                    elif item:
                        models.append(str(item))
                info["online"] = True
                info["models"] = models
                if models:
                    info["display"] = f"Ollama online, {len(models)} model(s)"
                else:
                    info["display"] = "Ollama online, no models listed"
        except Exception:
            pass
        return info

    def _worker_pool_label(self):
        info = getattr(self, "worker_pool_status", None) or {}
        if not info:
            return "unknown"
        return info.get("display", "unknown")

    def _runtime_trace(self, runner_type):
        control = self._backend_label(
            getattr(self, "control_plane_backend", None) or getattr(self, "active_backend", None)
        )
        control_model = self._model_label(
            getattr(self, "control_plane_backend", None) or getattr(self, "active_backend", None)
        )
        workers = self._worker_pool_label()

        if runner_type == "local":
            return f"Route: UI -> Control Plane<{control}/{control_model}> -> Local Draft"
        if runner_type == "council":
            return f"Route: UI -> Worker Council<{workers}> -> RepoMapper/CodeRepair/Validator"
        if runner_type == "pipeline":
            return f"Route: UI -> Pipeline -> Control Plane<{control}/{control_model}> -> Review/Handoff"
        if runner_type == "codex":
            return "Route: UI -> Codex Handoff Packet"
        if runner_type == "antigravity":
            return "Route: UI -> Antigravity Task Bundle"
        return f"Route: UI -> {runner_type}"

    def _check_backends(self):
        from ..backends import create_backend
        from ..config import default_config

        def _check():
            model = default_config.get_backend_model()
            supervisor_base_url = os.getenv(
                "TRIAGE_SUPERVISOR_BASE_URL", "http://localhost:1234/v1"
            )
            self.lmstudio_runtime_status = self._lmstudio_runtime_status(supervisor_base_url)
            self.worker_pool_status = self._native_ollama_status()

            # Control-plane first: LM Studio is the supervisor/control surface.
            lmstudio = create_backend(
                "lmstudio",
                base_url=supervisor_base_url,
                model=model,
            )
            if lmstudio.ping():
                self.control_plane_backend = lmstudio
                self.active_backend = lmstudio
                model_label = self._model_label(lmstudio)
                worker_label = self._worker_pool_label()
                self.backend_status_label.configure(
                    text=(
                        f"Control Plane: LM Studio online · requested: {model_label} · "
                        f"{self._lmstudio_runtime_label()}  |  Worker Pool: {worker_label}"
                    ),
                    text_color="#22c55e",
                )
                self._t_backend.configure(
                    text="Control: LM Studio online",
                    text_color="#22c55e",
                )
                self._t_model.configure(
                    text=f"Requested: {model_label} · {self._lmstudio_runtime_label()} · Workers: {worker_label}",
                    text_color="#93c5fd",
                )
                self._log_activity(
                    "Runtime map updated: "
                    f"control=LM Studio base={supervisor_base_url} model={model_label}; "
                    f"workers={worker_label}"
                )
                return

            # Fallback path: native Ollama can still serve as a single local engine.
            ollama_model = os.getenv("TRIAGE_OLLAMA_MODEL", model)
            ollama = create_backend("ollama", model=ollama_model)
            # Use native status here because OllamaBackend.ping may intentionally
            # decline the control-plane role when LM Studio is available.
            if (getattr(self, "worker_pool_status", {}) or {}).get("online"):
                self.control_plane_backend = None
                self.active_backend = ollama
                model_label = self._model_label(ollama)
                self.backend_status_label.configure(
                    text=f"Fallback Engine: Ollama online · {model_label}",
                    text_color="#22c55e",
                )
                self._t_backend.configure(
                    text="Fallback: Ollama online",
                    text_color="#22c55e",
                )
                self._t_model.configure(text=f"Model: {model_label}", text_color="#93c5fd")
                self._log_activity(f"Runtime map updated: fallback=Ollama model={model_label}")
                return

            self.control_plane_backend = None
            self.active_backend = None
            self.backend_status_label.configure(
                text="Runtime: Offline (Start LM Studio or Ollama)",
                text_color="#ef4444",
            )
            self._t_backend.configure(text="Offline", text_color="#ef4444")
            self._t_model.configure(text="-")

        threading.Thread(target=_check, daemon=True).start()

    # ─── Task Dispatch ────────────────────────────────────────────────────────
    def _handle_task(self, runner_type):
        prompt = self.prompt_box.get("0.0", "end").strip()
        files_str = self.files_entry.get().strip()
        files = [f.strip() for f in files_str.split(",") if f.strip()]

        if not prompt or prompt == "Describe your task here…":
            self.status_label.configure(
                text="Error: Prompt is required.", text_color="#ef4444"
            )
            return

        task_id = str(uuid.uuid4())
        self.current_loaded_task_id = task_id
        self.ledger.append_event(
            task_id,
            "task_created",
            {
                "title": prompt[:40] + ("…" if len(prompt) > 40 else ""),
                "description": prompt,
                "target_files": files,
            },
        )
        self._log_activity(f"Task {task_id[:8]} created for {runner_type}")
        self._refresh_compact_ledger_feed()

        cat = TaskClassifier.classify(prompt, backend=self.active_backend)
        danger = DangerDetector.analyze(prompt, files)
        self.ledger.append_event(
            task_id,
            "task_classified",
            {
                "category": cat,
                "risk_level": danger.risk_level,
                "recommended_profile": danger.recommended_profile,
                "reasons": danger.reasons,
            },
        )
        runner_label = self._context_runner_label(runner_type)
        context_pack, context_path, context_payload = create_context_pack_artifact(
            task_id=task_id,
            prompt=prompt,
            files=files,
            runner=runner_label,
            category=cat,
            ledger_dir=default_config.get_ledger_dir(),
        )
        self.ledger.append_event(task_id, "context_budgeted", context_payload)
        self._log_activity(
            "Context pack created "
            f"for task {task_id[:8]}: {context_pack.estimated_tokens}/"
            f"{context_pack.budget_tokens} tokens ({context_pack.budget_status})"
        )
        if context_pack.budget_status == "over_budget":
            self.status_label.configure(
                text=(
                    "Context budget warning: "
                    f"{context_pack.estimated_tokens}/{context_pack.budget_tokens} tokens"
                ),
                text_color="#f97316",
            )

        power = PowerMonitor.get_status()
        is_heavy = danger.risk_level in ["medium", "high"] or runner_type in [
            "local",
            "council",
        ]
        if (
            power["has_battery"]
            and not power["power_plugged"]
            and power["percent"] < 20
            and is_heavy
        ):
            self.ledger.append_event(
                task_id,
                "task_blocked",
                {"reason": f"Low battery ({power['percent']}%) without AC power."},
            )
            self.status_label.configure(
                text=f"⚠ Deferred: Battery {power['percent']:.0f}% — plug in before heavy tasks.",
                text_color="#f97316",
            )
            return

        if runner_type == "local":
            self._dispatch_local(task_id, prompt, files, danger)

        elif runner_type == "council":
            self._dispatch_council(task_id, prompt, files, danger)

        elif runner_type == "codex":
            self._dispatch_codex(task_id, prompt, files, danger)

        elif runner_type == "antigravity":
            self._dispatch_antigravity(task_id, prompt, files, danger)

        elif runner_type == "pipeline":
            self._dispatch_pipeline(task_id, prompt, files, danger)

    @staticmethod
    def _context_runner_label(runner_type: str) -> str:
        return {
            "local": "local_llm",
            "council": "worker_council",
            "codex": "codex",
            "antigravity": "antigravity",
            "pipeline": "pipeline",
        }.get(runner_type, runner_type)

    # -- Local --
    def _dispatch_local(self, task_id, prompt, files, danger):
        if not self.active_backend:
            self.status_label.configure(
                text="Error: No local engine active.", text_color="#ef4444"
            )
            return

        route_trace = self._runtime_trace("local")
        self.last_route_trace = route_trace
        self.ledger.append_event(
            task_id,
            "runner_selected",
            {
                "runner": "local_llm",
                "route_trace": route_trace,
                "control_plane": self._backend_label(self.active_backend),
                "control_model": self._model_label(self.active_backend),
            },
        )
        self.status_label.configure(
            text=f"{route_trace}…",
            text_color="#93c5fd",
        )
        self._log_activity(
            f"Local draft started for task {task_id[:8]} via {self.active_backend.name}"
        )
        self.btn_local.configure(state="disabled")
        self._clear_output(f"{route_trace}\n\nSending to local model…")

        def _run():
            from ..sustainability import PowerSampler, integrate_energy_kwh
            from ..config import default_config

            sampler = PowerSampler()
            sampler.start()
            t0 = time.time()
            try:
                messages = [
                    {
                        "role": "system",
                        "content": "You are a local coding assistant. Output minimal, correct code.",
                    },
                    {
                        "role": "user",
                        "content": f"Task: {prompt}\nTarget Files: {files}",
                    },
                ]

                def _stream_cb(chunk):
                    self.after(0, self._append_output, chunk)

                resp = self.active_backend.generate(
                    messages, stream_callback=_stream_cb
                )
                served_model = resp.raw.get("model") or self._model_label(self.active_backend)
                self.last_served_model = served_model
                duration = time.time() - t0
                samples = sampler.stop()

                default_w = default_config.get_global(
                    "sustainability", "default_watts", 300.0
                )
                energy_kwh, avg_watts, power_source = integrate_energy_kwh(
                    samples, duration, default_w
                )

                metrics = SustainabilityEstimator.estimate(
                    duration_seconds=duration, watts=avg_watts
                )
                metrics["energy_kwh"] = energy_kwh
                metrics["power_source"] = power_source

                tokens_in = resp.usage.get("prompt_tokens", 0)
                tokens_out = resp.usage.get("completion_tokens", 0)

                self.ledger.append_event(
                    task_id,
                    "local_draft_generated",
                    {
                        "status": "success",
                        "duration_seconds": duration,
                        "backend": self.active_backend.name,
                        "model": served_model,
                        "requested_model": self.active_backend.model,
                        "served_model": served_model,
                        "route_trace": route_trace,
                        "control_plane": self._backend_label(self.active_backend),
                        "control_model": self._model_label(self.active_backend),
                        "input_tokens": tokens_in,
                        "output_tokens": tokens_out,
                        **metrics,
                    },
                )
                self.review_timers[task_id] = time.time()
                self.ledger.append_event(task_id, "energy_estimated", metrics)

                self._show_result_metrics(
                    served_model,
                    self.active_backend.name,
                    tokens_in,
                    tokens_out,
                    duration,
                    metrics["energy_kwh"],
                    metrics["emissions_gco2e"],
                    metrics["water_liters_estimate"],
                    metrics["embodied_gco2e_allocated"],
                )

                self.status_label.configure(
                    text=f"✓ Draft in {duration:.1f}s · Served: {served_model} · Risk: {danger.risk_level}",
                    text_color="#22c55e",
                )
                self._log_activity(
                    f"Local draft completed for task {task_id[:8]} in {duration:.1f}s"
                )
            except Exception as e:
                sampler.stop()
                self.status_label.configure(text=f"Error: {e}", text_color="#ef4444")
                self._log_activity(f"Local draft error for task {task_id[:8]}: {e}", level="error")
            finally:
                self.btn_local.configure(state="normal")
                self._update_ticker()
                self.after(0, self._update_workflow_glow)

        threading.Thread(target=_run, daemon=True).start()

    # -- Worker Council --
    def _dispatch_council(self, task_id, prompt, files, danger):
        if not self.active_backend:
            self.status_label.configure(
                text="Error: No local engine active.", text_color="#ef4444"
            )
            return

        route_trace = self._runtime_trace("council")
        self.last_route_trace = route_trace
        self.ledger.append_event(
            task_id,
            "runner_selected",
            {
                "runner": "worker_council",
                "route_trace": route_trace,
                "worker_pool": self._worker_pool_label(),
            },
        )
        self.status_label.configure(
            text=f"{route_trace}…", text_color="#38bdf8"
        )
        self.btn_council.configure(state="disabled")
        self._clear_output(f"{route_trace}\n\nWorker Council initialising…\n")
        self._reset_agent_indicators(queued=True)
        self._log_activity(f"Council dispatch started for task {task_id[:8]}")

        def _run():
            from ..sustainability import PowerSampler, integrate_energy_kwh
            from ..config import default_config

            sampler = PowerSampler()
            sampler.start()
            t0 = time.time()
            try:
                from ..orchestration import ProjectManager

                pm = ProjectManager()
                self._append_output(
                    "  → RepoMapper, CodeRepair, Validator dispatched\n"
                )

                def _stream_cb(chunk):
                    if "IS THINKING" in chunk and "---" in chunk:
                        import re

                        match = re.search(r"\[(.*?)\]", chunk)
                        if match:
                            role = match.group(1).lower()
                            model_match = re.search(r"Model:\s*([^)]+)", chunk)
                            model = model_match.group(1).strip() if model_match else ""
                            detail = f"Model: {model}" if model else "Working"
                            self.after(0, self._set_active_agent, role)
                            self.after(0, self._set_agent_state, role, "running", detail)
                            self._log_activity(f"Council worker running: {role}")
                    self.after(0, self._append_output, chunk)

                result = pm.dispatch_task(
                    prompt=prompt,
                    target_files=files,
                    required_roles=["repo_mapper", "code_repair", "validator"],
                    stream_callback=_stream_cb,
                )
                duration = time.time() - t0
                samples = sampler.stop()

                default_w = default_config.get_global(
                    "sustainability", "default_watts", 300.0
                )
                energy_kwh, avg_watts, power_source = integrate_energy_kwh(
                    samples, duration, default_w
                )

                metrics = SustainabilityEstimator.estimate(
                    duration_seconds=duration, watts=avg_watts
                )
                metrics["energy_kwh"] = energy_kwh
                metrics["power_source"] = power_source

                eval_data = result.get("evaluation", {})
                local_status = eval_data.get("local_result_status", "unknown")
                summary = eval_data.get("handoff_summary", "")
                packet_path = result.get("escalation_packet")

                total_in = 0
                total_out = 0
                wasted_tokens = 0
                agent_updates = []
                for order_id in result.get("work_orders", []):
                    order = pm.board.orders.get(order_id)
                    if order and order.result:
                        ru = order.result.get("resource_usage", {})
                        input_tokens = ru.get("input_tokens_est", 0)
                        output_tokens = ru.get("output_tokens_est", 0)
                        duration_seconds = ru.get("duration_seconds", 0.0)
                        total_in += input_tokens
                        total_out += output_tokens

                        val_run = order.result.get("validation_run") or {}
                        failed_val = (val_run and not val_run.get("passed", True))
                        has_error = bool(order.result.get("error")) or order.status == "failed"
                        if failed_val or has_error:
                            wasted_tokens += input_tokens + output_tokens

                        agent_updates.append(
                            {
                                "role": order.assigned_role,
                                "state": "failed" if has_error else "completed",
                                "detail": (
                                    f"{duration_seconds:.1f}s · "
                                    f"{input_tokens + output_tokens} tok"
                                ),
                            }
                        )
                self.after(0, self._apply_agent_updates, agent_updates)

                if local_status == "insufficient":
                    wasted_tokens = total_in + total_out

                self.ledger.append_event(
                    task_id,
                    "council_completed",
                    {
                        "local_result_status": local_status,
                        "reason": eval_data.get("reason"),
                        "recommended_escalation": eval_data.get("recommended_escalation"),
                        "early_stopped": eval_data.get("early_stopped", False),
                        "early_stop_reason": eval_data.get("early_stop_reason", ""),
                        "firewall_triggered": eval_data.get("firewall_triggered", False),
                        "firewall_reason": eval_data.get("firewall_reason", ""),
                        "credit_allowance_total": eval_data.get("credit_allowance_total", 0),
                        "credit_allowance_used": eval_data.get("credit_allowance_used", 0),
                        "credit_allowance_remaining": eval_data.get("credit_allowance_remaining", 0),
                        "credit_allowance_exhausted": eval_data.get("credit_allowance_exhausted", False),
                        "escalation_packet": packet_path,
                        "duration_seconds": duration,
                        "input_tokens": total_in,
                        "output_tokens": total_out,
                        "wasted_tokens": wasted_tokens,
                        **metrics,
                    },
                )
                self.review_timers[task_id] = time.time()
                self.ledger.append_event(task_id, "energy_estimated", metrics)

                self._show_result_metrics(
                    "Council roles",
                    "Ollama worker pool",
                    total_in,
                    total_out,
                    duration,
                    metrics["energy_kwh"],
                    metrics["emissions_gco2e"],
                    metrics["water_liters_estimate"],
                    metrics["embodied_gco2e_allocated"],
                )

                out = f"\nCouncil Result: {local_status.upper()}\n\n{summary}"
                if packet_path:
                    out += f"\n\n📦 Escalation packet: {packet_path}"

                if local_status == "sufficient" and files:
                    repaired_code = None
                    for order_id in result.get("work_orders", []):
                        order = pm.board.orders.get(order_id)
                        if order and order.assigned_role == "code_repair":
                            order_result = order.result or {}
                            repaired_code = order_result.get("repaired_code")
                            break

                    if repaired_code:
                        target_file = files[0]
                        try:
                            with open(target_file, "w", encoding="utf-8") as f:
                                f.write(repaired_code)
                            out += f"\n\n✓ Seamless Operation: Successfully hardened and updated {target_file}"
                        except Exception as e:
                            out += f"\n\n⚠ Failed to write repaired code to {target_file}: {e}"

                self._append_output(out)

                color = "#22c55e" if local_status == "sufficient" else "#f97316"
                self.status_label.configure(
                    text=f"🏭 Council: {local_status} · {duration:.1f}s",
                    text_color=color,
                )
                self._log_activity(
                    f"Council completed task {task_id[:8]}: {local_status} in {duration:.1f}s"
                )
            except Exception as e:
                sampler.stop()
                self.status_label.configure(
                    text=f"Council error: {e}", text_color="#ef4444"
                )
                self._append_output(f"\nError: {e}")
                self._log_activity(f"Council error for task {task_id[:8]}: {e}", level="error")
            finally:
                self.btn_council.configure(state="normal")
                self._set_active_agent(None)
                self._update_ticker()
                self.after(0, self._update_workflow_glow)

        threading.Thread(target=_run, daemon=True).start()

    # -- Codex --
    def _dispatch_codex(self, task_id, prompt, files, danger):
        from ..handoff import HandoffPacket

        self.ledger.append_event(task_id, "runner_selected", {"runner": "codex"})
        filename = _codex_task_path(task_id)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        packet = HandoffPacket(
            title=f"Task: {prompt[:30]}",
            summary=prompt,
            context="",
            target_files=files,
            constraints=["Follow local codebase styling."],
            acceptance_criteria=["Tests pass."],
            test_commands=["pytest tests/"],
            safety_notes=danger.reasons,
            recommended_backend="Codex",
            recommended_permission_profile=danger.recommended_profile,
            risk_level=danger.risk_level,
        )
        with open(filename, "w", encoding="utf-8") as fh:
            fh.write(packet.to_markdown())
        self.ledger.append_event(
            task_id, "handoff_generated", {"artifact_path": filename}
        )
        self.review_timers[task_id] = time.time()
        self._clear_output(
            f"📦 Codex packet saved to:\n{filename}\n\nProfile: {danger.recommended_profile}"
        )
        self.status_label.configure(
            text=f"📦 Codex packet saved · {danger.recommended_profile}",
            text_color="#f97316",
        )
        self._log_activity(f"Codex packet saved for task {task_id[:8]}: {filename}")
        self._update_workflow_glow()

    # -- Antigravity --
    def _dispatch_antigravity(self, task_id, prompt, files, danger):
        from ..handoff import HandoffPacket

        self.ledger.append_event(task_id, "runner_selected", {"runner": "antigravity"})
        task_dir = _antigravity_task_dir(task_id)
        os.makedirs(task_dir, exist_ok=True)
        packet = HandoffPacket(
            title=f"Task: {prompt[:30]}",
            summary=prompt,
            context="",
            target_files=files,
            constraints=["Follow local codebase styling."],
            acceptance_criteria=["Tests pass."],
            test_commands=["pytest tests/"],
            safety_notes=danger.reasons,
            recommended_backend="Antigravity",
            recommended_permission_profile=danger.recommended_profile,
            risk_level=danger.risk_level,
        )
        task_file = f"{task_dir}/TASK.md"
        with open(task_file, "w", encoding="utf-8") as fh:
            fh.write(packet.to_markdown())
        self.ledger.append_event(
            task_id, "handoff_generated", {"artifact_path": task_file}
        )
        self.review_timers[task_id] = time.time()
        self._clear_output(
            f"🚀 Antigravity bundle saved to:\n{task_dir}/\n\nProfile: {danger.recommended_profile}"
        )
        self.status_label.configure(
            text=f"🚀 Antigravity bundle saved · {danger.recommended_profile}",
            text_color="#a855f7",
        )
        self._log_activity(f"Antigravity bundle saved for task {task_id[:8]}: {task_dir}")
        self._update_workflow_glow()

    # -- Pipeline --
    def _dispatch_pipeline(self, task_id, prompt, files, danger):
        if not self.active_backend:
            self.status_label.configure(
                text="Error: No local engine active.", text_color="#ef4444"
            )
            return

        self.ledger.append_event(task_id, "runner_selected", {"runner": "pipeline"})
        self.status_label.configure(
            text=f"Pipeline: Local Draft via {self.active_backend.name} (In Progress ⏳)…",
            text_color="#b45309",
        )
        self._log_activity(
            f"Pipeline started for task {task_id[:8]} via {self.active_backend.name}"
        )
        self.btn_pipeline.configure(state="disabled")
        self._clear_output("Pipeline Step 1: Sending to local model…")

        def _run():
            from ..sustainability import PowerSampler, integrate_energy_kwh
            from ..config import default_config

            sampler = PowerSampler()
            sampler.start()
            t0 = time.time()
            try:
                messages = [
                    {
                        "role": "system",
                        "content": "You are a local coding assistant. Output minimal, correct code.",
                    },
                    {
                        "role": "user",
                        "content": f"Task: {prompt}\nTarget Files: {files}",
                    },
                ]

                def _stream_cb(chunk):
                    self.after(0, self._append_output, chunk)

                resp = self.active_backend.generate(
                    messages, stream_callback=_stream_cb
                )
                duration = time.time() - t0
                samples = sampler.stop()

                default_w = default_config.get_global(
                    "sustainability", "default_watts", 300.0
                )
                energy_kwh, avg_watts, power_source = integrate_energy_kwh(
                    samples, duration, default_w
                )

                metrics = SustainabilityEstimator.estimate(
                    duration_seconds=duration, watts=avg_watts
                )
                metrics["energy_kwh"] = energy_kwh
                metrics["power_source"] = power_source

                tokens_in = resp.usage.get("prompt_tokens", 0)
                tokens_out = resp.usage.get("completion_tokens", 0)

                # Need to simulate validation failure if it's complex or has risk level > low
                # to trigger the council pipeline handoff. For this prototype, if it's
                # medium or high risk, we fail it to test the pipeline.
                validator_passed = danger.risk_level == "low"

                self.ledger.append_event(
                    task_id,
                    "local_draft_generated",
                    {
                        "status": "success",
                        "duration_seconds": duration,
                        "backend": self.active_backend.name,
                        "model": self.active_backend.model,
                        "input_tokens": tokens_in,
                        "output_tokens": tokens_out,
                        "validator_passed": validator_passed,
                        **metrics,
                    },
                )
                self.review_timers[task_id] = time.time()
                self.ledger.append_event(task_id, "energy_estimated", metrics)

                self._show_result_metrics(
                    served_model,
                    self.active_backend.name,
                    tokens_in,
                    tokens_out,
                    duration,
                    metrics["energy_kwh"],
                    metrics["emissions_gco2e"],
                    metrics["water_liters_estimate"],
                    metrics["embodied_gco2e_allocated"],
                )

                if not validator_passed:
                    self.status_label.configure(
                        text=f"Local draft failed validation. Escalating to Council (In Progress ⏳)…",
                        text_color="#b45309",
                    )
                    self._log_activity(f"Pipeline escalating task {task_id[:8]} to Worker Council")
                    self.after(1000, lambda: self._dispatch_council(task_id, prompt, files, danger))
                else:
                    self.status_label.configure(
                        text=f"✓ Pipeline completed in {duration:.1f}s · Risk: {danger.risk_level}",
                        text_color="#22c55e",
                    )
                    self._log_activity(
                        f"Pipeline completed for task {task_id[:8]} in {duration:.1f}s"
                    )
            except Exception as e:
                sampler.stop()
                self.status_label.configure(text=f"Error: {e}", text_color="#ef4444")
                self._log_activity(f"Pipeline error for task {task_id[:8]}: {e}", level="error")
            finally:
                self.btn_pipeline.configure(state="normal")
                self._update_ticker()
                self.after(0, self._update_workflow_glow)

        threading.Thread(target=_run, daemon=True).start()

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

    # ─── IPC File Watcher ─────────────────────────────────────────────────────
    def _set_agent_state(self, role, state, detail=""):
        if role not in self.agent_indicators:
            return

        color, label = _agent_state_style(state)
        self.agent_status[role] = state
        self.agent_indicators[role].configure(fg_color=color)
        self.agent_status_labels[role].configure(text=label, text_color=color)

        timestamp = datetime.now().strftime("%H:%M:%S")
        detail_text = detail or "Awaiting work"
        self.agent_meta_labels[role].configure(text=f"{detail_text} · {timestamp}")

    def _reset_agent_indicators(self, queued=False):
        state = "queued" if queued else "idle"
        detail = "Queued for council run" if queued else "Awaiting task"
        for role in self.agent_indicators:
            self._set_agent_state(role, state, detail)

    def _apply_agent_updates(self, updates):
        for update in updates:
            self._set_agent_state(
                update.get("role"),
                update.get("state", "idle"),
                update.get("detail", ""),
            )

    def _set_active_agent(self, active_role: str = None):
        if active_role is None:
            for role, state in list(self.agent_status.items()):
                if state in {"queued", "running"}:
                    self._set_agent_state(role, "idle", "No active council work")
            return

        for role, state in list(self.agent_status.items()):
            if role == active_role:
                continue
            if state == "running":
                self._set_agent_state(role, "queued", "Waiting for next worker")
        self._set_agent_state(active_role, "running", "Working")

    def _start_ipc_watcher(self):
        self._check_ipc_inbox()

    def _check_ipc_inbox(self):
        try:
            inbox_path = _ipc_inbox_path()
            if os.path.exists(inbox_path):
                import json

                with open(inbox_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                os.remove(inbox_path)

                # Bring window to front
                if self.state() == "iconic":
                    self.state("zoomed")
                self.lift()
                self.focus_force()

                # Inject prompt
                prompt = payload.get("prompt", "")
                if prompt:
                    self.prompt_box.delete("0.0", "end")
                    self.prompt_box.insert("0.0", prompt)
                    self.prompt_box.configure(text_color=("gray10", "#DCE4EE"))

                # Inject files
                files = payload.get("files", [])
                if files:
                    self.files_entry.delete(0, "end")
                    self.files_entry.insert(0, ", ".join(files))

                # Handle auto dispatch
                auto_dispatch = payload.get("auto_dispatch")
                if auto_dispatch:
                    # Give UI a moment to visually update before dispatching
                    self.after(500, lambda: self._handle_task(auto_dispatch))

        except Exception as e:
            print(f"IPC Watcher Error: {e}")
        finally:
            self.after(1000, self._check_ipc_inbox)

    def _get_glow_target(self, task) -> Optional[str]:
        if not task:
            return "local"

        if task.status == "pending":
            return "local"

        if task.status == "local_draft_generated":
            if task.validator_passed is False:
                return "council"
            return None

        if task.status == "handoff_generated":
            if task.runner == "local_llm":
                return "council"
            return "codex"

        if task.status == "council_completed":
            if getattr(task, "observed_status", "") != "sufficient":
                return "codex"
            return None

        if task.status == "reviewed" and not task.accepted:
            return "council"

        return None

    def _update_workflow_glow(self):
        if not UI_AVAILABLE:
            return

        task_id = getattr(self, "current_loaded_task_id", None)
        task = self.ledger.get_task(task_id) if task_id else None

        if not task:
            tasks = self.ledger.get_all_tasks()
            if tasks:
                task = tasks[0]
                self.current_loaded_task_id = task.task_id

        target = self._get_glow_target(task)

        # Reset all glows
        self.glow_local.configure(border_width=0)
        self.glow_council.configure(border_width=0)
        self.glow_codex.configure(border_width=0)
        self.glow_anti.configure(border_width=0)

        if target == "local":
            self.glow_local.configure(border_width=2, border_color="#22c55e")
        elif target == "council":
            self.glow_council.configure(border_width=2, border_color="#3b82f6")
        elif target == "codex":
            self.glow_codex.configure(border_width=2, border_color="#f97316")
        elif target == "antigravity":
            self.glow_anti.configure(border_width=2, border_color="#a855f7")


# ─── Entry Point ──────────────────────────────────────────────────────────────


def run_app():
    if not UI_AVAILABLE:
        print("Error: customtkinter is not installed. Run `pip install triagecore[ui]`")
        return
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    app = TriageDeskApp()
    app.mainloop()
