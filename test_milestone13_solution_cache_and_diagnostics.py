import pytest
from memory.service import MemoryService
from services.diagnostic_service import DiagnosticService


def test_milestone13_solution_cache_save_and_find():
    """
    Milestone 13 Test: MemoryService solution_cache tablosuna hata recetesini
    kaydetmeli ve sonrasinda ayni hata sorgulandiginda receteyi dondurmelidir.
    """
    db = MemoryService()
    test_err = "ModuleNotFoundError: No module named 'scipy'"
    
    db.save_solution(
        error_signature=test_err,
        tool_name="pip_installer",
        solution_fix="pip_installer(package_name='scipy')"
    )

    sol = db.find_solution(test_err)
    assert sol is not None
    assert sol["tool_name"] == "pip_installer"
    assert sol["solution_fix"] == "pip_installer(package_name='scipy')"
    assert sol["success_count"] >= 1


def test_milestone13_diagnostic_service_runs_and_reports():
    """
    Milestone 13 Test: DiagnosticService sistem metriklerini ve en cok
    RAM tüketen process'leri dogru sekilde raporlamalidir.
    """
    diag = DiagnosticService()
    report_data = diag.run_full_diagnostics()

    assert "cpu_usage_percent" in report_data
    assert "ram_percent" in report_data
    assert "top_memory_hogs" in report_data
    assert isinstance(report_data["top_memory_hogs"], list)

    text_report = diag.format_diagnostic_report()
    assert "SİSTEM TEŞHİS RAPORU" in text_report
    assert "RAM (Bellek)" in text_report
