import os
import re
import unicodedata
import webbrowser
import AppOpener
from core.logger import setup_logger
from tasks.models import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("OSControlTools")


def normalize_turkish_text(text: str) -> str:
    """Turkce I/i unicode karakter sorunlarini standart asciiye donusturur."""
    text = text.replace("İ", "i").replace("I", "i").replace("ı", "i")
    text = unicodedata.normalize('NFD', text)
    return ''.join(c for c in text if unicodedata.category(c) != 'Mn').lower().strip()


_VERB_WORDS = {"ac", "baslat", "calistir", "open", "launch", "start", "run", "kapat", "close", "lutfen"}


def strip_turkish_app_suffixes(text: str) -> str:
    """'Chrome'u ac', 'Opera GX baslat' gibi ifadelerden uygulama adini cikarir.

    NOT: Girdi normalize_turkish_text'ten GECMIS (ascii) metindir; bu yuzden fiiller 'ac', 'baslat'
    seklinde aranir. Eski surum 'aç'/'başlat' ariyordu, hic eslesmiyor ve uygulama adlarini
    kirpiyordu ('chrome' -> 'chrom'). Artik yalnizca kesme isaretli ekler ('steam'i') budanir.
    """
    # 1. Kesme isaretli ekleri temizle (steam'i -> steam)
    clean = re.sub(r"['\u2019][a-z]+", "", text)
    # 2. Fiilleri TAM SOZCUK olarak cikar (uygulama adlarina dokunma)
    words = [w for w in clean.split() if w not in _VERB_WORDS]
    return " ".join(words).strip()


class DynamicAppScanner:
    """Windows Başlat Menüsü ve Registry üzerindeki tüm kurulu uygulamaları tatar."""

    @staticmethod
    def scan_installed_apps() -> dict:
        apps = {}
        search_paths = [
            r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        ]
        for base_path in search_paths:
            if os.path.exists(base_path):
                for root, _, files in os.walk(base_path):
                    for file in files:
                        if file.endswith(".lnk"):
                            app_name = file.replace(".lnk", "").lower().strip()
                            full_path = os.path.join(root, file)
                            apps[app_name] = full_path
        return apps


class AppLauncherTool(BaseTool):
    name = "app_launcher"
    description = "Bilgisayardaki TUM uygulamalari AppOpener veya Dinamik Taramayla acar ve kapatir."
    risk_level = RiskLevel.MEDIUM

    def __init__(self):
        self.scanner = DynamicAppScanner()

    async def execute(self, target: str, action_type: str = "open", dry_run: bool = False, **kwargs) -> ToolResult:
        try:
            raw_target = target or kwargs.get("app") or kwargs.get("name") or kwargs.get("target_name") or ""
            normalized = normalize_turkish_text(str(raw_target))
            clean_target = strip_turkish_app_suffixes(normalized)

            if not clean_target:
                clean_target = normalized.replace("aç", "").replace("başlat", "").strip()

            if dry_run or os.getenv("JARVIS_TEST_MODE") == "true":
                return ToolResult(success=True, output=f"[TEST MODU] Uygulama eylemi simule edildi: {clean_target}")

            if action_type == "close":
                try:
                    AppOpener.close(clean_target, match_closest=True, output=False)
                    return ToolResult(success=True, output=f"🛑 **[APPOPENER]**: '{clean_target.upper()}' uygulamasi kapatildi.")
                except Exception as e:
                    return ToolResult(success=False, output=None, error=f"Uygulama kapatilamadi: {e}")

            # 1. Önce AppOpener ile Dene
            try:
                AppOpener.open(clean_target, match_closest=True, output=False)
                return ToolResult(
                    success=True,
                    output=f"🚀 **[APPOPENER]**: '{clean_target.upper()}' uygulamasi basariyla baslatildi.",
                    metadata={"target": clean_target}
                )
            except Exception:
                # 2. Bulunamazsa Dinamik Taramayla Ara
                apps = self.scanner.scan_installed_apps()
                for app_name, app_path in apps.items():
                    if clean_target in app_name or app_name in clean_target:
                        os.startfile(app_path)
                        return ToolResult(
                            success=True,
                            output=f"🚀 **[SCANNER]**: '{app_name.upper()}' uygulamasi baslatildi.",
                            metadata={"app": app_name, "path": app_path}
                        )
                # 3. Eski surum burada serbest metni os.startfile'a (ShellExecute) veriyordu: dosya yolu,
                # URL veya ms-*: protokolu calisabilirdi. Artik yalnizca taranan kisayollar acilir.
                return ToolResult(success=False, output=None, error=f"'{clean_target}' adinda kurulu bir uygulama bulunamadi.")

        except Exception as e:
            logger.error(f"AppLauncher hatasi: {e}")
            return ToolResult(success=False, output=None, error=str(e))
