"""
TestSphere AI — Device Risk Analyzer
Evaluates mobile devices and OS combinations to detect regression stability.
"""
from typing import Dict, Any, List
from backend.config import CONFIG
from backend.engine.data_access import get_device_matrix

HIGH_RISK_DEVICES = set(CONFIG["devices"]["high_risk"])


def get_device_risk_score(device: str, os_version: str) -> int:
    """
    Computes a risk profile score (20 to 100) based on database matrix rates.
    """
    matrix = get_device_matrix()
    for d in matrix:
        # Match device ID or name
        if d["device_name"].lower() == device.lower() and d["os_version"].lower() == os_version.lower():
            risk = d["risk_level"].upper()
            if risk == "CRITICAL":
                return 100
            elif risk == "HIGH":
                return 80
            elif risk == "MEDIUM":
                return 50
            return 20

    # Fallback to config constants
    if device in HIGH_RISK_DEVICES:
        return 80
    return 20


def is_high_risk_device(device: str, os_version: str) -> bool:
    """Returns True if the device configuration has high risk classification."""
    score = get_device_risk_score(device, os_version)
    return score >= 80


def get_all_device_risks() -> Dict[str, int]:
    """Generates a dynamic lookup mapping {device_name: risk_score}."""
    matrix = get_device_matrix()
    res = {}
    for d in matrix:
        name = d["device_name"]
        risk = d["risk_level"].upper()
        score = 100 if risk == "CRITICAL" else (80 if risk == "HIGH" else (50 if risk == "MEDIUM" else 20))
        res[name] = max(res.get(name, 0), score)
    return res
