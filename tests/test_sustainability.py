from triage_core.sustainability import (
    SustainabilityEstimator,
    integrate_energy_kwh,
    get_cpu_power_heuristic,
    PowerSampler,
    init_nvml
)
import time

def test_sustainability_estimator():
    # 300 watts for 10 seconds
    res = SustainabilityEstimator.estimate(duration_seconds=10.0, watts=300.0, grid_intensity=400.0)
    
    # kWh = 300 * 10 / 3_600_000 = 3000 / 3_600_000 = 0.0008333...
    assert res["energy_kwh"] > 0.00083
    assert res["energy_kwh"] < 0.00084
    
    # gCO2e = kWh * 400 = 0.333...
    assert res["emissions_gco2e"] > 0.33
    assert res["emissions_gco2e"] < 0.34

def test_sustainability_estimator_loads_config():
    res = SustainabilityEstimator.estimate(duration_seconds=10.0)
    assert "energy_kwh" in res
    assert "emissions_gco2e" in res
    assert res["watts_assumed"] == 300.0

def test_integrate_energy_kwh_heuristic_fallback():
    kwh, watts, source = integrate_energy_kwh([], 10.0, 300.0)
    assert source == "heuristic"
    assert watts == 300.0
    assert abs(kwh - (300.0 * 10.0) / 3_600_000.0) < 1e-9

def test_integrate_energy_kwh_measured():
    t0 = time.time()
    samples = [(t0, 100.0), (t0 + 5.0, 200.0)]
    kwh, watts, source = integrate_energy_kwh(samples, 5.0, 300.0)
    assert watts == 150.0
    assert abs(kwh - 750.0 / 3_600_000.0) < 1e-9

def test_get_cpu_power_heuristic():
    power = get_cpu_power_heuristic()
    assert power >= 10.0
    assert power <= 65.0

def test_power_sampler_runs():
    sampler = PowerSampler(interval=0.05)
    sampler.start()
    time.sleep(0.15)
    samples = sampler.stop()
    assert len(samples) > 0
    for t, p in samples:
        assert t > 0
        assert p >= 0


def test_get_geoip_location_success():
    from unittest.mock import MagicMock, patch
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "latitude": 37.7749,
        "longitude": -122.4194,
        "country_code": "US"
    }
    with patch("requests.get", return_value=mock_resp):
        from triage_core.sustainability import _get_geoip_location
        lat, lon, cc = _get_geoip_location()
        assert lat == 37.7749
        assert lon == -122.4194
        assert cc == "US"


def test_get_geoip_location_failure():
    from unittest.mock import patch
    with patch("requests.get", side_effect=Exception("network error")):
        from triage_core.sustainability import _get_geoip_location
        lat, lon, cc = _get_geoip_location()
        assert lat is None
        assert lon is None
        assert cc is None


def test_fetch_live_grid_intensity_success():
    from unittest.mock import MagicMock, patch
    from triage_core.sustainability import fetch_live_grid_intensity, _grid_intensity_cache

    _grid_intensity_cache["value"] = None
    _grid_intensity_cache["timestamp"] = 0.0

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"carbonIntensity": 250.0}

    with patch.dict("os.environ", {"CO2SIGNAL_API_KEY": "dummy_key"}):
        with patch("triage_core.sustainability._get_geoip_location", return_value=(37.7749, -122.4194, "US")):
            with patch("requests.get", return_value=mock_resp) as mock_get:
                val, src = fetch_live_grid_intensity()
                assert val == 250.0
                assert "electricitymaps_geoip_coordinates" in src
                mock_get.assert_called_once_with(
                    "https://api.co2signal.com/v1/latest",
                    headers={"auth-token": "dummy_key"},
                    params={"lat": "37.7749", "lon": "-122.4194"},
                    timeout=5.0
                )



def test_fetch_live_grid_intensity_cache():
    from unittest.mock import patch
    from triage_core.sustainability import fetch_live_grid_intensity, _grid_intensity_cache

    _grid_intensity_cache["value"] = 180.0
    _grid_intensity_cache["timestamp"] = time.time()
    _grid_intensity_cache["source"] = "electricitymaps_cached"

    with patch("requests.get") as mock_get:
        val, src = fetch_live_grid_intensity()
        assert val == 180.0
        assert src == "electricitymaps_cached"
        assert not mock_get.called


