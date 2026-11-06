import os
import re
import subprocess
import psutil
from core.logger import setup_logger
from tasks.models import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("ProcessManagerTools")

PROCESS_MAP = {
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "opera": "opera.exe",
    "opera gx": "opera.exe",
    "steam": "steam.exe",
    "discord": "discord.exe",
    "notepad": "notepad.exe",
    "not defteri": "notepad.exe",
    "calc": "calc.exe",
    "calculator": "calc.exe",
    "hesap makinesi": "calc.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "code": "code.exe",
    "vs code": "code.exe",
    "cursor": "cursor.exe",
    "winrar": "winrar.exe",
    "fc 26": "ea sports fc 26 showcase.exe",
    "spotify": "spotify.exe",
}

PROTECTED_PROCESSES = {
    "system", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe", "lsass.exe",
    "svchost.exe", "dwm.exe", "explorer.exe", "fontdrvhost.exe", "registry",
}
SAFE_EXE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.\-]{0,63}\.exe$")


def _extract_app_entity(raw_text: str) -> str:
    lower = raw_text.lower()
    for app_key in sorted(PROCESS_MAP.keys(), key=len, reverse=True):
        if app_key in lower:
            return app_key

    stop_words = ["kapat", "close", "kill", "sonlandır", "açıldıktan", "sonra", "önce", "yaz", "lütfen", "veya", "ve", "de", "da"]
    words = re.findall(r'\b\w+\b', lower)
    clean_words = [w for w in words if w not in stop_words]
    return " ".join(clean_words) if clean_words else raw_text


class ProcessKillTool(BaseTool):
    name = "process_kill"
    description = "Bilgisayarda calisan uygulamalari (Edge, Chrome, Cursor, Steam vb.) tum surec agaciyla (Process Tree) birlikte zorla kapatir."
    risk_level = RiskLevel.MEDIUM

    async def execute(self, target: str, **kwargs) -> ToolResult:
        try:
            app_entity = _extract_app_entity(target)
            exe_name = PROCESS_MAP.get(app_entity, f"{app_entity}.exe" if not app_entity.endswith(".exe") else app_entity)

            if not SAFE_EXE_RE.match(exe_name):
                return ToolResult(success=False, output=None, error=f"Geçersiz süreç adı: '{exe_name}'")
            if exe_name.lower() in PROTECTED_PROCESSES:
                return ToolResult(success=False, output=None, error=f"Erişim engellendi: korumalı sistem süreci: {exe_name}")

            # Kendini koruma: JARVIS'in kendi sureci ve ust surecleri (konsol/terminal) sonlandirilmasin.
            own_pids = {os.getpid()}
            try:
                own_pids.update(p.pid for p in psutil.Process(os.getpid()).parents())
            except Exception:
                pass
            own_names = set()
            for _pid in own_pids:
                try:
                    own_names.add(psutil.Process(_pid).name().lower())
                except Exception:
                    pass
            if exe_name.lower() in own_names:
                return ToolResult(
                    success=False, output=None,
                    error=f"Erişim engellendi: '{exe_name}' JARVIS'i çalıştıran sürecin kendisi; kapatılamaz."
                )

            running_pids = []
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    p_name = proc.info['name'].lower() if proc.info['name'] else ""
                    if exe_name.lower() in p_name or (app_entity and app_entity in p_name):
                        running_pids.append(proc.info['pid'])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            if not running_pids:
                return ToolResult(
                    success=True,
                    output=f"ℹ️ **[CANLI SÜREÇ DENETİMİ]**: **{app_entity.upper()}** uygulaması şu anda bilgisayarınızda çalışmıyor. Kapatılacak aktif işlem yok.",
                    metadata={"not_running": [app_entity]}
                )

            cmd = ["taskkill", "/F", "/T", "/IM", exe_name]
            res = subprocess.run(cmd, capture_output=True, text=True)

            logger.info(f"Taskkill Tree Executed: {cmd} | ReturnCode: {res.returncode} | Output: {res.stdout} | Error: {res.stderr}")

            # GUVENLIK/DOGRULUK FIX (Milestone 4): returncode kontrol edilmeden
            # koşulsuz success=True donuluyordu. taskkill basarisiz olsa
            # (yetki reddi, process zaten kapanmis, vb.) bile kullaniciya
            # 'basariyla kapatildi' yalani soyleniyordu.
            if res.returncode != 0:
                err_detail = res.stderr.strip() or res.stdout.strip() or f"taskkill returncode={res.returncode}"
                logger.warning(f"Taskkill basarisiz oldu: {exe_name} | {err_detail}")
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Süreç sonlandırılamadı: **{app_entity.upper()}** ({exe_name}). Detay: {err_detail}",
                    metadata={"target": app_entity, "returncode": res.returncode}
                )

            return ToolResult(
                success=True,
                output=f"🛑 **[GÖRÜNÜR PENCERE VE TÜM SÜREÇLER KAPATILDI]**: **{app_entity.upper()}** uygulamasına ait tüm süreç ağacı ({len(running_pids)} adet işlem) fiziki olarak kapatıldı.",
                metadata={"target": app_entity, "killed_pids_count": len(running_pids)}
            )

        except Exception as e:
            logger.error(f"ProcessKill hatasi: {e}")
            return ToolResult(success=False, output=None, error=str(e))
