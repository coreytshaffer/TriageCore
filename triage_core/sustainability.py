from typing import Dict

class SustainabilityEstimator:
    # Average gCO2e per kWh globally is roughly 475, but let's use 400 as a default mixed grid.
    DEFAULT_GRID_INTENSITY = 400.0  
    
    # 300 watts is a rough heuristic for a mid-range local GPU running inference.
    DEFAULT_WATTS = 300.0  
    
    DEFAULT_WATER_INTENSITY_L_PER_KWH = 1.5
    DEFAULT_DEVICE_EMBODIED_GCO2E = 300000.0
    DEFAULT_DEVICE_LIFETIME_HOURS = 20000.0

    @classmethod
    def estimate(cls, 
                 duration_seconds: float, 
                 watts: float = DEFAULT_WATTS, 
                 grid_intensity: float = DEFAULT_GRID_INTENSITY,
                 water_intensity: float = DEFAULT_WATER_INTENSITY_L_PER_KWH,
                 device_embodied: float = DEFAULT_DEVICE_EMBODIED_GCO2E,
                 device_lifetime_hrs: float = DEFAULT_DEVICE_LIFETIME_HOURS) -> Dict[str, float]:
        """
        Estimates the energy, emissions, water footprint, and embodied carbon for a local task.
        """
        energy_kwh = (watts * duration_seconds) / 3_600_000.0
        emissions_gco2e = energy_kwh * grid_intensity
        water_liters = energy_kwh * water_intensity
        
        task_hours = duration_seconds / 3600.0
        embodied_allocated = device_embodied * (task_hours / device_lifetime_hrs)
        
        return {
            "energy_kwh": energy_kwh,
            "emissions_gco2e": emissions_gco2e,
            "grid_intensity_gco2e_per_kwh": grid_intensity,
            "water_liters_estimate": water_liters,
            "embodied_gco2e_allocated": embodied_allocated,
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

