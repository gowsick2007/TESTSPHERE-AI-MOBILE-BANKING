"""
TestSphere AI — Change Analyzer
Parses list of changed files and determines modules and base risk level.
"""
from typing import List, Dict, Any

# Critical modules which default to higher risk
HIGH_RISK_MODULES = {"Authentication", "Authorization", "OTP", "Payment", "UPI", "Transaction", "FraudDetection", "AccountSecurity"}


def analyze_change(
    changed_files: List[str],
    change_type: str = "MODIFIED",
    module: str | None = None,
    is_security_sensitive: bool = False,
    risk_level: str = "MEDIUM",
) -> Dict[str, Any]:
    """
    Classify a code change request and locate impacted modules.
    """
    affected_modules = set()
    if module:
        affected_modules.add(module)

    # Classify based on file paths
    # File format examples: "auth/login.py", "payment/payment_controller.py"
    for f in changed_files:
        parts = f.split("/")
        if len(parts) > 1:
            # Map directory structure to module name
            mod_candidate = parts[0].title()
            affected_modules.add(mod_candidate)
        else:
            # Fallback for simple file names
            if "auth" in f.lower() or "login" in f.lower():
                affected_modules.add("Authentication")
            elif "pay" in f.lower() or "upi" in f.lower():
                affected_modules.add("Payment")

    # If security modules are touched, force security sensitive flag
    security_keywords = {"security", "auth", "login", "crypt", "cipher", "otp", "token"}
    sec_flag = is_security_sensitive
    for f in changed_files:
        if any(kw in f.lower() for kw in security_keywords):
            sec_flag = True

    # Identify if a high risk module is touched
    has_high_risk_module = any(m in HIGH_RISK_MODULES for m in affected_modules)
    final_risk = risk_level
    if has_high_risk_module or sec_flag:
        if risk_level in ["LOW", "MEDIUM"]:
            final_risk = "HIGH"

    return {
        "changed_files": changed_files,
        "change_type": change_type,
        "affected_modules": sorted(list(affected_modules)),
        "is_security_sensitive": sec_flag,
        "risk_level": final_risk,
    }
