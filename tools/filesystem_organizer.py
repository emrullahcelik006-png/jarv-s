import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
from core.logger import setup_logger
from core.types import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("FilesystemOrganizer")

CATEGORIES = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico"],
    "Documents": [".pdf", ".docx", ".doc", ".xlsx", ".pptx", ".txt", ".csv", ".epub"],
    "Installers": [".exe", ".msi", ".iso"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "Audio_Video": [".mp3", ".wav", ".mp4", ".mkv", ".avi", ".mov", ".flv"],
    "Projects_Code": [".py", ".json", ".html", ".css", ".js", ".ts", ".db", ".sqlite", ".cpp", ".c", ".cs", ".php"]
}


class SystemOrganizerTool(BaseTool):
    name = "system_organizer"
    description = "Organizes messy files in any directory (Downloads, Desktop, Documents) by category and optionally by modification date (YYYY-MM)."
    risk_level = RiskLevel.MEDIUM

    async def execute(self, target_dir: str = "downloads", by_date: Union[bool, str] = False, **kwargs) -> ToolResult:
        try:
            user_home = Path(os.path.expanduser("~")).resolve()
            clean_dir = str(target_dir).lower().strip()

            if clean_dir in ("downloads", "indirilenler"):
                target_path = user_home / "Downloads"
            elif clean_dir in ("desktop", "masaüstü", "masaustu"):
                target_path = user_home / "Desktop"
            elif clean_dir in ("documents", "belgeler"):
                target_path = user_home / "Documents"
            else:
                target_path = Path(target_dir).resolve()

            if not target_path.exists():
                return ToolResult(success=False, output=None, error=f"Hedef klasör bulunamadı: {target_path}")

            use_date = self.coerce_bool(by_date, default=False)
            moved_count = 0
            moved_summary = []

            for item in target_path.iterdir():
                if item.is_file() and not item.name.startswith("."):
                    ext = item.suffix.lower()
                    matched_cat = None

                    for cat, ext_list in CATEGORIES.items():
                        if ext in ext_list:
                            matched_cat = cat
                            break

                    if matched_cat:
                        if use_date:
                            mtime = item.stat().st_mtime
                            date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m")
                            cat_folder_name = f"{date_str}_{matched_cat}"
                        else:
                            cat_folder_name = matched_cat

                        dest_dir = target_path / cat_folder_name
                        dest_dir.mkdir(exist_ok=True)
                        dest_file = dest_dir / item.name

                        if not dest_file.exists():
                            shutil.move(str(item), str(dest_file))
                            moved_count += 1
                            moved_summary.append(f"• `{item.name}` ➔ `{cat_folder_name}/`")

            if moved_count == 0:
                return ToolResult(
                    success=True,
                    output=f"📂 **[KLASÖR DÜZENLEYİCİ]**: `{target_path.name}` klasöründe taşınacak dağınık dosya bulunamadı."
                )

            return ToolResult(
                success=True,
                output=f"🧹 **[SİSTEM DÜZENLENDİ]**: `{target_path.name}` klasöründeki {moved_count} adet dosya kategorilerine göre toplandı:\n\n" + "\n".join(moved_summary[:20]),
                metadata={"moved_count": moved_count, "target_dir": str(target_path)}
            )

        except Exception as e:
            logger.error(f"SystemOrganizer error: {e}")
            return ToolResult(success=False, output=None, error=str(e))
