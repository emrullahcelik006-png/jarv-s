from functools import lru_cache
from typing import Optional
import sys
from pydantic_settings import BaseSettings, SettingsConfigDict
from core.paths import WORKSPACE_ROOT

# Milestone 15: PyInstaller/cx_Freeze vb. ile paketlenen binary'de True olur.
IS_COMPILED: bool = bool(getattr(sys, "frozen", False))


class Settings(BaseSettings):
    JARVIS_ENV: str = "development"
    JARVIS_LOG_LEVEL: str = "INFO"
    JARVIS_CITY: str = "Istanbul"

    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000

    # Ollama
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    DEFAULT_CHAT_MODEL: str = "qwen2.5-coder:7b"
    DEFAULT_FAST_MODEL: str = "qwen2.5:1.5b"
    OLLAMA_TIMEOUT_SECONDS: int = 60

    # Groq Settings
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    GROQ_VISION_MODEL: str = "llama-3.2-11b-vision-preview"
    GROQ_RESEARCH_MODEL: str = "openai/gpt-oss-20b"
    GROQ_RESEARCH_PROVIDER: str = "browser_search"

    # Fish Audio
    FISH_AUDIO_API_KEY: Optional[str] = None

    # Milestone 15: GOD MODE (Developer Override)
    # Son kullanici surumunde .env ile degistirilebilir; varsayilan gelistirme sifresi.
    GOD_MODE_CODE: str = "1001"
    # Derlenmis (exe) surumde kaynak kod yama / self-code-analysis kapali tutulmali
    ALLOW_SELF_MODIFICATION: bool = not IS_COMPILED

    # --- Guvenlik / davranis ayarlari (hepsi .env ile degistirilebilir) ---
    # Eksik Python paketlerinin otomatik pip kurulumu: tedarik zinciri riski -> varsayilan KAPALI.
    AUTO_PIP_INSTALL: bool = False
    # Doluysa virgullu izin listesi (ornek: "requests,numpy"); bos = gecerli herhangi bir paket adi.
    AUTO_PIP_ALLOWLIST: str = ""
    # Bekleyen onay gorevlerinin gecerlilik suresi (saat). Suresi dolan gorev iptal edilir.
    TASK_APPROVAL_TTL_HOURS: int = 24
    # GOD MODE otomatik kapanma suresi (dakika).
    GOD_MODE_TTL_MINUTES: int = 60
    # RAG: eski sohbet kayitlari (model cevaplari) bilgi olarak enjekte edilsin mi? Hatali cevaplari kendine besler.
    RAG_INCLUDE_CHAT_LOG: bool = False
    # Arka plan ajani: RAM uyari esigi ve ayni uyariyi tekrar uretmeden onceki bekleme (saniye).
    RAM_WARN_PERCENT: float = 92.0
    RAM_WARN_COOLDOWN_SECONDS: int = 900
    # Yerel API oturum token'i zorunlu mu? (testlerde JARVIS_DISABLE_API_AUTH=1 ile kapatilir)
    REQUIRE_API_TOKEN: bool = True

    # .env dosyasi calisma dizininden degil, proje kokunden okunur (farkli klasorden baslatinca anahtarlar kaybolmasin).
    model_config = SettingsConfigDict(env_file=str(WORKSPACE_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
