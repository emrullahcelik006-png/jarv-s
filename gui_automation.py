import time
import pyautogui
from core.logger import setup_logger
from tasks.models import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("GUIAutomation")

# Güvenlik için PyAutoGUI fail-safe
pyautogui.FAILSAFE = True


class KeyPressTool(BaseTool):
    name = "key_press"
    description = "Klavyeden fiziki tuslara veya tus kombinasyonlarina basar (win, enter, alt+tab, ctrl+c, space, esc, backspace vb.)."
    risk_level = RiskLevel.MEDIUM

    KEY_MAP = {
        "windows": "win",
        "win": "win",
        "windows tuşu": "win",
        "enter": "enter",
        "gir": "enter",
        "space": "space",
        "boşluk": "space",
        "backspace": "backspace",
        "sil": "backspace",
        "esc": "esc",
        "escape": "esc",
        "tab": "tab",
    }

    async def execute(self, key_name: str = "win", **kwargs) -> ToolResult:
        try:
            clean_key = key_name.lower().strip()
            
            # Kombinasyon kontrolü (örn: "alt+tab" veya "ctrl+c")
            if "+" in clean_key:
                keys = [k.strip() for k in clean_key.split("+")]
                pyautogui.hotkey(*keys)
                return ToolResult(success=True, output=f"Tuş kombinasyonuna basıldı: {clean_key}")

            target_key = self.KEY_MAP.get(clean_key, clean_key)
            pyautogui.press(target_key)
            logger.info(f"Fiziki tuşa basıldı: {target_key}")
            return ToolResult(success=True, output=f"Fiziki tuşa basıldı: '{target_key}'")

        except Exception as e:
            logger.error(f"Tuş basma hatası: {e}")
            return ToolResult(success=False, output=None, error=str(e))
