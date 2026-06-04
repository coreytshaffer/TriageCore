from typing import Dict

class SustainabilityEstimator:
    # Average gCO2e per kWh globally is roughly 475, but let's use 400 as a default mixed grid.
    DEFAULT_GRID_INTENSITY = 400.0  
    
    # 300 watts is a rough heuristic for a mid-range local GPU running inference.
    DEFAULT_WATTS = 300.0  

    @classmethod
    def estimate(cls, duration_seconds: float, watts: float = DEFAULT_WATTS, grid_intensity: float = DEFAULT_GRID_INTENSITY) -> Dict[str, float]:
        """
        Estimates the energy and emissions for a local task.
        energy_kwh = watts * duration_seconds / 3_600_000
        emissions_gco2e = energy_kwh * grid_intensity_gco2e_per_kwh
        """
        energy_kwh = (watts * duration_seconds) / 3_600_000.0
        emissions_gco2e = energy_kwh * grid_intensity
        
        return {
            "energy_kwh": energy_kwh,
            "emissions_gco2e": emissions_gco2e,
            "grid_intensity_gco2e_per_kwh": grid_intensity,
            "duration_seconds": duration_seconds,
            "watts_assumed": watts
        }

class PowerMonitor:
    @classmethod
    def get_status(cls) -> Dict[str, any]:
        """
        Returns battery and AC power status.
        If psutil is unavailable or system has no battery, returns safe defaults.
        """
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery is None:
                # Desktop or VM with no battery sensor
                return {"has_battery": False, "percent": 100.0, "power_plugged": True}
                
            return {
                "has_battery": True,
                "percent": battery.percent,
                "power_plugged": battery.power_plugged
            }
        except ImportError:
            # Fallback if psutil fails to load
            return {"has_battery": False, "percent": 100.0, "power_plugged": True}

