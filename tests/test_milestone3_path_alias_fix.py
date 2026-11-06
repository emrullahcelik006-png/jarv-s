import pytest
from pathlib import Path
from core.policy import SecurityPolicyEngine
from tasks.models import RiskLevel

from core.paths import WORKSPACE_ROOT


def test_path_alias_filename_is_caught_by_security_policy():
    """
    Milestone 3 guvenlik regresyon testi:
    'filename' alias'i ile workspace disina cikmaya calisan bir istek,
    guvenlik katmani tarafindan YAKALANMALI (onceden bu alias hic
    kontrol edilmiyordu, sadece file_path/path/dir_path kontrol ediliyordu).
    """
    outside_path = str(Path("C:/Windows/System32/evil.txt"))

    # 'filename' alias'i ile HIGH riskli bir arac (file_write) cagriliyor
    risk, requires_approval = SecurityPolicyEngine.evaluate_risk(
        "file_write", {"filename": outside_path}
    )
    assert risk == RiskLevel.HIGH
    assert requires_approval is True


def test_path_alias_target_file_is_caught_by_security_policy():
    """'target_file' alias'i da ayni sekilde yakalanmali."""
    outside_path = str(Path("C:/Windows/System32/evil.txt"))
    risk, requires_approval = SecurityPolicyEngine.evaluate_risk(
        "file_write", {"target_file": outside_path}
    )
    assert risk == RiskLevel.HIGH
    assert requires_approval is True


def test_path_alias_directory_alias_is_caught_for_read_tools():
    """
    'directory' alias'i ile izin verilmeyen bir dizine erisim denemesi
    dusuk riskli araclarda bile yakalanmali (ALLOWED_READ_LAUNCH_ROOTS disinda).
    """
    # Var olmayan/izin verilmeyen bir surucu/dizin varsayimi
    risk, requires_approval = SecurityPolicyEngine.evaluate_risk(
        "directory_scan", {"directory": "Z:/forbidden_area"}
    )
    # Z: suruculer genelde yok, path.resolve() calisir ama ALLOWED_READ_LAUNCH_ROOTS
    # icinde olmadigi icin HIGH donmeli
    assert risk == RiskLevel.HIGH
    assert requires_approval is True


def test_path_within_workspace_still_works_with_alias():
    """Workspace icindeki gecerli bir yol, alias ile de dogru sekilde gecmeli."""
    valid_path = str(WORKSPACE_ROOT / "storage" / "test.txt")
    risk, requires_approval = SecurityPolicyEngine.evaluate_risk(
        "file_write", {"filename": valid_path}
    )
    assert risk == RiskLevel.HIGH  # file_write zaten HIGH
    assert requires_approval is True  # ama onay gerektirmesi path disaridan degil, risk seviyesinden
