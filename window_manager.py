import pygetwindow as gw
import psutil
from typing import List, Dict, Any
from core.logger import setup_logger
from core.types import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("WindowManagerTools")

try:
    import win32process
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

SYSTEM_GHOST_TITLES = (
    "program manager",
    "settings",
    "popuphost",
    "msctfime ui",
    "default ime",
    "windows input experience",
    "nvidia geforce overlay",
    "systemresourcenotifywindow",
    "action center",
    "start",
    "taskbar",
    "system tray"
)

SYSTEM_GHOST_PROCS = (
    "shellexperiencehost.exe",
    "searchhost.exe",
    "systemsettings.exe",
    "textinputhost.exe",
    "lockapp.exe",
    "applicationframehost.exe"
)


class WindowManagerTool(BaseTool):
    name = "window_manager"
    description = "pygetwindow ve win32process kullanarak acik tum pencereleri PID ve surec adi ile listeler veya istenen pencereyi one getirir."
    risk_level = RiskLevel.MEDIUM

    async def execute(self, action: str = "list_windows", target_title: str = "", **kwargs) -> ToolResult:
        try:
            act = action.lower().strip()
            all_windows = gw.getAllWindows()

            visible_windows = []
            window_details = []

            for w in all_windows:
                if not w.title or not w.title.strip() or not w.visible:
                    continue

                title_lower = w.title.lower().strip()
                if title_lower in SYSTEM_GHOST_TITLES or any(g in title_lower for g in ("popuphost", "msctfime", "default ime")):
                    continue

                proc_name = "unknown"
                pid = None

                if WIN32_AVAILABLE and hasattr(w, "_hWnd") and w._hWnd:
                    try:
                        _, pid = win32process.GetWindowThreadProcessId(w._hWnd)
                        if pid:
                            proc_name = psutil.Process(pid).name().lower()
                            if proc_name in SYSTEM_GHOST_PROCS and title_lower in ("settings", "start", "search"):
                                continue
                    except Exception:
                        pass

                visible_windows.append(w)
                window_details.append({
                    "title": w.title,
                    "pid": pid,
                    "process_name": proc_name
                })

            if act in ("list_windows", "pencereleri_listele", "listele"):
                titles_list = [f"• `{w.title}`" for w in visible_windows]
                return ToolResult(
                    success=True,
                    output=f"🖥️ **[BİLGİSAYARDA AÇIK OLAN PENCERELER]** ({len(titles_list)} adet bulundu):\n\n" + "\n".join(titles_list),
                    metadata={"count": len(titles_list), "windows": [w.title for w in visible_windows], "details": window_details}
                )

            elif act in ("focus_window", "öneyüz", "one_getir", "focus"):
                clean_target = target_title.lower().strip()
                matched_window = None

                for w in visible_windows:
                    if clean_target in w.title.lower():
                        matched_window = w
                        break

                if matched_window:
                    try:
                        if matched_window.isMinimized:
                            matched_window.restore()
                        matched_window.activate()
                        return ToolResult(
                            success=True,
                            output=f"🖥️ **[PENCERE ÖNE GETİRİLDİ]**: '{matched_window.title}' penceresi öne taşındı ve aktif yapıldı.",
                            metadata={"title": matched_window.title}
                        )
                    except Exception as ex:
                        return ToolResult(success=False, output=None, error=f"Pencere aktif yapilamadi: {ex}")

                return ToolResult(success=False, output=None, error=f"Açık pencereler arasında '{target_title}' bulunamadı.")

            return ToolResult(success=False, output=None, error=f"Bilinmeyen pencere eylemi: {action}")

        except Exception as e:
            logger.error(f"WindowManager hatasi: {e}")
            return ToolResult(success=False, output=None, error=str(e))
