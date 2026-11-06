import os
import json
import re
from pathlib import Path

USER_HOME = Path(os.path.expanduser("~")).resolve()

START_MENU_PATHS = [
    USER_HOME / r"AppData\Roaming\Microsoft\Windows\Start Menu\Programs",
    Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"),
    USER_HOME / "Desktop"
]

REGISTRY_PATH = Path("C:/JARVIS/apps/common/registry.json")


def clean_text(text: str) -> str:
    text = text.lower().replace("ı", "i").replace("ş", "s").replace("ğ", "g").replace("ç", "c").replace("ö", "o").replace("ü", "u")
    return re.sub(r"[^a-z0-9\s]", "", text).strip()


def run_deep_scan():
    print("🔍 Ekran görüntülerindeki Başlat Menüsü ve Alt Klasörler Taranıyor...")
    
    # Mevcut registry'i oku
    data = {"apps": {}}
    if REGISTRY_PATH.exists():
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except Exception:
            pass

    apps = data.get("apps", {})
    count = 0

    for base_path in START_MENU_PATHS:
        if not base_path.exists():
            continue

        for root, dirs, files in os.walk(base_path):
            for file in files:
                if file.endswith(".lnk") or file.endswith(".exe"):
                    full_path = str(Path(root) / file)
                    file_stem = Path(file).stem
                    parent_folder = Path(root).name

                    canonical = file_stem.lower().strip()
                    
                    # Aliases Varyasyonları (Örn: "WinRAR", "winrar", "winrar klasörü")
                    aliases = set()
                    aliases.add(canonical)
                    aliases.add(clean_text(file_stem))
                    
                    # Eğer alt klasördeyse (Örn: "Windows Sistemi -> Denetim Masası")
                    if parent_folder and parent_folder.lower() not in ("programs", "desktop"):
                        aliases.add(parent_folder.lower().strip())
                        aliases.add(clean_text(parent_folder))
                        aliases.add(f"{parent_folder.lower()} {file_stem.lower()}")

                    # Kısayola özel takma ad eklemeleri
                    if "denetim masası" in canonical:
                        aliases.update(["denetim masasi", "control panel", "denetim masası aç"])
                    elif "komut istemi" in canonical:
                        aliases.update(["cmd", "komut istemi", "komut satiri"])
                    elif "winrar" in canonical:
                        aliases.update(["rar", "winrar", "zip"])
                    elif "fc 26" in canonical:
                        aliases.update(["fifa", "fc26", "ea fc 26"])

                    apps[canonical] = {
                        "canonical_name": canonical,
                        "aliases": list(aliases),
                        "target_path": full_path,
                        "launch_type": "shortcut",
                        "adapter_module": None
                    }
                    count += 1

    data["apps"] = apps
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ TESPİT BAŞARILI: Toplam {count} adet kısayol/alt klasör taranarak 'apps/common/registry.json' dosyasına öğretildi!")

if __name__ == "__main__":
    run_deep_scan()
