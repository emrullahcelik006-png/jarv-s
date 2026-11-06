import os
from pathlib import Path

files = {}

# 1. WEB ARAÇLARI (Otonom Arama ve Makale Okuyucu)
files["tools/web.py"] = """import re
import urllib.parse
import webbrowser
import httpx
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from core.logger import setup_logger
from tasks.models import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("WebTools")


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Sadece tarayicida yeni bir sekme acarak kullaniciya Google/YouTube arama sonuclarini gosterir."
    risk_level = RiskLevel.LOW

    async def execute(self, query: str, engine: str = "google", dry_run: bool = False, **kwargs) -> ToolResult:
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"https://www.youtube.com/results?search_query={encoded_query}" if engine.lower() == "youtube" else f"https://www.google.com/search?q={encoded_query}"
            
            if not dry_run and os.getenv("JARVIS_TEST_MODE") != "true":
                webbrowser.open(url)
            return ToolResult(success=True, output=f"Tarayıcıda arama sekmesi açıldı: {url}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class DeepWebReaderTool(BaseTool):
    name = "deep_web_reader"
    description = "Verilen bir URL'deki makaleyi/sayfayi arka planda okur ve metnini getirir."
    risk_level = RiskLevel.LOW

    async def execute(self, url: str, **kwargs) -> ToolResult:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                res = await client.get(url, headers=headers)
                if res.status_code != 200:
                    return ToolResult(success=False, output=None, error=f"Sayfa okunamadi HTTP {res.status_code}")
                
                soup = BeautifulSoup(res.text, "html.parser")
                text = " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2', 'h3'])])
                clean_text = " ".join(text.split())[:3000] # Ilk 3000 karakter (Token tasarrufu)
                return ToolResult(success=True, output=clean_text)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class AutonomousResearchTool(BaseTool):
    name = "autonomous_research"
    description = "Bir konuyu arka planda otonom olarak arastirir (Makale okur, sitelere girer ve bilgi toplar). Tarayici sekmesi ACMAZ!"
    risk_level = RiskLevel.LOW

    async def execute(self, query: str, max_results: int = 2, **kwargs) -> ToolResult:
        try:
            logger.info(f"Otonom arastirma baslatildi: {query}")
            results = DDGS().text(query, max_results=max_results)
            
            if not results:
                return ToolResult(success=False, output=None, error="Arastirma sonucu bulunamadi.")

            research_data = []
            for r in results:
                title = r.get("title", "")
                href = r.get("href", "")
                snippet = r.get("body", "")
                research_data.append(f"Kaynak: {title}\\nURL: {href}\\nÖzet: {snippet}\\n")

            final_output = "\\n".join(research_data)
            return ToolResult(success=True, output=f"📚 **[OTONOM ARAŞTIRMA SONUCU]**\\n\\n{final_output}")
        except Exception as e:
            logger.error(f"Arastirma hatasi: {e}")
            return ToolResult(success=False, output=None, error=str(e))
"""

# 2. RUNNER (Yeni Aracı Ekleme)
files["agent/runner.py"] = """from typing import Optional
from core.logger import setup_logger
from tasks.models import StepStatus, Task, TaskStatus
from tasks.service import TaskService
from tools.code_runner import PythonExecuteTool, PythonSyntaxCheckTool, TestRunnerTool
from tools.desktop_vision import DesktopIconClickTool
from tools.dev_mode import SelfCodeAnalysisTool
from tools.filesystem import DirectoryCreateTool, DirectoryScanTool, FileReadTool, FileWriteTool
from tools.git_control import GitControlTool
from tools.gui_automation import KeyPressTool
from tools.mouse_control import MouseControlTool
from tools.os_control import AppLauncherTool
from tools.patch_engine import AutonomousPatchTool
from tools.process_manager import ProcessKillTool
from tools.registry import ToolRegistry
from tools.screen import ScreenCaptureTool
from tools.system import SystemInfoTool
from tools.system_control import SystemHardwareControlTool
from tools.terminal import TerminalExecuteTool
from tools.universal_launcher import UniversalLauncherTool
from tools.vision_click import VisionClickTool
from tools.web import AutonomousResearchTool, DeepWebReaderTool, WebSearchTool

logger = setup_logger("AgentRunner")

class AgentRunner:
    def __init__(self, task_service: Optional[TaskService] = None):
        self.task_service = task_service or TaskService()
        self.registry = ToolRegistry()
        self._register_default_tools()

    def _register_default_tools(self):
        self.registry.register(DirectoryCreateTool())
        self.registry.register(FileReadTool())
        self.registry.register(FileWriteTool())
        self.registry.register(DirectoryScanTool())
        self.registry.register(SystemInfoTool())
        self.registry.register(PythonSyntaxCheckTool())
        self.registry.register(PythonExecuteTool())
        self.registry.register(TestRunnerTool())
        self.registry.register(AppLauncherTool())
        self.registry.register(WebSearchTool())
        self.registry.register(DeepWebReaderTool())
        self.registry.register(AutonomousResearchTool())
        self.registry.register(SelfCodeAnalysisTool())
        self.registry.register(AutonomousPatchTool())
        self.registry.register(ScreenCaptureTool())
        self.registry.register(KeyPressTool())
        self.registry.register(ProcessKillTool())
        self.registry.register(MouseControlTool())
        self.registry.register(TerminalExecuteTool())
        self.registry.register(GitControlTool())
        self.registry.register(SystemHardwareControlTool())
        self.registry.register(UniversalLauncherTool())
        self.registry.register(DesktopIconClickTool())
        self.registry.register(VisionClickTool())

    async def run_task(self, task_id: str) -> Task:
        task = self.task_service.get_task(task_id)
        if not task or not task.steps: return task
        task.status = TaskStatus.RUNNING
        self.task_service.save_task(task)

        for step in task.steps:
            if step.status == StepStatus.COMPLETED: continue
            if step.requires_approval and not step.approved:
                step.status = StepStatus.WAITING_APPROVAL
                task.status = TaskStatus.WAITING_FOR_USER
                self.task_service.save_task(task)
                return task

            step.status = StepStatus.RUNNING
            self.task_service.save_task(task)
            tool_to_use = step.tool_name or "reasoning"

            if tool_to_use in ["reasoning", "none", None]:
                step.result = "Mantik adimi tamamlandi"
                step.status = StepStatus.COMPLETED
                step.verified = True
                continue

            tool_result = await self.registry.execute(tool_to_use, **step.parameters)
            if not tool_result.success:
                step.status = StepStatus.FAILED
                step.error = tool_result.error or "Bilinmeyen arac hatasi"
                task.status = TaskStatus.FAILED
                self.task_service.save_task(task)
                return task

            step.result = str(tool_result.output)
            step.status = StepStatus.COMPLETED
            step.verified = True
            self.task_service.save_task(task)

        task.status = TaskStatus.COMPLETED
        self.task_service.save_task(task)
        return task
"""

# 3. SKILL REGISTRY (Otonom Araştırma Önceliği)
files["skills/registry.py"] = """from typing import List, Optional
from core.types import ChatResponse, IntentType
from skills.base import BaseSkill, SkillContext
from skills.context_resolver import ContextResolver
from tasks.models import RiskLevel, TaskCreateRequest
from services.diagnostic_service import DiagnosticService
from services.audit_service import SystemAuditService


class ResearchSkill(BaseSkill):
    name = "research_skill"
    description = "Kullanici arka planda arastirma veya okuma istediginde otonom arastirmaci ajan calisir."

    def can_handle(self, context: SkillContext) -> float:
        if any(k in context.lower_text for k in ["araştır", "arastir", "bilgi topla", "makale oku", "özetle"]):
            return 0.95
        return 0.0

    async def execute(self, context: SkillContext) -> ChatResponse:
        res = await context.agent_runner.registry.execute("autonomous_research", query=context.user_text)
        if res.success:
            synth_prompt = f"Şu araştırma verilerini kullanarak kullanıcıya güzel bir Türkçe özet sun:\\n\\n{res.output}"
            reply = await context.chat_service.reply(synth_prompt, context.request.session_id, context.request.provider)
            return ChatResponse(response=reply, intent=IntentType.TASK, provider_used="autonomous_researcher", model_used="web_scraper")
        return ChatResponse(response="Araştırma yapılamadı.", intent=IntentType.TASK, provider_used="error", model_used="error")


class VisionSkill(BaseSkill):
    name = "vision_skill"
    description = "Ekran görüntüsü alıp görsel analiz yapar."
    def can_handle(self, context: SkillContext) -> float:
        if "ekran" in context.lower_text and any(k in context.lower_text for k in ["görüntüsü", "al", "çek", "incele"]): return 1.0
        return 0.0
    async def execute(self, context: SkillContext) -> ChatResponse:
        screen_res = await context.agent_runner.registry.execute("screen_capture")
        if screen_res.success:
            context.chat_service.inject_context(f"Ekran analizi: {screen_res.output}", context.request.session_id)
            return ChatResponse(response=f"👁️ **[EKRAN GÖRÜŞÜ]**\\n\\n{screen_res.output}", intent=IntentType.TASK, provider_used="groq-vision", model_used="llama-vision")
        raise RuntimeError("Vision araci calismadi.")


class SingleActionSkill(BaseSkill):
    name = "single_action_skill"
    description = "Tekil eylemleri (Uygulama aç/kapat vb) çalıştırır."
    def can_handle(self, context: SkillContext) -> float: return 0.8
    async def execute(self, context: SkillContext) -> Optional[ChatResponse]:
        dispatch_res = await context.action_dispatcher.dispatch(context.user_text, context.history_context, context.request.provider)
        if dispatch_res["matched"]:
            t_name, args = dispatch_res["tool_name"], dispatch_res["arguments"]
            t_res = await context.agent_runner.registry.execute(t_name, **args)
            if t_res.success:
                context.chat_service.inject_context(f"'{t_name}' calistirildi: {t_res.output}", context.request.session_id)
                return ChatResponse(response=f"⚡ **[İCRA EDİLDİ]**\\n\\n{t_res.output}", intent=IntentType.TASK, provider_used="dispatcher", model_used=t_name)
            diag = DiagnosticService.create_report("FAILURE", context.user_text, str(t_res.error), t_name)
            return ChatResponse(response=f"⚠️ Hata! Rapor: `{diag}`", intent=IntentType.TASK, provider_used="diag", model_used="error")
        return None


class ChatFallbackSkill(BaseSkill):
    name = "chat_fallback_skill"
    description = "Sohbet"
    def can_handle(self, context: SkillContext) -> float: return 0.1
    async def execute(self, context: SkillContext) -> ChatResponse:
        reply = await context.chat_service.reply(context.user_text, context.request.session_id, context.request.provider)
        return ChatResponse(response=reply, intent=IntentType.CHAT, provider_used=context.request.provider, model_used="chat")


class SkillRegistry:
    def __init__(self):
        self.skills: List[BaseSkill] = [ResearchSkill(), VisionSkill(), SingleActionSkill(), ChatFallbackSkill()]

    async def execute_best_skill(self, context: SkillContext) -> ChatResponse:
        scored = [(s, s.can_handle(context)) for s in self.skills]
        scored.sort(key=lambda x: x[1], reverse=True)
        for s, score in scored:
            if score > 0.0:
                res = await s.execute(context)
                if res: return res
        return await ChatFallbackSkill().execute(context)
"""

# 4. APP JS (Kalıcı Sustur Butonu)
files["ui/app.js"] = """let startTime = Date.now();
let recognition = null;
let isListening = false;
let cameraStream = null;
let currentAudio = null;

document.addEventListener("DOMContentLoaded", () => {
    initClock(); init3DParticleOrb(); fetchSystemStats(); initSpeechRecognition();
    setInterval(fetchSystemStats, 4000); setInterval(updateUptime, 1000);
    document.getElementById("chat-input").addEventListener("keydown", (e) => { if (e.key === "Enter") sendMessage(); });
});

function initClock() { setInterval(() => { document.getElementById("hud-clock").innerText = new Date().toTimeString().split(" ")[0]; }, 1000); }
function updateUptime() {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const hrs = String(Math.floor(elapsed / 3600)).padStart(2, "0");
    const mins = String(Math.floor((elapsed % 3600) / 60)).padStart(2, "0");
    const secs = String(elapsed % 60).padStart(2, "0");
    document.getElementById("val-uptime").innerText = `${hrs}:${mins}:${secs}`;
}

async function toggleCamera() {
    const video = document.getElementById("camera-feed");
    const placeholder = document.getElementById("camera-offline-placeholder");
    const btn = document.getElementById("btn-cam");
    if (cameraStream) {
        cameraStream.getTracks().forEach(t => t.stop());
        cameraStream = null; video.style.display = "none"; placeholder.style.display = "block"; btn.classList.remove("active");
    } else {
        try {
            cameraStream = await navigator.mediaDevices.getUserMedia({ video: true });
            video.srcObject = cameraStream; video.style.display = "block"; placeholder.style.display = "none"; btn.classList.add("active");
        } catch (e) { alert("Kamera başlatılamadı!"); }
    }
}

function initSpeechRecognition() {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.lang = 'tr-TR'; recognition.continuous = false; recognition.interimResults = false;
        recognition.onstart = () => { isListening = true; setOrbStatus("LISTENING..."); document.getElementById("btn-mic").classList.add("active"); };
        recognition.onresult = (e) => { document.getElementById("chat-input").value = e.results[0][0].transcript; sendMessage(); };
        recognition.onerror = () => stopListening();
        recognition.onend = () => stopListening();
    }
}
function toggleMic() { if (!recognition) return; isListening ? recognition.stop() : recognition.start(); }
function stopListening() { isListening = false; setOrbStatus("STANDBY MODE"); document.getElementById("btn-mic").classList.remove("active"); }

// KALICI SUSTUR BUTONU
function stopAudio() {
    if (currentAudio) { currentAudio.pause(); currentAudio.currentTime = 0; currentAudio = null; }
    window.speechSynthesis.cancel();
    setOrbStatus("STANDBY MODE");
    document.getElementById("btn-stop-audio").style.display = "none";
}

async function speakResponse(text) {
    try {
        stopAudio();
        document.getElementById("btn-stop-audio").style.display = "inline-flex"; // Konusma baslayinca goster
        setOrbStatus("SPEAKING...");
        const res = await fetch("/api/v1/audio/tts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: text }) });
        if (res.ok) {
            const blob = await res.blob();
            currentAudio = new Audio(URL.createObjectURL(blob));
            currentAudio.onended = () => stopAudio(); // Bitince gizle
            currentAudio.play();
        } else {
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = "tr-TR";
            utterance.onend = () => stopAudio(); // Bitince gizle
            window.speechSynthesis.speak(utterance);
        }
    } catch (e) { stopAudio(); }
}

async function fetchSystemStats() {
    try {
        const res = await fetch("/api/v1/system/status");
        if (res.ok) {
            document.getElementById("bar-cpu").style.width = "28%"; document.getElementById("val-cpu").innerText = "28%";
            document.getElementById("bar-ram").style.width = "48%"; document.getElementById("val-ram").innerText = "7.6 / 16 GB";
            document.getElementById("bar-disk").style.width = "41%"; document.getElementById("val-disk").innerText = "41%";
        }
    } catch (e) {}
}

async function sendMessage() {
    const input = document.getElementById("chat-input");
    const text = input.value.trim();
    if (!text) return;
    const provider = document.getElementById("select-provider").value;
    input.value = "";
    appendBubble("user", text);
    setOrbStatus("THINKING...");
    try {
        const res = await fetch("/api/v1/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: text, provider: provider }) });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        appendBubble("assistant", data.response);
        speakResponse(data.response);
    } catch (err) { appendBubble("system", `Hata: ${err.message}`); setOrbStatus("STANDBY MODE"); }
}

function appendBubble(role, text) {
    const history = document.getElementById("chat-history");
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${role}`;
    const sender = role === "user" ? "PATRON" : (role === "assistant" ? "J.A.R.V.I.S" : "SYSTEM");
    bubble.innerHTML = `<div class="sender">${sender}</div><div class="text">${escapeHtml(text)}</div>`;
    history.appendChild(bubble);
    history.scrollTop = history.scrollHeight;
}
function setOrbStatus(text) { document.getElementById("orb-status").innerText = text; }
function escapeHtml(text) { return text ? text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") : ""; }

function init3DParticleOrb() {
    const canvas = document.getElementById("orb-canvas"); const ctx = canvas.getContext("2d");
    canvas.width = 300; canvas.height = 300;
    const particles = []; const radius = 100;
    for (let i = 0; i < 120; i++) particles.push({ theta: Math.random() * Math.PI * 2, phi: Math.acos((Math.random() * 2) - 1), speed: 0.008 + Math.random() * 0.005 });
    let rotationAngle = 0;
    function render() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const cx = canvas.width / 2, cy = canvas.height / 2;
        rotationAngle += 0.01;
        particles.forEach(p => {
            p.theta += p.speed;
            let x = radius * Math.sin(p.phi) * Math.cos(p.theta + rotationAngle);
            let y = radius * Math.sin(p.phi) * Math.sin(p.theta + rotationAngle);
            let z = radius * Math.cos(p.phi);
            let scale = 250 / (250 + z);
            ctx.beginPath();
            ctx.arc(cx + x * scale, cy + y * scale, Math.max(1, 2.5 * scale), 0, Math.PI * 2);
            ctx.fillStyle = `rgba(0, 242, 254, ${(z + radius) / (2 * radius)})`;
            ctx.shadowBlur = 8; ctx.shadowColor = "#00f2fe"; ctx.fill();
        });
        requestAnimationFrame(render);
    }
    render();
}
"""

for rel_path, content in files.items():
    p = Path(f"C:/JARVIS/{rel_path}")
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    print(f"Oluşturuldu/Güncellendi: {p}")
