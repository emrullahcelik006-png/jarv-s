import os
import shutil
from pathlib import Path
from core.logger import setup_logger
from core.types import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("FilesystemTools")
USER_HOME = Path(os.path.expanduser("~")).resolve()
from core.paths import WORKSPACE_ROOT

PROTECTED_PATHS = [
    Path("C:/Windows").resolve(),
    Path("C:/Program Files").resolve(),
    Path("C:/Program Files (x86)").resolve(),
]


def _resolve_global_path(path_str: str) -> Path:
    clean = path_str.strip().strip("\"'").replace("\\", "/")
    lower = clean.lower()

    if lower in ("desktop", "masaüstü", "masaustu"):
        return USER_HOME / "Desktop"
    if lower.startswith("desktop/") or lower.startswith("masaüstü/") or lower.startswith("masaustu/"):
        sub_path = clean.split("/", 1)[1]
        return USER_HOME / "Desktop" / sub_path

    if lower in ("downloads", "indirilenler"):
        return USER_HOME / "Downloads"
    if lower.startswith("downloads/") or lower.startswith("indirilenler/"):
        sub_path = clean.split("/", 1)[1]
        return USER_HOME / "Downloads" / sub_path

    p = Path(path_str).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    return p.resolve()


_resolve_safe_path = _resolve_global_path


def _check_write_allowed(target_path: Path) -> None:
    r"""Korumalı sistem dizinlerine (C:\Windows vb.) izinsiz yazmayı engeller."""
    resolved = target_path.resolve()
    for protected in PROTECTED_PATHS:
        if str(resolved).lower().startswith(str(protected).lower()):
            raise PermissionError(f"Korumalı sistem dizinine yazma engellendi: {resolved}")


class DirectoryCreateTool(BaseTool):
    name = "directory_create"
    description = "Masaustunde veya sistemde klasor olusturur."
    risk_level = RiskLevel.LOW

    async def execute(self, dir_path: str = "desktop", **kwargs) -> ToolResult:
        try:
            target = _resolve_global_path(dir_path)
            _check_write_allowed(target)
            target.mkdir(parents=True, exist_ok=True)
            return ToolResult(success=True, output=f"Klasor olusturuldu: {target}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class FileReadTool(BaseTool):
    name = "file_read"
    description = "Dosya okur."
    risk_level = RiskLevel.LOW

    async def execute(self, file_path: str = None, **kwargs) -> ToolResult:
        try:
            path_val = file_path or kwargs.get("path") or kwargs.get("file") or kwargs.get("target") or "desktop"
            target = _resolve_global_path(str(path_val))
            if not target.exists() or not target.is_file():
                return ToolResult(success=False, output=None, error=f"Dosya yok: {target}")
            with open(target, "r", encoding="utf-8-sig", errors="replace") as f:
                lines = f.readlines()[:500]
            return ToolResult(success=True, output="".join(lines))
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class FileWriteTool(BaseTool):
    name = "file_write"
    description = "Dosya yazar."
    risk_level = RiskLevel.MEDIUM

    async def execute(self, file_path: str = None, content: str = None, **kwargs) -> ToolResult:
        try:
            path_val = file_path or kwargs.get("path") or kwargs.get("file") or kwargs.get("target") or "storage/output.txt"
            content_val = content if content is not None else (kwargs.get("text") or kwargs.get("data") or kwargs.get("body") or kwargs.get("query") or "")

            target = _resolve_global_path(str(path_val))
            _check_write_allowed(target)
            target.parent.mkdir(parents=True, exist_ok=True)

            with open(target, "w", encoding="utf-8") as f:
                f.write(str(content_val))

            return ToolResult(success=True, output=f"Dosya basariyla yazildi: {target}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class DirectoryScanTool(BaseTool):
    name = "directory_scan"
    description = "Klasor icerigini listeler."
    risk_level = RiskLevel.LOW

    async def execute(self, dir_path: str = "desktop", max_depth: int = 1, **kwargs) -> ToolResult:
        try:
            paths = [p.strip() for p in dir_path.split(",") if p.strip()]
            all_items = []

            for p_str in paths:
                target = _resolve_global_path(p_str)
                if not target.exists() or not target.is_dir():
                    continue

                for root, dirs, files in os.walk(target):
                    dirs[:] = [d for d in dirs if d not in (".git", ".venv", "__pycache__", "node_modules", "AppData")]
                    rel = Path(root).relative_to(target)
                    if len(rel.parts) > max_depth:
                        dirs.clear()
                        continue
                    for name in files[:20]:
                        all_items.append(f"[{target.name.upper()}] " + (str(rel / name) if str(rel) != "." else name))

            if not all_items:
                return ToolResult(success=False, output=None, error=f"Klasor(ler) bulunamadi: {dir_path}")

            return ToolResult(success=True, output=all_items, metadata={"count": len(all_items)})
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
