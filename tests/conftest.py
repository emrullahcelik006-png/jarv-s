import os

# API oturum token'i testlerde kapali (uretimde zorunlu). Ayar, uygulama import edilmeden ONCE verilmeli.
os.environ.setdefault("JARVIS_DISABLE_API_AUTH", "1")
os.environ.setdefault("JARVIS_TEST_MODE", "true")
