import ast
from pathlib import Path
from core.logger import setup_logger
from core.types import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("DevModeTools")
from core.paths import WORKSPACE_ROOT


class SelfCodeAnalysisTool(BaseTool):
    name = "self_code_analysis"
    description = r"JARVIS'in kendi kod tabanini (C:\JARVIS) tarayarak Python dosyalarini, siniflari ve syntax hatalarini analiz eder."
    risk_level = RiskLevel.LOW

    async def execute(self, target_dir: str = ".", **kwargs) -> ToolResult:
        try:
            target_path = (WORKSPACE_ROOT / target_dir).resolve()
            py_files = list(target_path.glob("**/*.py"))

            report = {
                "total_python_files": 0,
                "syntax_errors": [],
                "modules_found": [],
            }

            for file in py_files:
                if ".venv" in str(file) or "venv" in str(file):
                    continue

                report["total_python_files"] += 1
                rel_path = file.relative_to(WORKSPACE_ROOT)
                report["modules_found"].append(str(rel_path))

                try:
                    with open(file, "r", encoding="utf-8-sig", errors="replace") as f:
                        source = f.read()
                    ast.parse(source, filename=str(rel_path))
                except SyntaxError as se:
                    report["syntax_errors"].append({
                        "file": str(rel_path),
                        "error": se.msg,
                        "line": se.lineno
                    })

            success = len(report["syntax_errors"]) == 0
            return ToolResult(
                success=success,
                output=report,
                metadata={"status": "CLEAN" if success else "ERRORS_FOUND"}
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
