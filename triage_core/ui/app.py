try:
    import customtkinter as ctk
    from PIL import Image
    UI_AVAILABLE = True
except ImportError:
    UI_AVAILABLE = False
    class ctk:
        CTk = object

import os
import uuid
from ..task_ledger import TaskLedger
from ..classifier import DangerDetector, TaskClassifier
from ..sustainability import SustainabilityEstimator

class TriageDeskApp(ctk.CTk if UI_AVAILABLE else object):
    def __init__(self):
        if not UI_AVAILABLE:
            print("Error: customtkinter is not installed. Run `pip install triagecore[ui]`")
            return
            
        super().__init__()
        
        self.ledger = TaskLedger()
        
        self.title("TriageDesk Control Plane")
        self.geometry("900x600")
        
        # Configure grid layout (1x2)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # Determine icon path safely
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(current_dir, "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass
        
        # --- Sidebar ---
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="TriageDesk", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.btn_dispatch = ctk.CTkButton(self.sidebar_frame, text="Dispatch Task", command=lambda: self.select_frame("dispatch"))
        self.btn_dispatch.grid(row=1, column=0, padx=20, pady=10)
        
        self.btn_ledger = ctk.CTkButton(self.sidebar_frame, text="Task Ledger", command=lambda: self.select_frame("ledger"))
        self.btn_ledger.grid(row=2, column=0, padx=20, pady=10)
        
        self.btn_telemetry = ctk.CTkButton(self.sidebar_frame, text="Telemetry", command=lambda: self.select_frame("telemetry"))
        self.btn_telemetry.grid(row=3, column=0, padx=20, pady=10)
        
        # --- Dispatch Frame ---
        self.dispatch_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.dispatch_frame.grid_columnconfigure(0, weight=1)
        
        self.dispatch_label = ctk.CTkLabel(self.dispatch_frame, text="Create New Task", font=ctk.CTkFont(size=20, weight="bold"))
        self.dispatch_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        
        self.prompt_box = ctk.CTkTextbox(self.dispatch_frame, height=150)
        self.prompt_box.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.prompt_box.insert("0.0", "Describe your task here...")
        
        self.files_entry = ctk.CTkEntry(self.dispatch_frame, placeholder_text="Target Files (comma separated)")
        self.files_entry.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        
        self.buttons_frame = ctk.CTkFrame(self.dispatch_frame, fg_color="transparent")
        self.buttons_frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        
        self.btn_local = ctk.CTkButton(self.buttons_frame, text="Classify & Local Draft", command=lambda: self.handle_task("local"), fg_color="green")
        self.btn_local.pack(side="left", padx=(0, 10))
        
        self.btn_codex = ctk.CTkButton(self.buttons_frame, text="Codex Packet", command=lambda: self.handle_task("codex"), fg_color="orange")
        self.btn_codex.pack(side="left", padx=(0, 10))
        
        self.btn_anti = ctk.CTkButton(self.buttons_frame, text="Antigravity Packet", command=lambda: self.handle_task("antigravity"), fg_color="red")
        self.btn_anti.pack(side="left")
        
        self.status_label = ctk.CTkLabel(self.dispatch_frame, text="", text_color="gray")
        self.status_label.grid(row=4, column=0, padx=20, pady=5, sticky="w")
        
        self.backend_status_label = ctk.CTkLabel(self.dispatch_frame, text="Checking local engines...", text_color="gray")
        self.backend_status_label.grid(row=5, column=0, padx=20, pady=0, sticky="w")
        
        self.output_box = ctk.CTkTextbox(self.dispatch_frame, height=200, state="disabled")
        self.output_box.grid(row=6, column=0, padx=20, pady=10, sticky="nsew")
        
        # --- Ledger Frame ---
        self.ledger_frame = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        self.ledger_frame.grid_columnconfigure(0, weight=1)
        self.ledger_label = ctk.CTkLabel(self.ledger_frame, text="Task Ledger", font=ctk.CTkFont(size=20, weight="bold"))
        self.ledger_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        self.ledger_content_frame = ctk.CTkFrame(self.ledger_frame, fg_color="transparent")
        self.ledger_content_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        
        # --- Telemetry Frame ---
        self.telemetry_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.telemetry_frame.grid_columnconfigure(0, weight=1)
        self.telemetry_label = ctk.CTkLabel(self.telemetry_frame, text="Sustainability Telemetry", font=ctk.CTkFont(size=20, weight="bold"))
        self.telemetry_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        self.telemetry_stats = ctk.CTkLabel(self.telemetry_frame, text="", justify="left", font=ctk.CTkFont(size=14))
        self.telemetry_stats.grid(row=1, column=0, padx=20, pady=10, sticky="w")
        
        self.select_frame("dispatch")
        self.check_backends()

    def check_backends(self):
        import threading
        from ..backends import create_backend
        
        def _check():
            ollama = create_backend("ollama")
            if ollama.ping():
                self.backend_status_label.configure(text="Local Engine: Ollama Connected 🟢", text_color="green")
                self.active_backend = ollama
                return
                
            # Try a custom LM Studio configuration
            lmstudio = create_backend("custom", base_url="http://localhost:1234/v1")
            if lmstudio.ping():
                self.backend_status_label.configure(text="Local Engine: LM Studio Connected 🟢", text_color="green")
                self.active_backend = lmstudio
                return
                
            self.backend_status_label.configure(text="Local Engine: Offline 🔴 (Check Ollama/LM Studio)", text_color="red")
            self.active_backend = None
            
        threading.Thread(target=_check, daemon=True).start()

    def select_frame(self, name):
        if not UI_AVAILABLE: return
        self.dispatch_frame.grid_forget()
        self.ledger_frame.grid_forget()
        self.telemetry_frame.grid_forget()
        
        if name == "dispatch":
            self.dispatch_frame.grid(row=0, column=1, sticky="nsew")
        elif name == "ledger":
            self.ledger_frame.grid(row=0, column=1, sticky="nsew")
            self.refresh_ledger()
        elif name == "telemetry":
            self.telemetry_frame.grid(row=0, column=1, sticky="nsew")
            self.refresh_telemetry()

    def refresh_ledger(self):
        for widget in self.ledger_content_frame.winfo_children():
            widget.destroy()
            
        tasks = self.ledger.get_all_tasks()
        for i, t in enumerate(tasks):
            text = f"[{t.task_id[:8]}] {t.title} | Status: {t.status} | Risk: {t.risk_level} | {t.energy_kwh_estimate:.6f} kWh"
            lbl = ctk.CTkLabel(self.ledger_content_frame, text=text, anchor="w")
            lbl.grid(row=i, column=0, sticky="w", pady=2)

    def refresh_telemetry(self):
        tasks = self.ledger.get_all_tasks()
        total_kwh = sum(t.energy_kwh_estimate for t in tasks)
        total_gco2e = sum(t.emissions_gco2e_estimate for t in tasks)
        local_runs = sum(1 for t in tasks if t.runner == "local_llm")
        
        from ..sustainability import PowerMonitor
        power = PowerMonitor.get_status()
        if power["has_battery"]:
            plug_str = "AC" if power["power_plugged"] else "Battery"
            power_str = f"{power['percent']:.0f}% ({plug_str})"
        else:
            power_str = "AC (No Battery Sensor)"
            
        stats = f"Grid/Power Status: {power_str}\n\n"
        stats += f"Total Local Runs: {local_runs}\n"
        stats += f"Total Energy: {total_kwh:.6f} kWh\n"
        stats += f"Total Emissions: {total_gco2e:.6f} gCO2e"
        self.telemetry_stats.configure(text=stats)

    def handle_task(self, runner_type):
        prompt = self.prompt_box.get("0.0", "end").strip()
        files_str = self.files_entry.get().strip()
        files = [f.strip() for f in files_str.split(",") if f.strip()]
        
        if not prompt or prompt == "Describe your task here...":
            self.status_label.configure(text="Error: Prompt is required.", text_color="red")
            return
            
        task_id = str(uuid.uuid4())
        
        self.ledger.append_event(task_id, "task_created", {
            "title": prompt[:30] + "...",
            "description": prompt,
            "target_files": files
        })
        
        cat = TaskClassifier.classify(prompt)
        danger = DangerDetector.analyze(prompt, files)
        
        self.ledger.append_event(task_id, "task_classified", {
            "category": cat,
            "risk_level": danger.risk_level,
            "recommended_profile": danger.recommended_profile,
            "reasons": danger.reasons
        })
        
        # Power / Deferral Logic
        from ..sustainability import PowerMonitor
        power = PowerMonitor.get_status()
        is_heavy_task = danger.risk_level in ["medium", "high"] or runner_type == "local"
        if power["has_battery"] and not power["power_plugged"] and power["percent"] < 20 and is_heavy_task:
            self.ledger.append_event(task_id, "task_blocked", {
                "reason": f"Deferred heavy task due to low battery ({power['percent']}% without AC power)."
            })
            self.status_label.configure(text=f"Deferred: Low battery ({power['percent']}%) - Please plug in.", text_color="red")
            self.refresh_ledger()
            return

        if runner_type == "local":
            self.ledger.append_event(task_id, "runner_selected", {"runner": "local_llm"})
            
            if not getattr(self, "active_backend", None):
                self.status_label.configure(text="Error: No local engine active.", text_color="red")
                return
                
            self.status_label.configure(text=f"Drafting locally via {self.active_backend.name}...", text_color="blue")
            self.btn_local.configure(state="disabled")
            
            self.output_box.configure(state="normal")
            self.output_box.delete("0.0", "end")
            self.output_box.insert("0.0", f"Sending to {self.active_backend.name}...\n")
            self.output_box.configure(state="disabled")
            
            import threading
            import time
            def _run_local():
                start_time = time.time()
                try:
                    messages = [
                        {"role": "system", "content": "You are a local coding assistant. Output minimal, correct code."},
                        {"role": "user", "content": f"Task: {prompt}\nTarget Files: {files}"}
                    ]
                    response = self.active_backend.generate(messages)
                    duration = time.time() - start_time
                    
                    self.ledger.append_event(task_id, "local_draft_generated", {"status": "success", "duration_seconds": duration})
                    metrics = SustainabilityEstimator.estimate(duration_seconds=duration)
                    self.ledger.append_event(task_id, "energy_estimated", metrics)
                    
                    self.output_box.configure(state="normal")
                    self.output_box.insert("end", "\n" + response.text)
                    self.output_box.configure(state="disabled")
                    
                    self.status_label.configure(text=f"Local draft generated in {duration:.1f}s! Risk: {danger.risk_level}", text_color="green")
                except Exception as e:
                    self.status_label.configure(text=f"Local draft failed: {e}", text_color="red")
                finally:
                    self.btn_local.configure(state="normal")
                    self.refresh_ledger()
                    
            threading.Thread(target=_run_local, daemon=True).start()
            return # Skip immediate refresh for local runs since it runs async
            
        elif runner_type == "codex":
            self.ledger.append_event(task_id, "runner_selected", {"runner": "codex"})
            
            # Generate the actual file
            os.makedirs("triage_tasks", exist_ok=True)
            filename = f"triage_tasks/codex_task_{task_id[:8]}.md"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"# Task: {prompt}\n\nFiles: {files}")
                
            self.ledger.append_event(task_id, "handoff_generated", {
                "artifact_path": filename
            })
            
            # Launch Codex via subprocess
            import subprocess
            import shutil
            if shutil.which("codex"):
                try:
                    subprocess.Popen(["cmd.exe", "/c", "start", "codex", "--profile", danger.recommended_profile, filename])
                    self.status_label.configure(text=f"Codex launched! Profile: {danger.recommended_profile}", text_color="orange")
                except Exception as e:
                    self.status_label.configure(text=f"Packet saved, but failed to launch codex: {e}", text_color="orange")
            else:
                self.status_label.configure(text=f"Packet saved to {filename}. ('codex' not in PATH)", text_color="orange")
            
        elif runner_type == "antigravity":
            self.ledger.append_event(task_id, "runner_selected", {"runner": "antigravity"})
            
            task_dir = f".agent_tasks/{task_id[:8]}"
            os.makedirs(task_dir, exist_ok=True)
            task_file = f"{task_dir}/TASK.md"
            with open(task_file, "w", encoding="utf-8") as f:
                f.write(f"# Task: {prompt}\n\nFiles: {files}")
                
            self.ledger.append_event(task_id, "handoff_generated", {
                "artifact_path": task_file
            })
            
            # Launch Antigravity
            import subprocess
            import shutil
            if shutil.which("antigravity"):
                try:
                    subprocess.Popen(["cmd.exe", "/c", "start", "antigravity", "run", task_dir])
                    self.status_label.configure(text=f"Antigravity launched! Profile: {danger.recommended_profile}", text_color="red")
                except Exception as e:
                    self.status_label.configure(text=f"Bundle saved, but failed to launch antigravity: {e}", text_color="red")
            else:
                self.status_label.configure(text=f"Bundle saved to {task_dir}. ('antigravity' not in PATH)", text_color="red")
            
        self.refresh_ledger()

def run_app():
    if not UI_AVAILABLE:
        print("Error: customtkinter is not installed. Run `pip install triagecore[ui]`")
        return
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    app = TriageDeskApp()
    app.mainloop()
