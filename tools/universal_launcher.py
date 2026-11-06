import os
import webbrowser
from pathlib import Path
from typing import Optional
from core.logger import setup_logger
from core.types import RiskLevel
from memory.pc_catalog import PCCatalogService
from tools.base import BaseTool, ToolResult

logger = setup_logger("UniversalLauncher")


class UniversalLauncherTool(BaseTool):
    name = "universal_launcher"
    description = "Launches local applications, games, store apps, or web URLs safely."
    risk_level = RiskLevel.LOW

    async def execute(self, target: str = "", **kwargs) -> ToolResult:
        try:
            clean_target = str(target).strip()
            if not clean_target:
                return ToolResult(success=False, output=None, error="Target name cannot be empty.")

            catalog = PCCatalogService()
            item = catalog.search_item(clean_target)

            if not item or not item.get("path"):
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Application '{clean_target}' was not found on your computer."
                )

            target_path = item["path"]
            item_type = item.get("item_type", "app")

            # 1. URL / Domain Launch
            if item_type == "url" or target_path.startswith(("http://", "https://", "steam://")):
                webbrowser.open(target_path)
                return ToolResult(
                    success=True,
                    output=f"🌐 **[WEB APPLICATION]**: Opened '{clean_target.upper()}' in default browser (`{target_path}`).",
                    metadata={"name": clean_target, "url": target_path}
                )

            # 2. Local Executable / Store App Launch
            if not target_path.startswith("http") and not os.path.exists(target_path):
                try:
                    os.startfile(f"shell:AppsFolder\\{target_path}")
                    return ToolResult(
                        success=True,
                        output=f"🚀 **[STORE APP LAUNCHED]**: '{item['name'].upper()}' initialized.",
                        metadata={"name": item["name"], "appid": target_path}
                    )
                except Exception:
                    return ToolResult(
                        success=False,
                        output=None,
                        error=f"Shortcut for '{item['name']}' is invalid or file missing (`{target_path}`)."
                    )

            os.startfile(target_path)
            return ToolResult(
                success=True,
                output=f"🚀 **[APPLICATION LAUNCHED]**: '{item['name'].upper()}' (`{target_path}`) initialized successfully.",
                metadata={"name": item["name"], "path": target_path}
            )

        except Exception as e:
            logger.error(f"UniversalLauncher error: {e}")
            return ToolResult(success=False, output=None, error=str(e))
