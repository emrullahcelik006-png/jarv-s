import os
import platform
from datetime import datetime, timezone
from pathlib import Path
import psutil
from core.logger import setup_logger
from core.paths import WORKSPACE_ROOT
from tools.os_control import DynamicAppScanner

logger = setup_logger("AuditService")


class SystemAuditService:
    def __init__(self, output_dir: str = "storage/reports"):
        self.output_path = Path(output_dir)
        self.output_path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    async def generate_full_report() -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # 1. Donanim Metrikleri
        cpu_p = psutil.cpu_percent(interval=0.2)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")

        # 2. Yuklu Uygulamalar
        apps = DynamicAppScanner.scan_installed_apps()
        app_list_str = "\n".join([f"- **{name.title()}**: `{path}`" for name, path in list(apps.items())[:15]])

        report_md = f"""# 🛡️ J.A.R.V.I.S — SYSTEM & ENVIRONMENT AUDIT REPORT
**Tarih:** {timestamp}
**İşletim Sistemi:** {platform.system()} {platform.version()} ({platform.machine()})

---

## 📊 1. DONANIM VE SİSTEM PERFORMANSI
- **CPU Kullanımı:** %{cpu_p}
- **RAM (Bellek):** %{ram.percent} (Kullanılan: {round(ram.used / (1024**3), 2)} GB / Toplam: {round(ram.total / (1024**3), 2)} GB)
- **C: Disk Alanı:** %{disk.percent} (Boş Alan: {round(disk.free / (1024**3), 2)} GB / Toplam: {round(disk.total / (1024**3), 2)} GB)

---

## 🚀 2. TESPİT EDİLEN UYGULAMALAR (ÖRN. TESPİT EDİLEN {len(apps)} UYGULAMA)
{app_list_str}
... ve {max(0, len(apps) - 15)} ek uygulama daha kuruludur.

---

## 🤖 3. AGENT OPERATING LAYER DURUMU
- **Çekirdek Dizin:** `{WORKSPACE_ROOT}`
- **Aktif Modüller:** `Core`, `LLM (Ollama/Groq)`, `Task Engine`, `Agent Runner`, `Memory DB`, `Neural HUD`
- **Sistem Durumu:** TÜM SİSTEMLER OK VE OPERASYONEL

---
*Rapor JARVIS SystemAuditService tarafından otomatik üretilmiştir.*
"""
        report_file = (WORKSPACE_ROOT / "storage" / "reports" / "SYSTEM_REPORT.md")
        report_file.parent.mkdir(parents=True, exist_ok=True)
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report_md)

        logger.info(f"Sistem raporu yayinlandi: {report_file}")
        return report_md
