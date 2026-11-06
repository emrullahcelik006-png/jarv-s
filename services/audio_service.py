import asyncio
import edge_tts
from pathlib import Path
from core.logger import setup_logger

logger = setup_logger("AudioService")

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False


def _offline_tts_sync(text: str, output_file_path: Path) -> bool:
    """Çevrimdışı pyttsx3 ses sentezleyicisi (Ağ/DNS kesintilerinde çalışır)."""
    if not PYTTSX3_AVAILABLE:
        return False
    try:
        import pythoncom
    except ImportError:
        pythoncom = None
    if pythoncom is not None:
        pythoncom.CoInitialize()
    engine = None
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 165)
        engine.save_to_file(text, str(output_file_path))
        engine.runAndWait()
        return True
    except Exception as ex:
        logger.error(f"pyttsx3 offline tts error: {ex}")
        return False
    finally:
        # COM nesneleri, CoUninitialize'dan ONCE ve ayni thread'de serbest birakilmali
        import gc
        engine = None
        gc.collect()
        if pythoncom is not None:
            pythoncom.CoUninitialize()


class AudioService:
    DEFAULT_VOICE = "tr-TR-AhmetNeural"

    @classmethod
    async def text_to_speech(cls, text: str, output_file: str = "storage/temp_speech.mp3", voice: str = None) -> str:
        """Metni Türkçe insan sesine sentezleyip diske kaydedeer (Cloud + Offline Fallback)."""
        target_path = Path(output_file).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)

        selected_voice = voice or cls.DEFAULT_VOICE
        clean_text = text.replace("*", "").replace("#", "").replace("`", "").replace("⚡", "").replace("🚀", "")

        # 1. Cloud TTS (Edge TTS)
        try:
            communicate = edge_tts.Communicate(clean_text, selected_voice)
            await communicate.save(str(target_path))
            logger.info(f"TTS Ses (Cloud) dosyaya yazıldı: {target_path}")
            return str(target_path)
        except Exception as e:
            logger.warning(f"Edge TTS cloud error ({e}), switching to offline pyttsx3 fallback...")

        # 2. Offline Fallback (pyttsx3)
        ok = await asyncio.to_thread(_offline_tts_sync, clean_text, target_path)
        if ok and target_path.exists():
            logger.info(f"TTS Ses (Offline pyttsx3) dosyaya yazıldı: {target_path}")
            return str(target_path)

        raise RuntimeError(f"Ses sentezleme hem online hem offline modda başarısız oldu.")

    @classmethod
    async def text_to_speech_bytes(cls, text: str, voice: str = None) -> bytes:
        selected_voice = voice or cls.DEFAULT_VOICE
        clean_text = text.replace("*", "").replace("#", "").replace("`", "").replace("⚡", "").replace("🚀", "")

        try:
            communicate = edge_tts.Communicate(clean_text, selected_voice)
            audio_bytes = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes.extend(chunk["data"])

            logger.info(f"TTS In-Memory Ses Sentezlendi ({len(audio_bytes)} bytes)")
            return bytes(audio_bytes)
        except Exception as e:
            logger.error(f"TTS bellek sentezleme hatasi: {e}")
            return b""
