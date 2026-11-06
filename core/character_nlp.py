import re
import unicodedata
from difflib import SequenceMatcher
from typing import List, Tuple, Optional, Dict, Any


class CharacterNLPEngine:
    """ASCII Folding and Turkish-safe character normalization engine."""

    CHAR_REPLACEMENTS = {
        'İ': 'i', 'I': 'i', 'ı': 'i', 'i': 'i',
        'Ç': 'c', 'ç': 'c',
        'Ğ': 'g', 'ğ': 'g',
        'Ö': 'o', 'ö': 'o',
        'Ş': 's', 'ş': 's',
        'Ü': 'u', 'ü': 'u',
    }

    @classmethod
    def fold_text(cls, text: str) -> str:
        """Folds Turkish and special characters to clean ASCII 'i', 'c', 'g', 'o', 's', 'u'."""
        if not text:
            return ""
        
        # 1. Direct character replacement
        clean = "".join(cls.CHAR_REPLACEMENTS.get(ch, ch) for ch in text)
        
        # 2. Unicode normalization (removes combining dots/accents)
        clean = unicodedata.normalize('NFKD', clean)
        clean = "".join(ch for ch in clean if not unicodedata.combining(ch))
        
        # 3. Clean special symbols (™, ®, ©, etc.)
        clean = re.sub(r"[™®©]", "", clean)
        
        return clean.lower().strip()

    @classmethod
    def is_url_query(cls, text: str) -> bool:
        """Detects if user query is a web domain or URL rather than a local desktop app."""
        clean = text.lower().strip()
        if clean.startswith(("http://", "https://", "www.")):
            return True
        if any(clean.endswith(ext) for ext in (".com", ".org", ".net", ".io", ".gov", ".edu", ".co")):
            return True
        return False

    @classmethod
    def calculate_char_similarity(cls, str1: str, str2: str) -> float:
        norm1 = cls.fold_text(str1)
        norm2 = cls.fold_text(str2)
        if not norm1 or not norm2:
            return 0.0
        return SequenceMatcher(None, norm1, norm2).ratio()
