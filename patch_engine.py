import ast
import asyncio
import hashlib
import subprocess
import sys
from pathlib import Path
from core.config import get_settings
from core.logger import setup_logger
from core.types import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("AutonomousPatchTools")
from core.paths import WORKSPACE_ROOT


# Guvenlik katmanini ve testleri yamayan bir yama kendi denetimini devre disi birakabilir.
PROTECTED_PATCH_TARGETS = (
    "core/policy.py", "core/runtime_state.py", "core/config.py", "core/paths.py",
    "tools/registry.py", "tools/patch_engine.py", "tools/terminal.py", "tools/task_approval.py",
    "agent/runner.py", "agent/dispatcher.py", "skills/base.py", "skills/god_mode.py",
    "bridge/jarvis_bridge.py", ".env",
)
PROTECTED_PATCH_DIRS = ("tests/",)


def _is_protected(rel_posix: str) -> bool:
    rel = rel_posix.lower()
    return rel in PROTECTED_PATCH_TARGETS or any(rel.startswith(d) for d in PROTECTED_PATCH_DIRS)


class AutonomousPatchTool(BaseTool):
    name = "autonomous_patch"
    description = "Safely applies code patches to C:\\JARVIS Python files with pre-validation syntax parsing, backup, and pytest verification."
    risk_level = RiskLevel.HIGH

    async def execute(self, target_file: str, new_code: str, **kwargs) -> ToolResult:
        try:
            if not get_settings().ALLOW_SELF_MODIFICATION:
                return ToolResult(success=False, output=None, error="Kendi kodunu degistirme kapali (ALLOW_SELF_MODIFICATION=false).")

            target_path = (WORKSPACE_ROOT / target_file).resolve()

            # Strict Path Traversal Check
            if not target_path.is_relative_to(WORKSPACE_ROOT):
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Security violation: Target file '{target_file}' is outside WORKSPACE_ROOT."
                )

            rel_posix = target_path.relative_to(WORKSPACE_ROOT).as_posix()
            if _is_protected(rel_posix):
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Security violation: '{rel_posix}' korumali bir dosya/dizin; otomatik yama yapilamaz."
                )
            if target_path.suffix.lower() != ".py":
                return ToolResult(success=False, output=None, error="Yalnizca .py dosyalari yamalanabilir.")

            # Pre-validate syntax in memory BEFORE modifying disk
            try:
                ast.parse(new_code)
            except SyntaxError as se:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Pre-patch syntax check failed on line {se.lineno}: {se.msg}"
                )

            # Backup creation
            backup_dir = WORKSPACE_ROOT / "storage" / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            # Yola ozgu yedek adi: farkli klasorlerdeki ayni adli dosyalar (__init__.py) birbirini ezmesin.
            _tag = hashlib.sha1(rel_posix.encode("utf-8")).hexdigest()[:8]
            backup_file = backup_dir / f"{target_path.name}.{_tag}.bak"

            if target_path.exists():
                with open(target_path, "r", encoding="utf-8-sig", errors="replace") as f:
                    old_code = f.read()
                with open(backup_file, "w", encoding="utf-8") as f:
                    f.write(old_code)
            else:
                old_code = None

            # Apply patch to disk
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(new_code)

            # Run Pytest suite with 180s timeout
            # FIX (Milestone 8): "py" launcher yerine sys.executable kullaniliyor.
            # "py" launcher sistemde kurulu FARKLI bir Python'a (venv disi, 
            # bagimliliklari eksik) gidebilir, bu da gecerli bir yamanin bile
            # ModuleNotFoundError ile yanlislikla rollback edilmesine yol acabilirdi.
            # sys.executable, su an calisan (tum bagimliliklari yuklu) Python'u garanti eder.
            try:
                test_proc = await asyncio.to_thread(
                    subprocess.run,
                    [sys.executable, "-m", "pytest", "-v"],
                    cwd=str(WORKSPACE_ROOT),
                    capture_output=True,
                    text=True,
                    timeout=180
                )
            except Exception as run_err:
                # Zaman asimi / calistirma hatasi: dogrulanamayan yama diskte BIRAKILMAZ.
                logger.warning(f"Test calistirilamadi ({run_err}); yama geri aliniyor: '{target_file}'")
                if old_code is not None:
                    with open(target_path, "w", encoding="utf-8") as f:
                        f.write(old_code)
                elif target_path.exists():
                    target_path.unlink()
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Yama dogrulanamadi ({type(run_err).__name__}); geri alindi."
                )

            if test_proc.returncode == 0:
                return ToolResult(
                    success=True,
                    output=f"Patch applied and verified successfully on '{target_file}'. All tests passed.",
                    metadata={"backup_file": str(backup_file)}
                )
            else:
                # Rollback on test failure
                logger.warning(f"Tests failed after patch on '{target_file}'. Rolling back...")
                if old_code is not None:
                    with open(target_path, "w", encoding="utf-8") as f:
                        f.write(old_code)
                elif target_path.exists():
                    target_path.unlink()

                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Patch failed test suite verification. Rollback executed. Pytest output:\n{test_proc.stdout[-500:]}"
                )

        except Exception as e:
            logger.error(f"Autonomous patch error: {e}")
            return ToolResult(success=False, output=None, error=str(e))
