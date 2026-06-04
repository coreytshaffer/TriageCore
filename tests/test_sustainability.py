from triage_core.sustainability import SustainabilityEstimator

def test_sustainability_estimator():
    # 300 watts for 10 seconds
    res = SustainabilityEstimator.estimate(duration_seconds=10.0, watts=300.0, grid_intensity=400.0)
    
    # kWh = 300 * 10 / 3_600_000 = 3000 / 3_600_000 = 0.0008333...
    assert res["energy_kwh"] > 0.00083
    assert res["energy_kwh"] < 0.00084
    
    # gCO2e = kWh * 400 = 0.333...
    assert res["emissions_gco2e"] > 0.33
    assert res["emissions_gco2e"] < 0.34
