import os
import re
import subprocess
import sys
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from core.logger import setup_logger
from core.types import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("AdvancedOSTools")


class PipInstallerTool(BaseTool):
    name = "pip_installer"
    description = "Installs missing Python packages autonomously using pip."
    risk_level = RiskLevel.HIGH

    async def execute(self, package_name: str, **kwargs) -> ToolResult:
        try:
            parts = str(package_name or "").strip().split()
            clean_pkg = parts[0] if parts else ""
            if not clean_pkg:
                return ToolResult(success=False, output=None, error="Paket adı gerekli.")
            # Secenek enjeksiyonu (--index-url, -r dosya, URL vb.) engeli: yalnizca duz paket adi.
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}(?:==[A-Za-z0-9_.\-]{1,32})?", clean_pkg):
                return ToolResult(success=False, output=None, error=f"Gecersiz paket adi: '{clean_pkg}'")
            
            logger.warning(f"Autonomous PIP Install initiated for: {clean_pkg}")
            # sys.executable: JARVIS'in KENDI (venv) Python'una kurar; "py" baska bir Python'a gidebilir.
            cmd = [sys.executable, "-m", "pip", "install", clean_pkg]
            
            proc = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True, timeout=120
            )
            
            if proc.returncode == 0:
                return ToolResult(
                    success=True, 
                    output=f"📦 **[SİSTEM GÜNCELLEMESİ]**: `{clean_pkg}` kütüphanesi sisteme başarıyla kuruldu.\n\n```text\n{proc.stdout[-300:]}\n```"
                )
            else:
                return ToolResult(success=False, output=None, error=f"PIP Install failed: {proc.stderr}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class PowerManagementTool(BaseTool):
    name = "power_management"
    description = "Controls OS power states: lock, sleep, restart, shutdown."
    risk_level = RiskLevel.HIGH

    async def execute(self, action: str, **kwargs) -> ToolResult:
        try:
            act = action.lower().strip()
            if act in ("lock", "kilitle"):
                os.system("rundll32.exe user32.dll,LockWorkStation")
                return ToolResult(success=True, output="🔒 **[GÜVENLİK]**: Bilgisayar kilitlendi.")
            elif act in ("sleep", "uyku"):
                os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
                return ToolResult(success=True, output="💤 **[GÜÇ]**: Bilgisayar uyku moduna alındı.")
            elif act in ("restart", "yeniden başlat"):
                os.system("shutdown /r /t 5")
                return ToolResult(success=True, output="🔄 **[GÜÇ]**: Bilgisayar 5 saniye içinde yeniden başlatılacak.")
            elif act in ("shutdown", "kapat"):
                os.system("shutdown /s /t 5")
                return ToolResult(success=True, output="🛑 **[GÜÇ]**: Bilgisayar 5 saniye içinde kapatılacak.")
            elif act in ("abort", "iptal"):
                os.system("shutdown /a")
                return ToolResult(success=True, output="✅ **[GÜÇ]**: Kapatma/Yeniden başlatma işlemi iptal edildi.")
            
            return ToolResult(success=False, output=None, error="Bilinmeyen güç komutu.")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class WindowsServiceTool(BaseTool):
    name = "windows_service_manager"
    description = "Checks the status of background Windows Services."
    risk_level = RiskLevel.MEDIUM

    async def execute(self, service_name: str, **kwargs) -> ToolResult:
        try:
            import psutil
            srv = psutil.win_service_get(service_name.strip())
            info = srv.as_dict()
            return ToolResult(
                success=True, 
                output=f"⚙️ **[WİNDOWS SERVİSİ]**: `{info['name']}` ({info['display_name']})\n• **Durum:** {info['status'].upper()}\n• **Başlangıç:** {info['start_type']}"
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Servis bulunamadı: {e}")


def _search_drive(drive_letter: str, filename: str) -> list:
    results = []
    try:
        for root, dirs, files in os.walk(f"{drive_letter}:\\"):
            if len(results) >= 5:
                break
            dirs[:] = [d for d in dirs if d.lower() not in ["windows", "program files", "program files (x86)", "$recycle.bin"]]
            for f in files:
                if filename.lower() in f.lower():
                    results.append(os.path.join(root, f))
    except Exception:
        pass
    return results


class DeepFileSearchTool(BaseTool):
    name = "deep_file_search"
    description = "Searches for a specific file across the entire C:\\ drive."
    risk_level = RiskLevel.MEDIUM

    async def execute(self, filename: str, **kwargs) -> ToolResult:
        try:
            target = filename.strip()
            if len(target) < 3:
                return ToolResult(success=False, output=None, error="Arama terimi en az 3 karakter olmalı.")
            
            loop = asyncio.get_running_loop()
            with ThreadPoolExecutor(max_workers=2) as pool:
                task = loop.run_in_executor(pool, _search_drive, "C", target)
                try:
                    found_files = await asyncio.wait_for(task, timeout=45.0)
                except asyncio.TimeoutError:
                    return ToolResult(success=False, output=None, error="Tarama 45 saniyeyi aştığı için durduruldu.")

            if not found_files:
                return ToolResult(success=True, output=f"🔎 **[DERİN TARAMA]**: '{target}' adında dosya bulunamadı.")

            lines = [f"• `{p}`" for p in found_files]
            return ToolResult(
                success=True,
                output=f"🔎 **[DERİN TARAMA]**: '{target}' için {len(found_files)} sonuç bulundu:\n\n" + "\n".join(lines)
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
