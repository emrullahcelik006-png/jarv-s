import asyncio
import ipaddress
import json
import re
import socket
import subprocess
import webbrowser
from urllib.parse import quote_plus, urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from typing import Optional, List, Dict, Any
from core.logger import setup_logger
from core.config import get_settings
from core.types import RiskLevel
from tools.base import BaseTool, ToolResult
from llm.ollama_provider import OllamaProvider
from llm.groq_provider import GroqProvider

logger = setup_logger("WebTools")
settings = get_settings()

try:
    import winreg
    WINREG_AVAILABLE = True
except ImportError:
    WINREG_AVAILABLE = False

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

NOISE_PATTERNS = [
    r"cerez|cookie|privacy\s+policy|gizlilik\s+politikasi|kullanım\s+koşulları",
    r"tum\s+haklari\s+saklidir|all\s+rights\s+reserved|copyright",
    r"giris\s+yap|uye\s+ol|subscrib|abone\s+ol|bultene\s+katil",
    r"sosyal\s+medya|takip\s+edin|paylas\b|share\s+this",
    r"reklam|advertisement|sponsor",
]


def _is_public_http_url(url: str) -> bool:
    """SSRF korumasi: yalnizca http(s) ve genel (public) IP'lere cozulen adresler.
    127.0.0.1, 192.168.x.x, 10.x.x.x, link-local ve metadata adresleri reddedilir."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        for info in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
                return False
        return True
    except Exception:
        return False


def _clean_and_extract_html_text(html_content: str) -> str:
    if not html_content or len(html_content.strip()) < 50:
        return ""

    soup = BeautifulSoup(html_content, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "iframe", "aside", "form", "svg", "button", "input"]):
        tag.decompose()

    text_blocks = []
    for element in soup.find_all(["p", "h1", "h2", "h3", "h4", "li", "span", "td", "a"]):
        t = element.get_text(strip=True)
        if len(t) > 20 and not any(re.search(pat, t, flags=re.IGNORECASE) for pat in NOISE_PATTERNS):
            if not text_blocks or text_blocks[-1] != t:
                text_blocks.append(t)

    clean_body = " ".join(text_blocks)

    if len(clean_body) < 200:
        raw_text = soup.get_text(separator=" ", strip=True)
        lines = [line.strip() for line in raw_text.splitlines() if len(line.strip()) > 20 and not any(re.search(pat, line, flags=re.IGNORECASE) for pat in NOISE_PATTERNS)]
        clean_text = " ".join(lines)
    else:
        clean_text = clean_body

    normalized = " ".join(clean_text.split())
    return normalized[:3000]


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Opens an explicit web search query or URL in the default browser tab upon user request."
    risk_level = RiskLevel.LOW

    async def execute(self, query: str = "", **kwargs) -> ToolResult:
        try:
            clean_q = str(query).strip()
            if not clean_q:
                return ToolResult(success=False, output=None, error="Arama sorgusu boş olamaz.")

            if clean_q.startswith(("http://", "https://")):
                webbrowser.open(clean_q)
                return ToolResult(success=True, output=f"🌐 **[WEB BROWSER]**: '{clean_q}' adresi varsayılan tarayıcıda açıldı.")

            search_url = f"https://www.google.com/search?q={quote_plus(clean_q)}"
            webbrowser.open(search_url)
            return ToolResult(
                success=True,
                output=f"🔍 **[WEB ARAMASI]**: '{clean_q}' sorgusu Google üzerinde aratıldı ve tarayıcıda açıldı.",
                metadata={"query": clean_q, "url": search_url}
            )
        except Exception as e:
            logger.error(f"WebSearch error: {e}")
            return ToolResult(success=False, output=None, error=str(e))


class DeepWebReaderTool(BaseTool):
    name = "deep_web_reader"
    description = "Reads and extracts clean, noise-free text content from a given web URL in the background."
    risk_level = RiskLevel.LOW

    async def execute(self, url: str = "", **kwargs) -> ToolResult:
        try:
            target_url = str(url).strip()
            if not target_url:
                return ToolResult(success=False, output=None, error="URL parametresi eksik veya belirtilmedi.")

            headers = {
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
            }

            if not await asyncio.to_thread(_is_public_http_url, target_url):
                return ToolResult(success=False, output=None, error="Güvenlik: yalnızca genel (public) http/https adresleri okunabilir.")

            # Yonlendirmeleri elle takip et: her adim da genel adrese cozulmeli (SSRF/redirect korumasi).
            async with httpx.AsyncClient(timeout=14.0, follow_redirects=False) as client:
                res = await client.get(target_url, headers=headers)
                for _ in range(4):
                    if res.status_code not in (301, 302, 303, 307, 308) or not res.headers.get("location"):
                        break
                    next_url = urljoin(str(res.url), res.headers["location"])
                    if not await asyncio.to_thread(_is_public_http_url, next_url):
                        return ToolResult(success=False, output=None, error="Güvenlik: yönlendirme genel olmayan bir adrese gidiyor.")
                    res = await client.get(next_url, headers=headers)
                if res.status_code != 200:
                    return ToolResult(success=False, output=None, error=f"Sayfa okunamadı (HTTP {res.status_code})")

                extracted_text = _clean_and_extract_html_text(res.text)

                if not extracted_text:
                    return ToolResult(
                        success=False,
                        output=None,
                        error=f"'{target_url}' adresindeki sayfa içeriği okunamadı veya boş döndü."
                    )

                return ToolResult(
                    success=True,
                    output=extracted_text,
                    metadata={"url": target_url, "length": len(extracted_text)}
                )
        except Exception as e:
            logger.error(f"DeepWebReader error: {e}")
            return ToolResult(success=False, output=None, error=str(e))


class AutonomousResearchTool(BaseTool):
    name = "autonomous_research"
    description = "Performs background research across 5 sources, deeply scrapes top pages, and synthesizes a concise AI intelligence report."
    risk_level = RiskLevel.LOW

    async def execute(self, query: str = "", **kwargs) -> ToolResult:
        try:
            clean_q = str(query).strip()
            if not clean_q:
                return ToolResult(success=False, output=None, error="Araştırma sorgusu boş olamaz.")

            logger.info(f"Autonomous multi-source research initiated for: '{clean_q}'")
            search_results = []

            # 1. LAYER 1: DDGS API Search
            try:
                try:
                    from ddgs import DDGS
                except ImportError:
                    from duckduckgo_search import DDGS

                def _fetch_ddg_sync():
                    with DDGS() as ddgs:
                        return list(ddgs.text(clean_q, max_results=5))

                raw_ddg = await asyncio.to_thread(_fetch_ddg_sync)
                for item in raw_ddg:
                    search_results.append({
                        "title": item.get("title", ""),
                        "snippet": item.get("body", ""),
                        "url": item.get("href", "")
                    })
            except Exception as ex:
                logger.warning(f"DDGS API search warning: {ex}")

            # 2. LAYER 2: Bing HTML Scraper Fallback
            if not search_results:
                try:
                    headers = {"User-Agent": USER_AGENT, "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"}
                    bing_url = f"https://www.bing.com/search?q={clean_q.replace(' ', '+')}"
                    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                        res = await client.get(bing_url, headers=headers)
                        if res.status_code == 200:
                            soup = BeautifulSoup(res.text, "html.parser")
                            for li in soup.find_all("li", class_="b_algo", limit=6):
                                h2 = li.find("h2")
                                a_tag = h2.find("a") if h2 else None
                                snippet_p = li.find("p") or li.find("div", class_="b_caption")
                                if a_tag and a_tag.get("href"):
                                    href_str = a_tag.get("href")
                                    title_str = a_tag.get_text().strip()
                                    if not any(bad in href_str.lower() for bad in ["takvim", "calendar"]):
                                        search_results.append({
                                            "title": title_str,
                                            "snippet": snippet_p.get_text().strip() if snippet_p else "Canlı Web Kaynağı.",
                                            "url": href_str
                                        })
                                        if len(search_results) >= 5:
                                            break
                except Exception as b_err:
                    logger.warning(f"Bing scraper fallback error: {b_err}")

            if not search_results:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"'{clean_q}' konusu hakkında canlı web aramalarında sonuç bulunamadı."
                )

            # 3. Deep Background Page Scraping (Scrape top 2 URLs)
            urls_to_scrape = [r["url"] for r in search_results if r.get("url") and "bing.com" not in r.get("url")][:2]
            scraped_texts = []

            reader = DeepWebReaderTool()
            for u in urls_to_scrape:
                read_res = await reader.execute(url=u)
                if read_res.success and read_res.output:
                    scraped_texts.append(f"Source ({u}):\n{read_res.output}")

            combined_raw_text = "\n\n".join(scraped_texts)

            # 4. AI SYNTHESIS WITH STRICT FORMATTING (NO TABLES, BULLET POINTS ONLY)
            ai_synthesis = ""
            if combined_raw_text:
                synth_prompt = (
                    f"Aşağıda '{clean_q}' konusu hakkında canlı web sayfalarından çekilen metinler yer almaktadır.\n"
                    f"Lütfen bu verileri inceleyip kullanıcıya TABLO KULLANMADAN, sadece sade, net ve kısa maddeler (bullet points) halinde bir özet sun.\n"
                    f"Geçmiş yıllara ait uzun tablo dökümleri OLUŞTURMA. Doğrudan sorulan sorunun öz cevabına odaklan:\n\n"
                    f"{combined_raw_text[:3000]}"
                )

                try:
                    provider = GroqProvider() if settings.GROQ_API_KEY else OllamaProvider(default_model=settings.DEFAULT_FAST_MODEL)
                    response = await provider.generate(prompt=synth_prompt, temperature=0.2)
                    ai_synthesis = response.content.strip()
                    # Sanitize unicode spaces
                    ai_synthesis = ai_synthesis.replace("\u202f", " ").replace("\u200b", " ")
                except Exception as ai_err:
                    logger.warning(f"AI Synthesis fallback: {ai_err}")

            # 5. Format Clean Final Report
            source_links = [f"• **[{r.get('title')}]({r.get('url')})**" for r in search_results[:5]]

            final_report = f"🌐 **[CANLI WEB RAPORU]** ('{clean_q}'):\n\n"

            if ai_synthesis:
                final_report += f"{ai_synthesis}\n\n---\n"

            final_report += "📌 **Arama Kaynakları:**\n" + "\n".join(source_links)

            return ToolResult(
                success=True,
                output=final_report,
                metadata={"query": clean_q, "results_count": len(search_results), "scraped_count": len(scraped_texts)}
            )

        except Exception as e:
            logger.error(f"AutonomousResearch error: {e}")
            return ToolResult(success=False, output=None, error=str(e))


class BrowserDiscoveryTool(BaseTool):
    name = "browser_discovery"
    description = "Detects installed web browsers on the system."
    risk_level = RiskLevel.LOW

    async def execute(self, **kwargs) -> ToolResult:
        browsers = []
        if WINREG_AVAILABLE:
            try:
                hkey = winreg.HKEY_LOCAL_MACHINE
                subkey = r"SOFTWARE\Clients\StartMenuInternet"
                with winreg.OpenKey(hkey, subkey) as key:
                    i = 0
                    while True:
                        try:
                            browser_name = winreg.EnumKey(key, i)
                            browsers.append(browser_name)
                            i += 1
                        except OSError:
                            break
            except Exception as e:
                logger.warning(f"Browser discovery reg error: {e}")

        if not browsers:
            browsers = ["Chrome", "Edge", "Firefox"]

        return ToolResult(
            success=True,
            output=f"🌐 **[KURULU TARAYICILAR]**: {', '.join(browsers)}",
            metadata={"browsers": browsers}
        )
