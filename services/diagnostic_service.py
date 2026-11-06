import json
import uuid
import psutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from core.logger import setup_logger

logger = setup_logger("DiagnosticService")
from core.paths import WORKSPACE_ROOT


class DiagnosticService:
    def __init__(self, reports_dir: str = "storage/reports"):
        self.reports_dir = (WORKSPACE_ROOT / reports_dir).resolve()
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def create_report(
        event_type: str,
        user_prompt: str,
        error_message: str,
        tool_name: str,
        context: Optional[Dict[str, Any]] = None,
        reports_dir: str = "storage/reports"
    ) -> str:
        """Sistem hatalarini ve olaylarini diske rapor dosyasi olarak kaydeder ve dosya yolunu doner."""
        out_dir = (WORKSPACE_ROOT / reports_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        report_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{event_type.lower()}_{timestamp}_{report_id}.txt"
        filepath = out_dir / filename

        report_lines = [
            f"=== JARVIS DIAGNOSTIC ERROR REPORT [{timestamp}] ===",
            f"Event Type: {event_type}",
            f"Tool Name: {tool_name}",
            f"User Prompt: {user_prompt}",
            f"Error Message: {error_message}",
            f"Context: {json.dumps(context or {}, ensure_ascii=False)}",
            f"====================================================="
        ]

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))

        logger.info(f"Diagnostic report created at: {filepath}")
        return str(filepath)

    def run_full_diagnostics(self) -> Dict[str, Any]:
        """Bilgisayarin tum hayati organlarini tarayip anomali tespiti yapar."""
        cpu_percent = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")

        high_ram_processes: List[Dict[str, Any]] = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
            try:
                ram_mb = proc.info['memory_info'].rss / (1024 * 1024)
                if ram_mb > 200:
                    high_ram_processes.append({
                        "name": proc.info['name'],
                        "pid": proc.info['pid'],
                        "ram_mb": round(ram_mb, 2)
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        high_ram_processes.sort(key=lambda x: x['ram_mb'], reverse=True)

        anomalies = []
        if mem.percent > 85:
            anomalies.append(f"KRITIK RAM YUKU: Bellek %{mem.percent} dolulukta!")
        if cpu_percent > 80:
            anomalies.append(f"YUKSEK CPU YUKU: Islemci %{cpu_percent} kullanimda!")
        if disk.percent > 90:
            anomalies.append(f"DUSUK DISK ALANI: C: Surucusu %{disk.percent} dolu!")

        report = {
            "status": "HEALTHY" if not anomalies else "WARNING",
            "cpu_usage_percent": cpu_percent,
            "ram_total_gb": round(mem.total / (1024**3), 2),
            "ram_used_gb": round(mem.used / (1024**3), 2),
            "ram_percent": mem.percent,
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_free_gb": round(disk.free / (1024**3), 2),
            "disk_percent": disk.percent,
            "anomalies": anomalies,
            "top_memory_hogs": high_ram_processes[:5]
        }
        return report

    def format_diagnostic_report(self) -> str:
        data = self.run_full_diagnostics()
        status_icon = "✅" if data["status"] == "HEALTHY" else "⚠️"
        
        lines = [
            f"{status_icon} **[SİSTEM TEŞHİS RAPORU]**",
            f"• **Genel Sağlık:** `{data['status']}`",
            f"• **CPU Kullanımı:** %{data['cpu_usage_percent']}",
            f"• **RAM (Bellek):** {data['ram_used_gb']} GB / {data['ram_total_gb']} GB (%{data['ram_percent']})",
            f"• **Disk (C:):** {data['disk_free_gb']} GB Boş / {data['disk_total_gb']} GB (%{data['disk_percent']} Dolu)",
        ]

        if data["anomalies"]:
            lines.append("\n🚨 **[ALARM VE ANOMALİLER]**")
            for anom in data["anomalies"]:
                lines.append(f"  - {anom}")

        if data["top_memory_hogs"]:
            lines.append("\n🐘 **[EN YÜKSEK RAM TÜKETEN UYGULAMALAR]**")
            for proc in data["top_memory_hogs"]:
                lines.append(f"  - `{proc['name']}` (PID: {proc['pid']}): {proc['ram_mb']} MB")

        return "\n".join(lines)
