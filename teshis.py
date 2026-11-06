import os, httpx
from dotenv import dotenv_values
from core.config import get_settings

k = get_settings().GROQ_API_KEY or ""
dosya = dotenv_values(".env", encoding="utf-8-sig").get("GROQ_API_KEY")
print("cwd:", os.getcwd())
print("Sistem env'de GROQ_API_KEY var mı:", "GROQ_API_KEY" in os.environ)
print("Kullanılan anahtar .env ile aynı mı:", k == dosya)
print("uzunluk:", len(k), "| baş:", k[:6], "| son:", k[-3:])
r = httpx.get("https://api.groq.com/openai/v1/models",
              headers={"Authorization": f"Bearer {k}"}, timeout=10)
print(r.status_code, r.text[:200])