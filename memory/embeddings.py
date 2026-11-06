import math
from typing import List, Optional
import httpx
from core.config import get_settings
from core.logger import setup_logger

logger = setup_logger("EmbeddingService")
settings = get_settings()


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """İki vektör arasındaki Kosinüs Anlamsal Benzerliğini hesaplar (0.0 - 1.0)."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


class OllamaEmbeddingProvider:
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.DEFAULT_FAST_MODEL

    async def get_embedding(self, text: str) -> List[float]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text}
                )
                if res.status_code == 200:
                    data = res.json()
                    emb = data.get("embedding", [])
                    if emb:
                        return emb
        except Exception as e:
            logger.warning(f"Ollama embedding hatasi ({e}), determagist fallback vektör üretildi.")

        return self._fallback_embedding(text)

    def _fallback_embedding(self, text: str, dim: int = 64) -> List[float]:
        """Ollama veya baglanti olmamasi durumunda 100% calisan determagist vektör üretici."""
        words = text.lower().split()
        vec = [0.0] * dim
        for idx, word in enumerate(words):
            h = sum(ord(c) for c in word)
            vec[h % dim] += 1.0 / (idx + 1)
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]
