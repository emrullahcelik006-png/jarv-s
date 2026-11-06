import base64
import asyncio
from pathlib import Path
from typing import Optional
from core.config import get_settings
from core.logger import setup_logger
from core.types import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("CameraSensorTools")
from core.paths import WORKSPACE_ROOT
settings = get_settings()


def _capture_frame_sync(output_file_path: Path) -> bool:
    """Captures a single frame from local webcam using OpenCV/Windows Media drivers."""
    try:
        import cv2
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return False

        # Camera sensor warmup
        for _ in range(5):
            cap.read()

        ret, frame = cap.read()
        cap.release()

        if ret and frame is not None:
            cv2.imwrite(str(output_file_path), frame)
            return True
        return False
    except Exception as e:
        logger.warning(f"OpenCV camera frame capture error: {e}")
        return False


class CameraVisionTool(BaseTool):
    name = "camera_vision"
    description = "Captures a single photo frame from webcam and analyzes the scene using Vision AI."
    risk_level = RiskLevel.LOW

    async def execute(self, output_file: str = "storage/temp_camera.png", prompt: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            target_path = (WORKSPACE_ROOT / output_file).resolve()
            target_path.parent.mkdir(parents=True, exist_ok=True)

            captured = await asyncio.to_thread(_capture_frame_sync, target_path)

            if not captured or not target_path.exists():
                return ToolResult(
                    success=False,
                    output=None,
                    error="Kamera sensörüne erişilemedi veya aktif kamera cihazı bulunamadı."
                )

            with open(target_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode("utf-8")

            from tools.screen import ScreenCaptureTool
            screen_tool = ScreenCaptureTool()
            user_inst = prompt or "Bu bir kamera görüntüsüdür. Kameranın önünde ne var, ortamda/odada neler görünüyor? Türkçe detaylı açıkla."
            vision_analysis = await screen_tool._analyze_image_with_vision(base64_image, user_prompt=user_inst)

            return ToolResult(
                success=True,
                output=f"👁️ **[KAMERA VİZYON SENSÖRÜ]**\n\n{vision_analysis}\n\n*(Fotoğraf kaydedildi: `{target_path}`)*",
                metadata={"filepath": str(target_path)}
            )
        except Exception as e:
            logger.error(f"CameraVision error: {e}")
            return ToolResult(success=False, output=None, error=str(e))
