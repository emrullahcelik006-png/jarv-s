import os
import psutil
from datetime import datetime, timezone
from pathlib import Path
from core.logger import setup_logger
from core.paths import WORKSPACE_ROOT
from tasks.models import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("ReportTools")
USER_HOME = Path(os.path.expanduser("~")).resolve()

EXCLUDE_DIRS = {".venv", "node_modules", ".git", "appdata", "build", "dist", "__pycache__", ".pytest_cache"}


class ProblemAnalysisReportTool(BaseTool):
    name = "problem_analysis_report"
    description = "Masaustu ve Indirilenlerdeki .txt/.py dosyalarini hizlica tara, 'Hata/Error' gecenleri bulur ve rapor yazar."
    risk_level = RiskLevel.MEDIUM

    async def execute(self, output_file: str = "storage/reports/SORUN_ANALIZI.md", **kwargs) -> ToolResult:
        try:
            targets = [USER_HOME / "Desktop", USER_HOME / "Downloads"]
            found_files = []

            for target_dir in targets:
                if not target_dir.exists():
                    continue
                for root, dirs, files in os.walk(target_dir):
                    # 1. HIZLANDIRMA: Ağır yazılım klasörlerini atla
                    dirs[:] = [d for d in dirs if d.lower() not in EXCLUDE_DIRS and not d.startswith(".")]

                    # 2. HIZLANDIRMA: Sadece ilk 2 alt klasör derinliğine bak
                    rel_depth = len(Path(root).relative_to(target_dir).parts)
                    if rel_depth > 2:
                        dirs.clear()
                        continue

                    for file in files:
                        if file.lower().endswith((".txt", ".py")):
                            file_path = Path(root) / file
                            try:
                                # 3. HIZLANDIRMA: 500 KB'tan büyük devasa dosyaları atla
                                if file_path.stat().st_size > 500_000:
                                    continue
                                with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                                    content = f.read(100000)  # Ilk 100 KB oku
                                    if "hata" in content.lower() or "error" in content.lower():
                                        found_files.append(str(file_path))
                            except Exception:
                                pass

            ram = psutil.virtual_memory()
            ram_str = f"%{ram.percent} (Kullanılan: {round(ram.used / (1024**3), 2)} GB / Toplam: {round(ram.total / (1024**3), 2)} GB)"
            file_list_str = "\n".join([f"- `{p}`" for p in found_files]) if found_files else "- Tarama alanında 'Hata/Error' içeren dosya tespit edilmedi."

            report_md = f"""# 🔍 J.A.R.V.I.S — SORUN VE HATA ANALİZ RAPORU
**Tarih:** {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}

---

## 📊 1. ANLIK BELLEK (RAM) DURUMU
- **RAM Kullanımı:** {ram_str}

---

## 📁 2. 'HATA' / 'ERROR' İÇEREN TESPİT EDİLEN DOSYALAR ({len(found_files)} Adet)
{file_list_str}

---
*Rapor JARVIS ProblemAnalysisReportTool tarafından otomatik üretilmiştir.*
"""
            out_path = (WORKSPACE_ROOT / "storage" / "reports" / "SORUN_ANALIZI.md")
            out_path.parent.mkdir(parents=True, exist_ok=True)

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(report_md)

            logger.info(f"Sorun analiz raporu fiziki yazıldı: {out_path}")

            return ToolResult(
                success=True,
                output=f"📊 **[SORUN ANALİZ RAPORU OLUŞTURULDU]**: Rapor `{out_path}` konumuna fiziki olarak yazıldı.\n\n" + report_md[:500],
                metadata={"filepath": str(out_path), "found_count": len(found_files)}
            )
        except Exception as e:
            logger.error(f"Report tool hatasi: {e}")
            return ToolResult(success=False, output=None, error=str(e))
