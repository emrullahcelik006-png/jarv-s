"""Proje yollari icin TEK dogru kaynak.

Varsayilan: bu dosyanin iki ust klasoru (proje koku). Proje masaustunde de,
baska bir surucude de, C:\\JARVIS altinda da calisir; yol sabit degildir.
Gerekirse JARVIS_HOME ortam degiskeniyle degistirilebilir.
"""
import os
from pathlib import Path


def _resolve_root() -> Path:
    env = os.environ.get("JARVIS_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


WORKSPACE_ROOT: Path = _resolve_root()
STORAGE_DIR: Path = WORKSPACE_ROOT / "storage"
