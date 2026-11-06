import pytest
from core.policy import SecurityPolicyEngine
from tasks.models import RiskLevel


def test_security_policy_evaluation():
    # Dusuk riskli arac
    risk1, req_app1 = SecurityPolicyEngine.evaluate_risk("system_info", {})
    assert risk1 == RiskLevel.LOW
    assert req_app1 is False

    # Yüksek riskli arac (Terminal komutu çalıştırma)
    risk2, req_app2 = SecurityPolicyEngine.evaluate_risk("terminal_execute", {"command": "echo test"})
    assert risk2 == RiskLevel.HIGH
    assert req_app2 is True
