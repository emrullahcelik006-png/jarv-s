import re
from typing import Optional, List


class ContextResolver:
    """Sohbet geçmişindeki son listeleri ve dizileri tarayarak YALNIZCA açık sıra kelimelerini ('ilk', 'ikinci', '3.', 'sonuncu') çözer."""

    NUMBER_WORDS = {
        "ilk": 0, "birinci": 0, "1.": 0,
        "ikinci": 1, "2.": 1,
        "üçüncü": 2, "ucuncu": 2, "3.": 2,
        "dördüncü": 3, "dorduncu": 3, "4.": 3,
        "beşinci": 4, "besinci": 4, "5.": 4,
        "son": -1, "sonuncu": -1, "en son": -1
    }

    @classmethod
    def resolve_reference(cls, user_text: str, history_text: str) -> Optional[str]:
        lower_user = user_text.lower().strip()

        # Match ONLY explicit order words with word boundaries (Prevents matching numbers like '12:00' or '10')
        target_idx = None
        for word, idx in cls.NUMBER_WORDS.items():
            pattern = r"\b" + re.escape(word) + r"\b"
            if re.search(pattern, lower_user):
                target_idx = idx
                break

        if target_idx is None:
            return None

        # Extract last bulleted list item from history
        lines = history_text.split("\n")
        list_items = []

        for line in reversed(lines):
            line_str = line.strip()
            if line_str.startswith("•") or line_str.startswith("-") or line_str.startswith("["):
                clean_item = re.sub(r"^[•\-\[\d\.\s]+", "", line_str).strip("`'\"[] ").strip()
                if clean_item and len(clean_item) > 2:
                    list_items.insert(0, clean_item)
            elif list_items and not line_str:
                break

        if not list_items:
            return None

        try:
            return list_items[target_idx]
        except IndexError:
            return list_items[0] if list_items else None
