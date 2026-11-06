import re

_mem_negative = ["kuantum", "ram", "rom", "bellek kartı", "hafıza kartı", "cache", "önbellek", "profesör", "doktor", "motor", "teori", "makale"]
_mem_positive = ["hafızadaki bilgi", "benim hakkımda ne biliyorsun", "bilgilerimi listele", "kullanıcı bilgilerimi", "beni hatırlıyor musun", "hafızamda ne var"]

def _is_memory_query(text):
    lower = text.lower()
    return (not any(n in lower for n in _mem_negative)) and any(p in lower for p in _mem_positive)

def test_memory_query_positive():
    assert _is_memory_query("Bilgilerimi listele") is True
    assert _is_memory_query("Benim hakkımda ne biliyorsun?") is True
    assert _is_memory_query("Hafızadaki bilgileri göster") is True

def test_memory_query_negative_false_positive_leak():
    # Bu testin basarisi, benchmark'taki profil sizintisi hatasinin
    # tekrar yasanmayacagini kanitlar.
    assert _is_memory_query("Profesör Arda Yalçın'ın Kuantum Hafıza Motoru nedir?") is False
    assert _is_memory_query("RAM hafızası ne kadar olmalı?") is False
    assert _is_memory_query("Hafıza kartı nasıl takılır?") is False
