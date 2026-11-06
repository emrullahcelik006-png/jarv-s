import asyncio
import re
import subprocess
import sys
from pathlib import Path
from core.logger import setup_logger
from core.types import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("TerminalTools")
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

BLOCKED_COMMANDS = ["format ", "rmdir /s /q c:\\", "del /f /s /q c:\\", "shutdown", "reboot"]

BLOCKED_PATTERNS = [
    r"\bremove-item\b", r"\brm\s+(-\w+\s+)*-\w*r", r"\brmdir\b", r"\brd\s+/s", r"\bdel\s+(/\w\s+)*[a-z]:\\",
    r"\bdiskpart\b", r"\bformat-volume\b", r"\bclear-disk\b", r"\breg\s+delete\b", r"\bbcdedit\b",
    r"\bstop-computer\b", r"\brestart-computer\b", r"\bnet\s+user\b", r"\bcipher\s+/w\b",
    r"invoke-expression|\biex\b", r"downloadstring|invoke-webrequest.*\|\s*iex",
]


class TerminalExecuteTool(BaseTool):
    name = "terminal_execute"
    description = "PowerShell / CMD uzerinde guvenli terminal komutlari (python script.py, pip install, dir, echo vb.) calistirir."
    risk_level = RiskLevel.HIGH

    async def execute(self, command: str = None, **kwargs) -> ToolResult:
        try:
            cmd_val = (
                command
                or kwargs.get("action")
                or kwargs.get("cmd")
                or kwargs.get("script")
                or kwargs.get("instruction")
                or kwargs.get("target")
                or "echo No Command"
            )
            cmd_str = str(cmd_val).strip()
            # Yalnizca komutun TAMAMINI saran eslesen tirnak cifti kaldirilir
            # (python -c "print(1)" gibi icteki tirnaklari bozmamak icin).
            if len(cmd_str) >= 2 and cmd_str[0] == cmd_str[-1] and cmd_str[0] in ("\"", "'") and cmd_str.count(cmd_str[0]) == 2:
                cmd_str = cmd_str[1:-1].strip()
            cmd_lower = cmd_str.lower()
            cmd_norm = re.sub(r"\s+", " ", cmd_lower)

            hit = any(b in cmd_lower or b in cmd_norm for b in BLOCKED_COMMANDS) or any(re.search(pat, cmd_norm) for pat in BLOCKED_PATTERNS)
            if hit:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Erişim Engellendi: Tehlikeli komut tespiti! -> '{cmd_str}'"
                )

            cwd_val = kwargs.get("cwd", ".")
            target_cwd = (WORKSPACE_ROOT / str(cwd_val)).resolve() if not Path(str(cwd_val)).is_absolute() else Path(str(cwd_val)).resolve()

            try:
                target_cwd.relative_to(WORKSPACE_ROOT)
            except ValueError:
                target_cwd = WORKSPACE_ROOT

            if not target_cwd.exists():
                target_cwd = WORKSPACE_ROOT

            logger.info(f"Terminal Komutu Çalıştırılıyor: '{cmd_str}' [Dizin: {target_cwd}]")

            # EVENT LOOP KİLİTLENMEMESİ İÇİN ASENKRON THREAD
            res = await asyncio.to_thread(
                subprocess.run,
                cmd_str,
                shell=True,
                cwd=str(target_cwd),
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace"
            )

            output_text = res.stdout.strip()
            error_text = res.stderr.strip()

            if res.returncode == 0:
                return ToolResult(
                    success=True,
                    output=f"💻 **[TERMINAL KOMUTU İCRA EDİLDİ]** (`{cmd_str}`)\n\n```text\n{output_text or 'Komut başarıyla tamamlandı (Çıktı yok).'}\n```",
                    metadata={"return_code": 0, "command": cmd_str}
                )
            else:
                return ToolResult(
                    success=False,
                    output=output_text,
                    error=f"Terminal Komut Hatası [{res.returncode}]:\n{error_text or output_text}",
                    metadata={"return_code": res.returncode}
                )

        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output=None, error="Terminal komutu zaman aşımına uğradı (Timeout: 30s).")
        except Exception as e:
            logger.error(f"Terminal hatasi: {e}")
            return ToolResult(success=False, output=None, error=str(e))
