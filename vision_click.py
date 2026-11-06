import base64
import json
import re
from pathlib import Path
from typing import Optional
import httpx
import pyautogui
from PIL import ImageGrab
from core.config import get_settings
from core.logger import setup_logger
from core.types import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("VisionClickTools")
from core.paths import WORKSPACE_ROOT
settings = get_settings()

NON_VISION_PATTERNS = ("canopylabs", "whisper", "guard", "embed", "safeguard", "audio", "tts", "gpt-oss")


class VisionClickTool(BaseTool):
    name = "vision_click"
    description = "Ekran goruntusunu alir, Vision AI ile istenen butonun/ikonun koordinatlarini bulur ve fareyle tiklar."
    risk_level = RiskLevel.HIGH

    async def execute(self, element_name: str, click_type: str = "double_click", **kwargs) -> ToolResult:
        try:
            screen_file = WORKSPACE_ROOT / "storage" / "temp_vision_click.png"
            screen_file.parent.mkdir(parents=True, exist_ok=True)

            screenshot = ImageGrab.grab()
            screenshot.save(screen_file, "PNG")
            screen_w, screen_h = pyautogui.size()

            with open(screen_file, "rb") as img_f:
                b64_img = base64.b64encode(img_f.read()).decode("utf-8")

            coords = await self._locate_element_coordinates(b64_img, element_name)
            if not coords:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Vision AI ekranda '{element_name}' ögesinin yerini tespit edemedi."
                )

            x_pct, y_pct = coords
            target_x = max(0, min(int((x_pct / 100.0) * screen_w), screen_w - 1))
            target_y = max(0, min(int((y_pct / 100.0) * screen_h), screen_h - 1))

            pyautogui.moveTo(target_x, target_y, duration=0.3)
            if click_type == "double_click":
                pyautogui.doubleClick(target_x, target_y)
            else:
                pyautogui.click(target_x, target_y)

            return ToolResult(
                success=True,
                output=f"👁️🖱️ **[GÖRSEL VISION TIKLAMA BAŞARILI]**: Ekranda '{element_name}' algılandı. ({target_x}, {target_y}) konumuna tıklandı.",
                metadata={"x": target_x, "y": target_y, "element": element_name}
            )

        except Exception as e:
            logger.error(f"VisionClick hatasi: {e}")
            return ToolResult(success=False, output=None, error=str(e))

    async def _locate_element_coordinates(self, b64_img: str, element_name: str) -> Optional[tuple]:
        if not settings.GROQ_API_KEY:
            return None

        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
        }

        # Dynamic Vision Model Discovery
        vision_model = None
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                m_res = await client.get("https://api.groq.com/openai/v1/models", headers=headers)
                if m_res.status_code == 200:
                    available = [m.get("id", "") for m in m_res.json().get("data", [])]
                    v_matches = [
                        m for m in available 
                        if ("vision" in m.lower() or "llava" in m.lower()) 
                        and not any(bad in m.lower() for bad in NON_VISION_PATTERNS)
                    ]
                    if v_matches:
                        vision_model = v_matches[0]
        except Exception:
            pass

        if not vision_model:
            vision_model = "llama-3.2-11b-vision-preview"

        url = "https://api.groq.com/openai/v1/chat/completions"
        prompt_text = (
            f"Analyze this computer screenshot. I want to click on '{element_name}'. "
            f"Estimate the center coordinates as percentage of screen width and height (0 to 100). "
            f"Reply ONLY with JSON: {{\"x_percent\": float, \"y_percent\": float}}"
        )

        payload = {
            "model": vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}}
                    ]
                }
            ],
            "max_tokens": 150
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, json=payload, headers=headers)
                if res.status_code == 200:
                    raw = res.json()["choices"][0]["message"]["content"]
                    match = re.search(r"\{.*\}", raw, re.DOTALL)
                    if match:
                        data = json.loads(match.group(0))
                        return (float(data["x_percent"]), float(data["y_percent"]))
        except Exception:
            pass
        return None
