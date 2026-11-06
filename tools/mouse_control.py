import asyncio
import pyautogui
from typing import Optional, Union
from core.logger import setup_logger
from core.types import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("MouseControlTools")

# Safety fail-safe for PyAutoGUI
pyautogui.FAILSAFE = True


class MouseControlTool(BaseTool):
    name = "mouse_control"
    description = "Controls mouse movement, 2D scrolling (up/down/left/right), clicks, and dragging."
    risk_level = RiskLevel.LOW

    async def execute(
        self,
        action: str = "scroll",
        direction: str = "down",
        amount: Optional[Union[int, str]] = None,
        scroll_amount: Optional[Union[int, str]] = None,
        x: Optional[Union[int, str]] = None,
        y: Optional[Union[int, str]] = None,
        **kwargs
    ) -> ToolResult:
        try:
            act = str(action).lower().strip()
            direct = str(direction).lower().strip()

            # Handle parameter backward compatibility (scroll_amount vs amount)
            raw_val = scroll_amount if scroll_amount is not None else amount
            if raw_val is None:
                raw_val = 600

            try:
                val = int(raw_val)
            except (ValueError, TypeError):
                val = 600

            # 1. 2D SCROLLING (UP / DOWN / LEFT / RIGHT)
            if act in ("scroll", "kaydır", "kaydir"):
                # Negative scroll_amount handling for backward compatibility
                if val < 0 and direct == "down":
                    direct = "down"
                    val = abs(val)
                elif val < 0 and direct == "up":
                    direct = "down"
                    val = abs(val)

                if direct in ("up", "yukarı", "yukari"):
                    pyautogui.scroll(abs(val))
                    return ToolResult(
                        success=True,
                        output=f"🖱️ **[SAYFA KAYDIRILDI]**: Yukarı doğru {abs(val)} birim kaydırıldı."
                    )
                elif direct in ("left", "sol", "sola"):
                    try:
                        pyautogui.hscroll(-abs(val))
                    except Exception:
                        pyautogui.keyDown('shift')
                        pyautogui.scroll(-abs(val))
                        pyautogui.keyUp('shift')
                    return ToolResult(
                        success=True,
                        output=f"🖱️ **[SAYFA KAYDIRILDI]**: Sola doğru {abs(val)} birim kaydırıldı."
                    )
                elif direct in ("right", "sağ", "saga"):
                    try:
                        pyautogui.hscroll(abs(val))
                    except Exception:
                        pyautogui.keyDown('shift')
                        pyautogui.scroll(abs(val))
                        pyautogui.keyUp('shift')
                    return ToolResult(
                        success=True,
                        output=f"🖱️ **[SAYFA KAYDIRILDI]**: Sağa doğru {abs(val)} birim kaydırıldı."
                    )
                else:
                    # Default: Downward scrolling
                    pyautogui.scroll(-abs(val))
                    return ToolResult(
                        success=True,
                        output=f"🖱️ **[SAYFA KAYDIRILDI]**: Aşağı doğru {abs(val)} birim kaydırıldı."
                    )

            # 2. MOVEMENT & CLICKS
            elif act in ("move", "hareket", "git"):
                if x is not None and y is not None:
                    target_x, target_y = int(x), int(y)
                    pyautogui.moveTo(target_x, target_y, duration=0.2)
                    return ToolResult(success=True, output=f"🖱️ **[FARE]**: ({target_x}, {target_y}) koordinatına taşındı.")

            elif act in ("click", "tıkla", "tikla"):
                if x is not None and y is not None:
                    pyautogui.click(int(x), int(y))
                    return ToolResult(success=True, output=f"🖱️ **[FARE]**: ({x}, {y}) konumuna tıklandı.")
                pyautogui.click()
                return ToolResult(success=True, output="🖱️ **[FARE]**: Sol tıklandı.")

            elif act in ("double_click", "çift_tıkla"):
                pyautogui.doubleClick()
                return ToolResult(success=True, output="🖱️ **[FARE]**: Çift tıklandı.")

            elif act in ("right_click", "sağ_tıkla"):
                pyautogui.rightClick()
                return ToolResult(success=True, output="🖱️ **[FARE]**: Sağ tıklandı.")

            return ToolResult(success=False, output=None, error=f"Bilinmeyen fare eylemi: {action}")

        except Exception as e:
            logger.error(f"MouseControl error: {e}")
            return ToolResult(success=False, output=None, error=str(e))
