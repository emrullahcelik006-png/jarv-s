import os
import pyautogui
from pathlib import Path
from core.logger import setup_logger
from tasks.models import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("DesktopVisionTools")
USER_HOME = Path(os.path.expanduser("~")).resolve()


class DesktopIconClickTool(BaseTool):
    name = "desktop_icon_click"
    description = "Masaustundeki oyun veya uygulama simgesini bulur ve fareyle cift tiklayarak acalar."
    risk_level = RiskLevel.MEDIUM

    async def execute(self, icon_name: str, **kwargs) -> ToolResult:
        try:
            clean_name = icon_name.lower().replace("aç", "").replace("oyununu", "").strip()
            desktop_dir = USER_HOME / "Desktop"

            target_file = None
            if desktop_dir.exists():
                for f in desktop_dir.iterdir():
                    if clean_name in f.stem.lower():
                        target_file = f
                        break

            if target_file:
                # Masaüstü simgesini Windows Shell uzerinden firlat
                os.startfile(str(target_file))
                logger.info(f"Masaüstü ikonu başlatıldı: {target_file}")
                return ToolResult(
                    success=True,
                    output=f"🖱️🎮 **[MASAÜSTÜ İKONU ÇİFT TIKLANDI VE AÇILDI]**: Masaüstündeki '{target_file.name}' ikonu başlatıldı.",
                    metadata={"file": str(target_file)}
                )

            return ToolResult(success=False, output=None, error=f"Masaüstünde '{icon_name}' adında bir simge bulunamadı.")
        except Exception as e:
            logger.error(f"DesktopIconClick hatasi: {e}")
            return ToolResult(success=False, output=None, error=str(e))
