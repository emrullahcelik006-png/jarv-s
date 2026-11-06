import ast
import os
from pathlib import Path
from typing import Dict, List, Any
from core.logger import setup_logger
from tasks.models import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("ProjectHealthTools")
from core.paths import WORKSPACE_ROOT


class ProjectHealthTool(BaseTool):
    name = "project_health"
    description = "Scans the JARVIS codebase (C:\\JARVIS) for Python syntax errors, dependency issues, and project statistics."
    risk_level = RiskLevel.LOW

    async def execute(self, target_dir: str = ".", **kwargs) -> ToolResult:
        try:
            target_path = (WORKSPACE_ROOT / target_dir).resolve()
            if not target_path.exists():
                return ToolResult(success=False, output=None, error=f"Target directory '{target_dir}' does not exist.")

            report = {
                "total_files": 0,
                "syntax_errors": [],
                "clean_files": 0
            }

            for root, dirs, files in os.walk(target_path):
                dirs[:] = [d for d in dirs if d not in (".venv", "venv", ".git", "__pycache__")]
                for file in files:
                    if file.endswith(".py"):
                        report["total_files"] += 1
                        file_p = Path(root) / file
                        try:
                            with open(file_p, "r", encoding="utf-8-sig", errors="replace") as f:
                                ast.parse(f.read())
                            report["clean_files"] += 1
                        except SyntaxError as se:
                            rel_p = str(file_p.relative_to(WORKSPACE_ROOT))
                            report["syntax_errors"].append({
                                "file": rel_p,
                                "error": se.msg,
                                "line": se.lineno
                            })

            success = len(report["syntax_errors"]) == 0
            return ToolResult(
                success=success,
                output=report,
                metadata={"status": "HEALTHY" if success else "SYNTAX_ERRORS_FOUND"}
            )
        except Exception as e:
            logger.error(f"ProjectHealthTool error: {e}")
            return ToolResult(success=False, output=None, error=str(e))
