import ast
import asyncio
import os
import subprocess
import sys
from pathlib import Path
from core.logger import setup_logger
from tasks.models import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("CodeRunnerTools")
USER_HOME = Path(os.path.expanduser("~")).resolve()


def _resolve_global_path(path_str: str) -> Path:
    clean = path_str.strip().strip("\"'").replace("\\", "/")
    lower = clean.lower()
    if lower in ("desktop", "masaüstü", "masaustu"):
        return USER_HOME / "Desktop"
    if lower.startswith("desktop/") or lower.startswith("masaüstü/") or lower.startswith("masaustu/"):
        sub_path = clean.split("/", 1)[1]
        return USER_HOME / "Desktop" / sub_path
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    return p.resolve()


class PythonSyntaxCheckTool(BaseTool):
    name = "syntax_check"
    description = "Python kodunun veya dosyasinin soz dizimi (syntax) hatasini kontrol eder."
    risk_level = RiskLevel.LOW

    async def execute(self, file_path: str = None, code_snippet: str = None, **kwargs) -> ToolResult:
        try:
            path_val = file_path or kwargs.get("path") or kwargs.get("file")
            if path_val:
                target = _resolve_global_path(str(path_val))
                with open(target, "r", encoding="utf-8-sig", errors="replace") as f:
                    source = f.read()
            elif code_snippet:
                source = code_snippet
            else:
                return ToolResult(success=False, output=None, error="file_path veya code_snippet gerekli")

            ast.parse(source)
            return ToolResult(success=True, output="Syntax OK: Kod basariyla derlendi.")
        except SyntaxError as e:
            return ToolResult(success=False, output=None, error=f"Syntax Hatasi: {e.msg} (Satir: {e.lineno})")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class PythonExecuteTool(BaseTool):
    name = "python_execute"
    description = "Belirtilen .py Python betik dosyasini dogrudan calistirir ve ciktisini alir."
    risk_level = RiskLevel.MEDIUM

    async def execute(self, file_path: str = None, **kwargs) -> ToolResult:
        try:
            path_val = file_path or kwargs.get("path") or kwargs.get("file") or kwargs.get("script") or kwargs.get("target")
            if not path_val:
                return ToolResult(success=False, output=None, error="Calistirilacak Python dosyasi (file_path) belirtilmedi.")

            target = _resolve_global_path(str(path_val))
            if not target.exists() or not target.is_file():
                return ToolResult(success=False, output=None, error=f"Calistirilacak Python dosyasi bulunamadi: {target}")

            logger.info(f"Python Betigi Calistiriliyor: {target}")
            cmd = [sys.executable, str(target)]

            # THREAD ISOLATION TO PREVENT BLOCKING FASTAPI EVENT LOOP
            res = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace"
            )

            out_text = res.stdout.strip()
            err_text = res.stderr.strip()

            if res.returncode == 0:
                return ToolResult(
                    success=True,
                    output=f"🐍 **[PYTHON BETİĞİ ÇALIŞTIRILDI]** (`{target.name}`)\n\n```text\n{out_text or 'Betik basariyla calisti (Çıktı yok).'}\n```",
                    metadata={"return_code": 0, "file": str(target)}
                )
            else:
                return ToolResult(
                    success=False,
                    output=out_text,
                    error=f"Python Çalıştırma Hatası [{res.returncode}]:\n{err_text or out_text or 'Bilinmeyen Python Hatasi'}",
                    metadata={"return_code": res.returncode}
                )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output=None, error="Python betigi zaman asimina ugradi (Timeout 30s)")
        except Exception as e:
            logger.error(f"PythonExecute error: {e}")
            return ToolResult(success=False, output=None, error=str(e))


class TestRunnerTool(BaseTool):
    name = "test_runner"
    description = "Pytest birim testlerini calistirir."
    risk_level = RiskLevel.MEDIUM

    async def execute(self, test_target: str = "tests", **kwargs) -> ToolResult:
        try:
            target_str = str(test_target or "tests").strip()
            # Hedef bir pytest SECENEGI olamaz (-p plugin, --basetemp ...) ve tests/ disina cikamaz.
            if target_str.startswith("-") or ".." in Path(target_str).parts:
                return ToolResult(success=False, output=None, error="Gecersiz test hedefi.")
            cmd = [sys.executable, "-m", "pytest", target_str, "-q"]

            # THREAD ISOLATION TO PREVENT BLOCKING FASTAPI EVENT LOOP
            res = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
                errors="replace"
            )

            success = res.returncode == 0
            err_msg = res.stderr.strip() or res.stdout.strip() or f"Pytest basarisiz [Return code: {res.returncode}]"
            return ToolResult(
                success=success,
                output=res.stdout,
                error=err_msg if not success else None,
                metadata={"return_code": res.returncode},
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output=None, error="Test zaman asimina ugradi (Timeout 60s)")
        except Exception as e:
            logger.error(f"TestRunner error: {e}")
            return ToolResult(success=False, output=None, error=str(e))
