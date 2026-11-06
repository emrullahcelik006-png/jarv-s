import json
import re
import time
import asyncio
import webbrowser
from urllib.parse import quote_plus
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from core.logger import setup_logger
from core.types import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("PCControlTools")

NOTCH = 120
SATIR_DELTA = NOTCH // 3
PIKSEL_DELTA = 1.2
ADIM_BOYUTU = 5 * NOTCH
ADIM_BEKLEME = 0.03
MAX_KAYDIRMA = 500 * SATIR_DELTA
MAX_BEKLEME = 30

SITELER = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "instagram": "https://www.instagram.com",
}
ARAMA_URL = {
    "google": "https://www.google.com/search?q=",
    "youtube": "https://www.youtube.com/results?search_query=",
}
YON_ANAHTAR = {"asagi": "down", "yukari": "up", "sol": "left", "sag": "right"}
IZINLI = {"kaydir", "uca_git", "tikla", "basili_tut", "tus_basili_tut", "tus_bas", "fare_git", "ara", "bul", "ac"}
IZINLI_TUSLAR = {"up", "down", "left", "right", "pageup", "pagedown", "home", "end", "enter", "esc", "space", "tab"}

JS_BUL = """
const q = arguments[0].toLocaleLowerCase('tr');
const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
while (w.nextNode()) {
  if (w.currentNode.nodeValue.toLocaleLowerCase('tr').includes(q)) {
    w.currentNode.parentElement.scrollIntoView({block: 'center'});
    return true;
  }
}
return false;
"""

_TR = str.maketrans("çğıöşüÇĞİÖŞÜI", "cgiosucgiosuI")
_BIRLER = {"sifir": 0, "bir": 1, "iki": 2, "uc": 3, "dort": 4, "bes": 5, "alti": 6, "yedi": 7, "sekiz": 8, "dokuz": 9}
_ONLAR = {"on": 10, "yirmi": 20, "otuz": 30, "kirk": 40, "elli": 50, "altmis": 60, "yetmis": 70, "seksen": 80, "doksan": 90}


def _katla(metin: str) -> str:
    return metin.replace("\u2019", "'").translate(_TR).lower()


def _sayilari_rakama_cevir(n: str) -> str:
    cikti, buf = [], []
    def bosalt():
        if buf:
            t = 0
            for k in buf:
                t = max(t, 1) * 100 if k == "yuz" else t + _ONLAR.get(k, _BIRLER.get(k, 0))
            cikti.append(str(t))
            buf.clear()
    for k in n.split():
        if k in _ONLAR or k in _BIRLER or k == "yuz":
            buf.append(k)
        else:
            bosalt()
            cikti.append(k)
    bosalt()
    return " ".join(cikti)


def _parcala(metin: str) -> List[tuple]:
    n = _katla(metin)
    ham, bas = [], 0
    for m in re.finditer(r"\s*(?:,|\b(?:ve\s+)?(?:sonra|ardindan)\b)\s*", n):
        ham.append((metin[bas:m.start()], n[bas:m.start()]))
        bas = m.end()
    ham.append((metin[bas:], n[bas:]))
    sonuc = []
    for o, x in ham:
        sol = len(x) - len(x.lstrip(" .!?"))
        sag = len(x.rstrip(" .!?"))
        if sag > sol:
            sonuc.append((o[sol:sag], x[sol:sag]))
    return sonuc


def _eyleme_cevir(o: str, n: str) -> Optional[dict]:
    n2 = _sayilari_rakama_cevir(n)

    # 1. Sayfada metin bul (Selenium DOM)
    m = re.match(r"^sayfa\w*\s+(?:icinde\s+)?(?P<q>.+?)\s+(?:bul|ara|goster)$", n)
    if m:
        return {"eylem": "bul", "metin": o[m.start("q"):m.end("q")]}

    # 2. Web'de ara
    m = re.match(r"^(?:(?P<site>google|youtube)\S*\s+)?(?P<q>.+?)\s+ara(?:ma\s+yap)?$", n)
    if m:
        return {"eylem": "ara", "site": m.group("site") or "google", "sorgu": o[m.start("q"):m.end("q")]}

    # 3. Basılı tut
    if "basili" in n:
        s = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:saniye|sn)\b", n2)
        sure = float(s.group(1).replace(",", ".")) if s else 1.0
        y = re.search(r"\b(asagi|yukari|sol|sag)\w*", n)
        if y and re.search(r"\bok\b", n):
            return {"eylem": "tus_basili_tut", "tus": YON_ANAHTAR[y.group(1)], "sure": sure}
        return {"eylem": "basili_tut", "sure": sure, "dugme": "sag" if re.search(r"\bsag\b", n) else "sol"}

    # 4. Tıkla / Dokun
    if re.search(r"\b(?:tikla|dokun)\w*", n):
        return {"eylem": "tikla", "dugme": "sag" if re.search(r"\bsag\b", n) else "sol", "cift": "cift" in n}

    # 5. En alta / En üste
    if re.search(r"\ben\s+(?:alt|ust)", n) or re.search(r"\bsayfa\w*\s+(?:son|bas)\w*", n):
        asagi = re.search(r"\b(?:en\s+alt|sayfa\w*\s+son)", n)
        return {"eylem": "uca_git", "yon": "asagi" if asagi else "yukari"}

    # 6. Fareyi koordinata götür
    m = re.search(r"\bfare\w*\s+(\d+)\s*[,x ]\s*(\d+)", n)
    if m:
        return {"eylem": "fare_git", "x": int(m.group(1)), "y": int(m.group(2))}

    # 7. Site / Adres aç
    m = re.match(r"^(?P<u>[\w.:/\-]+)(?:'\w+)?\s+(?:ac|git|adresine\s+git)$", n)
    if m:
        u = m.group("u")
        if u in SITELER:
            return {"eylem": "ac", "url": SITELER[u]}
        if "." in u:
            return {"eylem": "ac", "url": o[m.start("u"):m.end("u")]}

    # 8. Kaydır
    y = re.search(r"\b(asagi|yukari|sol|sag)\w*", n)
    if y:
        b = re.search(r"\b(satir|sayfa|piksel|px)\w*", n2)
        birim = "satir"
        if b:
            birim = "piksel" if b.group(1) == "px" else b.group(1)
        s = re.search(r"\d+(?:[.,]\d+)?", n2)
        miktar = float(s.group().replace(",", ".")) if s else (1 if birim == "sayfa" else 5)
        return {"eylem": "kaydir", "yon": y.group(1), "miktar": miktar, "birim": birim}

    return None


class PCControlTool(BaseTool):
    name = "pc_control"
    description = "Executes deterministic PC control commands (scrolling, clicking, key hold, mouse move, Selenium DOM text finding, web search, URL open)."
    risk_level = RiskLevel.MEDIUM

    def __init__(self, tarayici_port: Optional[int] = None):
        super().__init__()
        self.tarayici_port = tarayici_port
        self.driver = None

    def _connect_selenium_sync(self, port: int = 9222) -> bool:
        try:
            from selenium import webdriver
            sec = webdriver.ChromeOptions()
            sec.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
            self.driver = webdriver.Chrome(options=sec)
            return True
        except Exception as e:
            logger.warning(f"Selenium connection to port {port} failed: {e}")
            self.driver = None
            return False

    def _execute_command_sync(self, command_text: str) -> str:
        import pyautogui
        pyautogui.FAILSAFE = True

        if self.tarayici_port and not self.driver:
            self._connect_selenium_sync(self.tarayici_port)

        actions = []
        for o, n in _parcala(command_text):
            e = _eyleme_cevir(o, n)
            if e:
                actions.append(e)

        if not actions:
            return f"Komut ayrıştırılamadı: '{command_text}'"

        results = []
        for e in actions:
            act_type = e.get("eylem")

            if act_type == "fare_git":
                x, y = int(e.get("x", 500)), int(e.get("y", 500))
                pyautogui.moveTo(x, y, duration=0.2)
                results.append(f"Fare {x}x{y} konumuna taşındı")

            elif act_type == "kaydir":
                yon = e.get("yon", "asagi")
                miktar = float(e.get("miktar", 5))
                isaret = -1 if yon in ("asagi", "sol") else 1
                if yon in ("asagi", "yukari"):
                    pyautogui.scroll(int(isaret * miktar * 120))
                else:
                    try:
                        pyautogui.hscroll(int(isaret * miktar * 120))
                    except Exception:
                        pyautogui.keyDown('shift')
                        pyautogui.scroll(int(isaret * miktar * 120))
                        pyautogui.keyUp('shift')
                results.append(f"Kaydırıldı: {miktar:g} {yon}")

            elif act_type == "tikla":
                dugme = "right" if e.get("dugme") == "sag" else "left"
                cift = bool(e.get("cift", False))
                pyautogui.click(button=dugme, clicks=2 if cift else 1)
                results.append(f"Tıklandı ({dugme})")

            elif act_type == "basili_tut":
                sure = float(e.get("sure", 1.0))
                dugme = "right" if e.get("dugme") == "sag" else "left"
                pyautogui.mouseDown(button=dugme)
                time.sleep(sure)
                pyautogui.mouseUp(button=dugme)
                results.append(f"Basılı tutuldu ({sure:g}s)")

            elif act_type == "tus_basili_tut":
                tus = e.get("tus")
                sure = float(e.get("sure", 1.0))
                if tus in IZINLI_TUSLAR:
                    pyautogui.keyDown(tus)
                    time.sleep(sure)
                    pyautogui.keyUp(tus)
                    results.append(f"Tuş '{tus}' {sure:g}s basılı tutuldu")

            elif act_type == "tus_bas":
                tus = e.get("tus")
                if tus in IZINLI_TUSLAR:
                    pyautogui.press(tus)
                    results.append(f"Tuşa basıldı ({tus})")

            elif act_type == "uca_git":
                yon = e.get("yon", "asagi")
                isaret = -1 if yon == "asagi" else 1
                pyautogui.scroll(int(isaret * 500 * 40))
                results.append(f"En {'alta' if yon == 'asagi' else 'üste'} gidildi")

            elif act_type == "ara":
                site = e.get("site", "google")
                sorgu = e.get("sorgu", "")
                if sorgu:
                    target_url = ARAMA_URL.get(site, ARAMA_URL["google"]) + quote_plus(sorgu)
                    if self.driver:
                        self.driver.get(target_url)
                    else:
                        webbrowser.open(target_url)
                    results.append(f"Arama yapıldı ({site}): '{sorgu}'")

            elif act_type == "ac":
                target_url = e.get("url", "")
                if target_url:
                    if not re.match(r"^https?://", target_url, re.I):
                        target_url = "https://" + target_url
                    if self.driver:
                        self.driver.get(target_url)
                    else:
                        webbrowser.open(target_url)
                    results.append(f"Adres açıldı: {target_url}")

            elif act_type == "bul":
                metin = e.get("metin", "")
                if self.driver:
                    ok = self.driver.execute_script(JS_BUL, metin)
                    results.append(f"Metin '{metin}': {'Bulundu ve Odaklandı' if ok else 'Bulunamadı'}")
                else:
                    results.append("Bul eylemi için Selenium bağlantısı gerekiyor.")

        return " | ".join(results) if results else "Eylem tamamlandı."

    async def execute(self, command: str = "", port: Optional[int] = None, **kwargs) -> ToolResult:
        try:
            cmd_text = str(command).strip()
            if not cmd_text:
                return ToolResult(success=False, output=None, error="Command text required.")

            if port:
                self.tarayici_port = int(port)

            res_text = await asyncio.to_thread(self._execute_command_sync, cmd_text)
            return ToolResult(
                success=True,
                output=f"🖥️ **[PC KONTROLÖRLÜK İCRA EDİLDİ]**:\n\n{res_text}",
                metadata={"command": cmd_text}
            )
        except Exception as e:
            logger.error(f"PCControlTool error: {e}")
            return ToolResult(success=False, output=None, error=str(e))
