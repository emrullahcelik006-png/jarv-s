import base64
import httpx
from pathlib import Path
from PIL import ImageGrab
from typing import Optional
from core.config import get_settings
from core.logger import setup_logger
from core.types import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("ScreenTools")
from core.paths import WORKSPACE_ROOT
settings = get_settings()

NON_VISION_PATTERNS = ("canopylabs", "whisper", "guard", "embed", "safeguard", "audio", "tts", "gpt-oss")


class ScreenCaptureTool(BaseTool):
    name = "screen_capture"
    description = "Takes a screenshot or analyzes an uploaded base64 image using Vision AI (Groq or Local Ollama)."
    risk_level = RiskLevel.LOW

    async def execute(self, output_file: str = "storage/temp_screen.png", image_data: Optional[str] = None, prompt: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            if image_data:
                clean_b64 = image_data.split(",")[-1] if "," in image_data else image_data
                analysis = await self._analyze_image_with_vision(clean_b64, user_prompt=prompt)
                return ToolResult(
                    success=True,
                    output=f"👁️ **[GÖRSEL VİZYON ANALİZİ]**\n\n{analysis}",
                    metadata={"source": "user_uploaded_image"}
                )

            target_path = (WORKSPACE_ROOT / output_file).resolve()
            target_path.parent.mkdir(parents=True, exist_ok=True)

            screenshot = ImageGrab.grab()
            screenshot.save(target_path, "PNG")

            with open(target_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode("utf-8")

            vision_analysis = await self._analyze_image_with_vision(base64_image, user_prompt=prompt)

            return ToolResult(
                success=True,
                output=f"👁️ **[EKRAN VİZYON ANALİZİ]**\n\n{vision_analysis}\n\n*(Görüntü kaydedildi: `{target_path}`)*",
                metadata={"filepath": str(target_path)}
            )
        except Exception as e:
            logger.error(f"Screen capture/vision error: {e}")
            return ToolResult(success=False, output=None, error=str(e))

    async def _analyze_image_with_vision(self, base64_image: str, user_prompt: Optional[str] = None) -> str:
        default_instruction = "Bu bir bilgisayar ekran görüntüsü veya kamera fotoğrafıdır. Görselde neler olduğunu, açık pencereleri veya nesneleri detaylı, Türkçe ve net olarak açıkla."
        final_prompt = user_prompt.strip() if user_prompt and len(user_prompt.strip()) > 2 else default_instruction

        # 1. ATTEMPT GROQ CLOUD VISION API (If vision model exists)
        if settings.GROQ_API_KEY:
            headers = {
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
            }
            vision_model = None
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    m_res = await client.get("https://api.groq.com/openai/v1/models", headers=headers)
                    if m_res.status_code == 200:
                        available = [m.get("id", "") for m in m_res.json().get("data", [])]
                        v_matches = [m for m in available if any(v_kw in m.lower() for v_kw in ["vision", "llava", "multimodal"])]
                        if v_matches:
                            vision_model = v_matches[0]
            except Exception as e:
                logger.warning(f"Groq vision model discovery error: {e}")

            if vision_model:
                url = "https://api.groq.com/openai/v1/chat/completions"
                payload = {
                    "model": vision_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": final_prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                            ]
                        }
                    ],
                    "max_tokens": 600
                }
                try:
                    async with httpx.AsyncClient(timeout=25.0) as client:
                        res = await client.post(url, json=payload, headers=headers)
                        if res.status_code == 200:
                            return res.json()["choices"][0]["message"]["content"]
                except Exception as ex:
                    logger.warning(f"Groq Vision API call failed: {ex}")

        # 2. ATTEMPT LOCAL OLLAMA VISION (llava, moondream, llama3.2-vision)
        ollama_url = f"{settings.OLLAMA_BASE_URL}/api/generate"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                tags_res = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
                if tags_res.status_code == 200:
                    models = [m.get("name", "") for m in tags_res.json().get("models", [])]
                    local_v = [m for m in models if any(v_kw in m.lower() for v_kw in ["llava", "moondream", "vision"])]
                    
                    if local_v:
                        target_local_model = local_v[0]
                        payload = {
                            "model": target_local_model,
                            "prompt": final_prompt,
                            "images": [base64_image],
                            "stream": False
                        }
                        logger.info(f"Analyzing image locally via Ollama Vision model: {target_local_model}")
                        async with httpx.AsyncClient(timeout=30.0) as v_client:
                            v_res = await v_client.post(ollama_url, json=payload)
                            if v_res.status_code == 200:
                                return v_res.json().get("response", "Görsel analiz edildi.")
        except Exception as o_err:
            logger.warning(f"Local Ollama Vision failed: {o_err}")

        return (
            "📸 **[GÖRÜNTÜ KAYDEDİLDİ]**: Fotoğraf/Ekran görüntüsü başarıyla alındı. "
            "Ancak görseli analiz edebilmek için yerel bir Görme Modeli (Vision Model) gereklidir.\n\n"
            "👉 **Tek Komutla Yerel Modeli Yükleyin:** Terminalde `ollama pull moondream` veya `ollama pull llava` komutunu çalıştırarak %100 çevrimdışı görsel analizi aktifleştirebilirsiniz."
        )
