import uuid
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
from .task_ledger import TaskLedger
from .sustainability import SustainabilityEstimator

@dataclass
class ExperimentRun:
    experiment_id: str
    task_id: str
    runner: str
    model: Optional[str] = None
    backend: Optional[str] = None
    prompt_strategy: Optional[str] = None
    context_strategy: Optional[str] = None
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    duration_seconds: float = 0.0
    accepted: bool = False
    tests_passed: bool = False
    human_review_minutes: float = 0.0
    retry_count: int = 0
    hardware_profile: Optional[str] = None
    energy_kwh_estimate: float = 0.0
    emissions_gco2e_estimate: float = 0.0
    water_liters_estimate: float = 0.0
    embodied_gco2e_allocated: float = 0.0

    def calculate_sustainability(self):
        est = SustainabilityEstimator.estimate(self.duration_seconds)
        self.energy_kwh_estimate = est.get("energy_kwh", 0.0)
        self.emissions_gco2e_estimate = est.get("emissions_gco2e", 0.0)
        self.water_liters_estimate = est.get("water_liters_estimate", 0.0)
        self.embodied_gco2e_allocated = est.get("embodied_gco2e_allocated", 0.0)

    def log(self, ledger: Optional[TaskLedger] = None):
        if not ledger:
            ledger = TaskLedger()
            
        if self.duration_seconds > 0 and self.energy_kwh_estimate == 0.0:
            self.calculate_sustainability()

        payload = asdict(self)
        ledger.append_event(self.task_id, "experiment_run_completed", payload)
