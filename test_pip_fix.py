from agent.dispatcher import _detect_pip_intent

def test_pip_positive():
    assert _detect_pip_intent("numpy kütüphanesini kur") == (True, "numpy")
    assert _detect_pip_intent("pip install flask") == (True, "flask")
    assert _detect_pip_intent("requests paketini yükle") == (True, "requests")

def test_pip_negative():
    assert _detect_pip_intent("Bozkurt sembolü ne demek?")[0] is False
    assert _detect_pip_intent("Türk mitolojisinde kurt neden önemli?")[0] is False
    assert _detect_pip_intent("Kurgu romanları hakkında bilgi ver")[0] is False
    assert _detect_pip_intent("Kural dışı davranış ne demek?")[0] is False
    assert _detect_pip_intent("Okul hayatım nasıldı?")[0] is False
    assert _detect_pip_intent("Kurban bayramı ne zaman?")[0] is False
