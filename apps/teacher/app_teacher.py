import json
from pathlib import Path
from typing import List, Optional
from core.logger import setup_logger

logger = setup_logger("AppTeacher")
from core.paths import WORKSPACE_ROOT
REGISTRY_PATH = WORKSPACE_ROOT / "apps" / "common" / "registry.json"


class AppTeacher:
    """JARVIS'e yeni uygulamaları, kısayolları ve takma adlarını öğreten servis."""

    def __init__(self, registry_file: Path = REGISTRY_PATH):
        self.registry_file = registry_file

    def teach_app(
        self,
        canonical_name: str,
        target_path: str,
        aliases: Optional[List[str]] = None,
        launch_type: str = "shortcut",
        adapter_module: Optional[str] = None
    ) -> bool:
        c_name = canonical_name.lower().strip()
        alias_list = list(set([c_name] + [a.lower().strip() for a in (aliases or [])]))

        data = {"apps": {}}
        if self.registry_file.exists():
            with open(self.registry_file, "r", encoding="utf-8") as f:
                data = json.load(f)

        data["apps"][c_name] = {
            "canonical_name": c_name,
            "aliases": alias_list,
            "target_path": target_path,
            "launch_type": launch_type,
            "adapter_module": adapter_module
        }

        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Öğretme Başarılı: '{c_name}' -> {target_path}")
        return True
