from triage_core.sustainability import PowerMonitor
from unittest.mock import patch, MagicMock

def test_power_monitor_no_psutil():
    with patch.dict("sys.modules", {"psutil": None}):
        status = PowerMonitor.get_status()
        assert status["has_battery"] is False
        assert status["percent"] == 100.0
        assert status["power_plugged"] is True

def test_power_monitor_with_psutil_no_battery():
    mock_psutil = MagicMock()
    mock_psutil.sensors_battery.return_value = None
    
    with patch.dict("sys.modules", {"psutil": mock_psutil}):
        status = PowerMonitor.get_status()
        assert status["has_battery"] is False
        assert status["percent"] == 100.0
        assert status["power_plugged"] is True

def test_power_monitor_with_psutil_battery():
    mock_psutil = MagicMock()
    mock_battery = MagicMock()
    mock_battery.percent = 45.0
    mock_battery.power_plugged = False
    mock_psutil.sensors_battery.return_value = mock_battery
    
    with patch.dict("sys.modules", {"psutil": mock_psutil}):
        status = PowerMonitor.get_status()
        assert status["has_battery"] is True
        assert status["percent"] == 45.0
        assert status["power_plugged"] is False
