import json
import re
from typing import Any, Dict, List, Union


def parse_json_safely(raw_text: str) -> Dict[str, Any]:
    """Extracts and parses JSON object or array safely from raw LLM output text."""
    if not raw_text or not isinstance(raw_text, str):
        return {}

    clean_text = raw_text.strip()

    try:
        parsed = json.loads(clean_text)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"items": parsed}
    except Exception:
        pass

    match = re.search(r"(\{.*\}|\[.*\])", clean_text, re.DOTALL)
    if match:
        json_str = match.group(0)
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                return {"items": parsed}
        except Exception:
            pass

    return {}
