"""
TestSphere AI — Device Risk Analyzer
Determines device-level risk contribution for test selection scoring.
"""
import logging
from Engine.data_access import get_device_matrix, get_device_risk

logger = logging.getLogger(__name__)

HIGH_RISK_DEVICES: set[str] = {"Pixel 8", "Samsung S24", "iPhone 15"}
HIGH_RISK_OS_VERSIONS: set[str] = {"Android 15", "iOS 18"}


def get_device_risk_score(device_name: str) -> int:
    """
    Return a numeric risk contribution for a device.
      HIGH risk → +10
      MEDIUM    → +5
      LOW       → 0
      UNKNOWN   → +5 (conservative)
    """
    risk_level = get_device_risk(device_name)
    return {"HIGH": 10, "MEDIUM": 5, "LOW": 0, "UNKNOWN": 5}.get(risk_level, 5)


def is_high_risk_device(device_name: str, os_version: str = "") -> bool:
    """Return True if device or OS is classified as high-risk."""
    if device_name in HIGH_RISK_DEVICES:
        return True
    if os_version in HIGH_RISK_OS_VERSIONS:
        return True
    risk = get_device_risk(device_name)
    return risk == "HIGH"


def get_affected_devices(affected_modules: list[str], all_tests: list[dict]) -> dict:
    """
    Determine which devices are affected by a change based on the affected modules.

    Returns device impact summary keyed by device name.
    """
    affected_set = set(affected_modules)
    device_counts: dict[str, dict] = {}

    for t in all_tests:
        if t.get("module") in affected_set:
            dev = t.get("device", "Unknown")
            if dev not in device_counts:
                device_counts[dev] = {
                    "device": dev,
                    "os_version": t.get("os_version", ""),
                    "test_count": 0,
                    "risk_level": get_device_risk(dev),
                }
            device_counts[dev]["test_count"] += 1

    return device_counts


def compute_device_heatmap(all_tests: list[dict], failures: list[dict]) -> list[dict]:
    """
    Build device × module failure heatmap data.
    Returns a list of {device, module, failure_count} rows.
    """
    from collections import defaultdict
    heat: dict[tuple, int] = defaultdict(int)
    for f in failures:
        heat[(f.get("device", "?"), f.get("module", "?"))] += 1

    result = [{"device": d, "module": m, "failure_count": c}
              for (d, m), c in sorted(heat.items(), key=lambda x: -x[1])]
    return result
