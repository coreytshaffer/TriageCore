import os
import ctypes
import threading
import time
from typing import Dict, Any, List, Tuple
import requests
from .config import default_config

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_nvml_lib = None
_nvml_initialized = False
_nvml_device = None


def init_nvml() -> bool:
    global _nvml_lib, _nvml_initialized, _nvml_device
    if _nvml_initialized:
        return True
    try:
        paths = [
            "nvml.dll",
            r"C:\Program Files\NVIDIA Corporation\NVSMI\nvml.dll",
            r"C:\Windows\System32\nvml.dll",
            "libnvidia-ml.so",
            "libnvidia-ml.so.1",
        ]
        for p in paths:
            try:
                _nvml_lib = ctypes.CDLL(p)
                break
            except Exception:
                continue
        if _nvml_lib:
            ret = _nvml_lib.nvmlInit()
            if ret == 0:
                _nvml_device = ctypes.c_void_p()
                ret2 = _nvml_lib.nvmlDeviceGetHandleByIndex(
                    0, ctypes.byref(_nvml_device)
                )
                if ret2 == 0:
                    _nvml_initialized = True
                    return True
    except Exception:
        pass
    return False


def get_gpu_power() -> float:
    if not _nvml_initialized:
        if not init_nvml():
            return 0.0
    try:
        power_mw = ctypes.c_uint()
        ret = _nvml_lib.nvmlDeviceGetPowerUsage(_nvml_device, ctypes.byref(power_mw))
        if ret == 0:
            return power_mw.value / 1000.0
    except Exception:
        pass
    return 0.0


def shutdown_nvml():
    global _nvml_initialized
    if _nvml_initialized and _nvml_lib:
        try:
            _nvml_lib.nvmlShutdown()
        except Exception:
            pass
        _nvml_initialized = False


# Register NVML cleanup on exit
import atexit

atexit.register(shutdown_nvml)

_rapl_energy_path = "/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj"
_rapl_last_val = None
_rapl_last_time = None


def rapl_is_available() -> bool:
    return os.path.exists(_rapl_energy_path)


def get_cpu_power_rapl() -> float:
    global _rapl_last_val, _rapl_last_time
    if not os.path.exists(_rapl_energy_path):
        return 0.0
    try:
        with open(_rapl_energy_path, "r") as f:
            val = int(f.read().strip())
        now = time.time()
        power = 0.0
        if _rapl_last_val is not None and _rapl_last_time is not None:
            dt = now - _rapl_last_time
            if dt > 0:
                d_energy = val - _rapl_last_val
                power = (d_energy / 1e6) / dt
        _rapl_last_val = val
        _rapl_last_time = now
        return power
    except Exception:
        return 0.0


def get_cpu_power_heuristic() -> float:
    try:
        import psutil

        cpu_util = psutil.cpu_percent(interval=None) / 100.0
        cpu_tdp = default_config.get_global("sustainability", "cpu_tdp", 65.0)
        cpu_idle = default_config.get_global("sustainability", "cpu_idle", 10.0)
        return cpu_idle + (cpu_tdp - cpu_idle) * cpu_util
    except Exception:
        return 15.0


_grid_intensity_cache = {
    "value": None,
    "timestamp": 0.0,
    "source": "static_config",
}


def _get_geoip_location() -> Tuple[float, float, str]:
    """
    Attempts to geolocate the host using a free public IP geolocation API.
    Returns: (latitude, longitude, country_code) or (None, None, None) on error.
    """
    try:
        resp = requests.get("https://ipapi.co/json/", timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            lat = data.get("latitude")
            lon = data.get("longitude")
            cc = data.get("country_code")
            if lat is not None and lon is not None:
                return float(lat), float(lon), cc
    except Exception:
        pass
    return None, None, None


def fetch_live_grid_intensity() -> Tuple[float, str]:
    """
    Fetches real-time carbon intensity of the local grid using CO2 Signal / ElectricityMaps API.
    Utilizes local IP-based geolocation if coordinates are not configured in TOML.
    Caches the result in-memory for 1 hour.
    Returns: (intensity_gco2e_per_kwh, source_description)
    """
    global _grid_intensity_cache

    api_choice = default_config.get_global("sustainability", "grid_intensity_api", "co2signal")
    if api_choice == "none":
        return None, "static_config"

    now = time.time()
    if _grid_intensity_cache["value"] is not None and (now - _grid_intensity_cache["timestamp"]) < 3600:
        return _grid_intensity_cache["value"], _grid_intensity_cache["source"]

    api_key = os.environ.get("CO2SIGNAL_API_KEY") or os.environ.get("ELECTRICITYMAPS_API_KEY")
    if not api_key:
        return None, "static_config"

    try:
        lat = default_config.get_global("sustainability", "grid_intensity_lat")
        lon = default_config.get_global("sustainability", "grid_intensity_lon")

        def to_float_or_none(v):
            if v is None or str(v).strip() == "":
                return None
            try:
                return float(v)
            except ValueError:
                return None

        lat = to_float_or_none(lat)
        lon = to_float_or_none(lon)

        cc = None
        source_type = "configured_coordinates"

        if lat is None or lon is None:
            lat, lon, cc = _get_geoip_location()
            source_type = "geoip_coordinates"

        if lat is None or lon is None:
            if cc:
                params = {"countryCode": cc}
                source_type = f"geoip_country_{cc}"
            else:
                return None, "static_config"
        else:
            params = {"lat": str(lat), "lon": str(lon)}

        headers = {"auth-token": api_key}
        url = "https://api.co2signal.com/v1/latest"

        resp = requests.get(url, headers=headers, params=params, timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            intensity = data.get("carbonIntensity")
            if intensity is not None:
                intensity_val = float(intensity)
                _grid_intensity_cache = {
                    "value": intensity_val,
                    "timestamp": now,
                    "source": f"electricitymaps_{source_type}",
                }
                return intensity_val, _grid_intensity_cache["source"]
    except Exception:
        pass

    return None, "static_config"


class SustainabilityEstimator:
    DEFAULT_GRID_INTENSITY = 400.0
    DEFAULT_WATTS = 300.0
    DEFAULT_WATER_INTENSITY_L_PER_KWH = 1.5
    DEFAULT_DEVICE_EMBODIED_GCO2E = 300000.0
    DEFAULT_DEVICE_LIFETIME_HOURS = 20000.0

    @classmethod
    def estimate(
        cls,
        duration_seconds: float,
        watts: float = None,
        grid_intensity: float = None,
        water_intensity: float = None,
        device_embodied: float = None,
        device_lifetime_hrs: float = None,
    ) -> Dict[str, Any]:
        """
        Estimates the energy, emissions, water footprint, and embodied carbon for a local task.
        """
        # Load from config, falling back to class defaults
        if watts is None:
            watts = default_config.get_global(
                "sustainability", "default_watts", cls.DEFAULT_WATTS
            )
        grid_intensity_source = "static_config"
        if grid_intensity is None:
            live_val, live_src = fetch_live_grid_intensity()
            if live_val is not None:
                grid_intensity = live_val
                grid_intensity_source = live_src
            else:
                grid_intensity = default_config.get_global(
                    "sustainability",
                    "grid_intensity_gco2e_per_kwh",
                    cls.DEFAULT_GRID_INTENSITY,
                )
                grid_intensity_source = "static_config"
        else:
            grid_intensity_source = "caller_override"

        if water_intensity is None:
            water_intensity = default_config.get_global(
                "sustainability",
                "water_intensity_l_per_kwh",
                cls.DEFAULT_WATER_INTENSITY_L_PER_KWH,
            )
        if device_embodied is None:
            device_embodied = default_config.get_global(
                "sustainability",
                "device_embodied_gco2e",
                cls.DEFAULT_DEVICE_EMBODIED_GCO2E,
            )
        if device_lifetime_hrs is None:
            device_lifetime_hrs = default_config.get_global(
                "sustainability",
                "device_lifetime_hours",
                cls.DEFAULT_DEVICE_LIFETIME_HOURS,
            )

        energy_kwh = (watts * duration_seconds) / 3_600_000.0
        emissions_gco2e = energy_kwh * grid_intensity
        water_liters = energy_kwh * water_intensity

        task_hours = duration_seconds / 3600.0
        embodied_allocated = device_embodied * (task_hours / device_lifetime_hrs)

        return {
            "energy_kwh": energy_kwh,
            "emissions_gco2e": emissions_gco2e,
            "grid_intensity_gco2e_per_kwh": grid_intensity,
            "grid_intensity_source": grid_intensity_source,
            "water_liters_estimate": water_liters,
            "embodied_gco2e_allocated": embodied_allocated,
            "duration_seconds": duration_seconds,
            "watts_assumed": watts,
        }


class PowerMonitor:
    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """
        Returns battery and AC power status.
        If psutil is unavailable or system has no battery, returns safe defaults.
        """
        try:
            import psutil

            battery = psutil.sensors_battery()
            if battery is None:
                return {"has_battery": False, "percent": 100.0, "power_plugged": True}

            return {
                "has_battery": True,
                "percent": battery.percent,
                "power_plugged": battery.power_plugged,
            }
        except ImportError:
            return {"has_battery": False, "percent": 100.0, "power_plugged": True}


class PowerSampler:
    def __init__(self, interval: float = 0.2):
        self.interval = interval
        self.samples: List[Tuple[float, float]] = []
        self._stop_event = threading.Event()
        self._thread = None
        self.measurement_source = "heuristic"

    def start(self):
        self.samples = []
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> List[Tuple[float, float]]:
        if self._thread:
            self._stop_event.set()
            self._thread.join(timeout=1.0)
        return self.samples

    def _run(self):
        has_measured_gpu = init_nvml()
        has_measured_cpu = rapl_is_available()

        if has_measured_gpu or has_measured_cpu:
            self.measurement_source = "measured"
        else:
            self.measurement_source = "heuristic"

        while not self._stop_event.is_set():
            t_start = time.time()
            try:
                gpu_w = 0.0
                if has_measured_gpu:
                    gpu_w = get_gpu_power()

                cpu_w = 0.0
                if has_measured_cpu:
                    cpu_w = get_cpu_power_rapl()
                else:
                    cpu_w = get_cpu_power_heuristic()

                total_w = gpu_w + cpu_w
                self.samples.append((t_start, total_w))
            except Exception:
                pass

            elapsed = time.time() - t_start
            sleep_time = self.interval - elapsed
            if sleep_time > 0:
                self._stop_event.wait(sleep_time)


def integrate_energy_kwh(
    samples: List[Tuple[float, float]], duration_seconds: float, default_watts: float
) -> Tuple[float, float, str]:
    """
    Integrates the samples list to compute energy_kwh, avg_watts, and source.
    Returns: (energy_kwh, avg_watts, source)
    """
    if not samples or len(samples) < 2:
        energy_kwh = (default_watts * duration_seconds) / 3_600_000.0
        return energy_kwh, default_watts, "heuristic"

    total_joules = 0.0
    for i in range(1, len(samples)):
        t1, w1 = samples[i - 1]
        t2, w2 = samples[i]
        dt = t2 - t1
        w_avg = (w1 + w2) / 2.0
        total_joules += w_avg * dt

    time_span = samples[-1][0] - samples[0][0]
    if time_span > 0:
        avg_watts = total_joules / time_span
    else:
        avg_watts = default_watts

    energy_kwh = total_joules / 3_600_000.0

    is_measured = _nvml_initialized or rapl_is_available()
    source = "measured" if is_measured else "heuristic"

    return energy_kwh, avg_watts, source
