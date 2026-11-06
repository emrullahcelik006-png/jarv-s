import inspect
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, Field
from core.types import RiskLevel


class ToolResult(BaseModel):
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseTool(ABC):
    name: str
    description: str
    risk_level: RiskLevel = RiskLevel.LOW

    @staticmethod
    def coerce_int(val: Any, default: int = 0) -> int:
        """Safely coerces any input (str, float, None) into a valid integer."""
        if val is None:
            return default
        try:
            return int(float(str(val).strip()))
        except (ValueError, TypeError):
            return default

    @staticmethod
    def coerce_bool(val: Any, default: bool = False) -> bool:
        """Safely coerces any input into a valid boolean."""
        if val is None:
            return default
        if isinstance(val, bool):
            return val
        str_v = str(val).lower().strip()
        if str_v in ("true", "1", "yes", "evet", "on", "active"):
            return True
        if str_v in ("false", "0", "no", "hayır", "off", "inactive"):
            return False
        return default

    @staticmethod
    def coerce_str(val: Any, default: str = "") -> str:
        """Safely coerces any input into a clean stripped string."""
        if val is None:
            return default
        return str(val).strip()

    def validate_and_clean_args(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """LLM'den gelen parametre isimlerini aracın imzasını (signature) inceleyerek akıllıca eşleştirir."""
        if not kwargs:
            return {}

        cleaned = dict(kwargs)

        try:
            sig = inspect.signature(self.execute)
            expected_params = sig.parameters
        except Exception:
            expected_params = {}

        alias_groups = [
            (("file_path", "filepath", "path", "filename", "file", "target_file"), "file_path"),
            (("dir_path", "dir", "directory", "folder", "folder_path", "target_dir"), "dir_path"),
            (("target_name", "target", "app", "app_name", "application", "name"), "target_name"),
            (("command", "cmd", "action", "script", "instruction"), "command"),
            (("content", "text", "text_content", "body", "data"), "content"),
            (("query", "search_query", "text", "q"), "query"),
            (("url", "link", "website"), "url"),
            (("value", "amount", "level"), "value"),
        ]

        for param_name in expected_params:
            if param_name in ("self", "kwargs"):
                continue

            if param_name in kwargs and kwargs[param_name] is not None:
                continue

            for aliases, canonical in alias_groups:
                if param_name in aliases or param_name == canonical:
                    for alias in aliases:
                        if alias in kwargs and kwargs[alias] is not None:
                            cleaned[param_name] = kwargs[alias]
                            break
                    if param_name in cleaned:
                        break

        if "value" in cleaned and cleaned["value"] is not None:
            cleaned["value"] = self.coerce_int(cleaned["value"], default=0)

        return cleaned

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        pass
