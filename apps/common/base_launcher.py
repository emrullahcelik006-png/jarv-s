import json
import os
import webbrowser
import subprocess
import AppOpener
from difflib import get_close_matches
from pathlib import Path
from typing import Optional, Dict, Any
from core.logger import setup_logger

logger = setup_logger("BaseLauncher")
from core.paths import WORKSPACE_ROOT
REGISTRY_PATH = WORKSPACE_ROOT / "apps" / "common" / "registry.json"


class BaseLauncher:
    def __init__(self, registry_file: Path = REGISTRY_PATH):
        self.registry_file = registry_file
        self.data: Dict[str, Any] = {}
        self.load_registry()

    def load_registry(self):
        if self.registry_file.exists():
            with open(self.registry_file, "r", encoding="utf-8-sig") as f:
                self.data = json.load(f).get("apps", {})

    def resolve_app_key(self, query: str) -> Optional[str]:
        clean_q = query.lower().strip()
        all_aliases = {}

        for app_key, app_info in self.data.items():
            for alias in app_info.get("aliases", []):
                all_aliases[alias.lower()] = app_key

        if clean_q in all_aliases:
            return all_aliases[clean_q]

        # CUTOFF DEĞERİ 0.75 SEVİYESİNE ÇEKİLDİ (Yanlış eşleşme koruması)
        matches = get_close_matches(clean_q, list(all_aliases.keys()), n=1, cutoff=0.75)
        if matches:
            matched_alias = matches[0]
            logger.info(f"Fuzzy match bulundu (cutoff=0.75): '{query}' -> '{matched_alias}' ({all_aliases[matched_alias]})")
            return all_aliases[matched_alias]

        return None

    def launch(self, query: str) -> Dict[str, Any]:
        self.load_registry()
        app_key = self.resolve_app_key(query)

        if not app_key or app_key not in self.data:
            return {"success": False, "message": f"Uygulama kayıtlarda bulunamadı: '{query}'"}

        app_info = self.data[app_key]
        target = app_info.get("target_path", "")
        l_type = app_info.get("launch_type", "appopener")

        try:
            if l_type == "url" or target.startswith("http://") or target.startswith("https://"):
                webbrowser.open(target)
            elif l_type == "protocol" or target.startswith("steam://") or target.startswith("ms-"):
                webbrowser.open(target)
            elif l_type == "appopener":
                AppOpener.open(target, match_closest=True, output=False)
            elif l_type in ("shortcut", "command", "file") and os.path.exists(target):
                os.startfile(target)
            else:
                try:
                    AppOpener.open(target, match_closest=True, output=False)
                except Exception:
                    os.startfile(target)

            return {
                "success": True,
                "app_name": app_info["canonical_name"],
                "target_path": target,
                "message": f"'{app_info['canonical_name'].upper()}' başarıyla başlatıldı."
            }
        except Exception as e:
            logger.error(f"Başlatma hatası ({app_key}): {e}")
            return {"success": False, "message": f"Başlatma hatası: {str(e)}"}
