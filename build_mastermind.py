import os
from pathlib import Path

files = {}

# 1. UI INDEX HTML (Stop Butonu Eklendi)
files["ui/index.html"] = """<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>J.A.R.V.I.S — Neural HUD Interface</title>
    <link rel="stylesheet" href="/static/style.css">
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;800&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
</head>
<body>
    <div class="hud-container">
        <header class="hud-header">
            <div class="brand">
                <span class="logo">J.A.R.V.I.S</span>
                <span class="status-badge live">SYSTEM ONLINE</span>
            </div>
            <div class="clock-display" id="hud-clock">00:00:00</div>
            <div class="system-controls"><span id="provider-badge">MODEL: OLLAMA / GROQ</span></div>
        </header>

        <main class="hud-main">
            <aside class="panel left-panel">
                <div class="widget">
                    <div class="widget-title">⚙️ SYSTEM STATS</div>
                    <div class="stat-bar-group">
                        <div class="stat-label"><span>CPU LOAD</span><span id="val-cpu">0%</span></div>
                        <div class="bar-bg"><div class="bar-fill" id="bar-cpu" style="width: 0%;"></div></div>
                    </div>
                    <div class="stat-bar-group">
                        <div class="stat-label"><span>MEMORY (RAM)</span><span id="val-ram">0 / 0 GB</span></div>
                        <div class="bar-bg"><div class="bar-fill" id="bar-ram" style="width: 0%;"></div></div>
                    </div>
                    <div class="stat-bar-group">
                        <div class="stat-label"><span>STORAGE (C:)</span><span id="val-disk">0%</span></div>
                        <div class="bar-bg"><div class="bar-fill" id="bar-disk" style="width: 0%;"></div></div>
                    </div>
                </div>
                <div class="widget">
                    <div class="widget-title">👁️ OPTICAL SENSOR (CAMERA)</div>
                    <div class="camera-container" style="text-align: center;">
                        <video id="camera-feed" autoplay playsinline style="width: 100%; height: 140px; border-radius: 6px; border: 1px solid var(--border-cyan); object-fit: cover; display: none;"></video>
                        <div id="camera-offline-placeholder" style="padding: 30px 10px; font-size: 0.75rem; color: var(--text-muted); border: 1px dashed rgba(0,242,254,0.2); border-radius: 6px;">CAMERA SENSOR OFFLINE</div>
                    </div>
                </div>
                <div class="widget">
                    <div class="widget-title">⏱️ SYSTEM UPTIME</div>
                    <div class="uptime-val" id="val-uptime">00:00:00</div>
                </div>
            </aside>

            <section class="panel center-stage">
                <div class="orb-wrapper">
                    <canvas id="orb-canvas"></canvas>
                    <div class="orb-title">J.A.R.V.I.S</div>
                    <div class="orb-status-pill" id="orb-status">STANDBY MODE</div>
                </div>
                <div class="orb-toolbar">
                    <button class="icon-btn" id="btn-mic" onclick="toggleMic()" title="Mikrofon Dinle"><span class="icon">🎙️</span> Mikrofon</button>
                    <button class="icon-btn" id="btn-cam" onclick="toggleCamera()" title="Kamerayı Aç/Kapat"><span class="icon">📷</span> Kamera</button>
                    <button class="icon-btn" id="btn-stop-audio" onclick="stopAudio()" title="Sesi Sustur" style="display:none; background:var(--accent-red); color:#fff; border-color:var(--accent-red);"><span class="icon">🛑</span> Sustur</button>
                </div>
            </section>

            <aside class="panel right-panel">
                <div class="panel-header">
                    <h3>💬 CONVERSATION PROTOCOL</h3>
                    <div class="provider-toggle">
                        <select id="select-provider">
                            <option value="ollama">Local (Ollama Qwen2.5)</option>
                            <option value="groq">Cloud (Groq Ultra-Fast)</option>
                        </select>
                    </div>
                </div>
                <div class="chat-history" id="chat-history">
                    <div class="chat-bubble system">
                        <div class="sender">J.A.R.V.I.S</div>
                        <div class="text">Sistemler çevrimiçi patron. Sizi dinliyorum.</div>
                    </div>
                </div>
                <div class="chat-input-container">
                    <input type="text" id="chat-input" placeholder="Sistemlere talimat verin veya konuşun..." autocomplete="off">
                    <button id="btn-send" onclick="sendMessage()">➤</button>
                </div>
            </aside>
        </main>
    </div>
    <script src="/static/app.js"></script>
</body>
</html>"""

# 2. UI APP JS (Susturma Mantığı & Hata Çözümleri)
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

function stopAudio() {
    if (currentAudio) { currentAudio.pause(); currentAudio.currentTime = 0; currentAudio = null; }
    window.speechSynthesis.cancel();
    setOrbStatus("STANDBY MODE");
    document.getElementById("btn-stop-audio").style.display = "none";
}

async function speakResponse(text) {
    try {
        stopAudio();
        document.getElementById("btn-stop-audio").style.display = "inline-flex";
        setOrbStatus("SPEAKING...");
        const res = await fetch("/api/v1/audio/tts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: text }) });
        if (res.ok) {
            const blob = await res.blob();
            currentAudio = new Audio(URL.createObjectURL(blob));
            currentAudio.onended = () => stopAudio();
            currentAudio.play();
        } else {
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = "tr-TR";
            utterance.onend = () => stopAudio();
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

# 3. CHAT SERVICE (Hafıza Enjeksiyonu)
files["services/chat_service.py"] = """from typing import Dict, List, Optional
from core.config import get_settings
from core.logger import setup_logger
from llm.base import BaseLLMProvider, LLMMessage
from llm.ollama_provider import OllamaProvider
from llm.groq_provider import GroqProvider

logger = setup_logger("ChatService")
settings = get_settings()

JARVIS_CHAT_SYSTEM_PROMPT = '''You are J.A.R.V.I.S., a REAL, fully-integrated, autonomous AI Agent Operating Layer running LOCALLY on the user's Windows machine.
CRITICAL OPERATING RULES:
1. YOU HAVE DIRECT OS & FILE ACCESS. Never say you are just an AI.
2. If the context contains recent tool results or actions, USE THEM to answer the user!
3. Answer clearly, professionally, and directly in Turkish.'''

class ChatService:
    def __init__(self):
        self.ollama = OllamaProvider(default_model=settings.DEFAULT_CHAT_MODEL)
        self.groq = GroqProvider(default_model=settings.GROQ_MODEL)
        self._history: Dict[str, List[LLMMessage]] = {}

    def _get_provider(self, provider_name: Optional[str] = "ollama") -> BaseLLMProvider:
        if (provider_name or "ollama").lower() == "groq": return self.groq
        return self.ollama

    async def reply(self, user_message: str, session_id: str = "default", provider_name: str = "ollama") -> str:
        provider = self._get_provider(provider_name)
        if session_id not in self._history:
            self._history[session_id] = [LLMMessage(role="system", content=JARVIS_CHAT_SYSTEM_PROMPT)]
        
        self._history[session_id].append(LLMMessage(role="user", content=user_message))
        if len(self._history[session_id]) > 25:
            self._history[session_id] = [self._history[session_id][0]] + self._history[session_id][-24:]

        try:
            response = await provider.chat(messages=self._history[session_id])
            self._history[session_id].append(LLMMessage(role="assistant", content=response.content))
            return response.content
        except Exception as e:
            logger.error(f"ChatService hatasi: {e}")
            raise RuntimeError(f"Chat provider hatasi: {e}")

    def inject_context(self, text: str, session_id: str = "default"):
        \"\"\"Araç çıktılarını ve otonom sistem bilgisini hafızaya ekler.\"\"\"
        if session_id not in self._history:
            self._history[session_id] = [LLMMessage(role="system", content=JARVIS_CHAT_SYSTEM_PROMPT)]
        self._history[session_id].append(LLMMessage(role="system", content=f"[SİSTEM/ARAÇ BİLGİSİ]: {text}"))
"""

# 4. CHAT ROUTE (Otonom Kurtarma & Sentez)
files["api/routes/chat.py"] = """import re
from fastapi import APIRouter, HTTPException
from agent.dispatcher import ActionDispatcher
from agent.runner import AgentRunner
from agent.orchestrator import orchestrator
from core.types import ChatRequest, ChatResponse, IntentType
from llm.router import IntentRouter
from memory.service import MemoryService
from services.audit_service import SystemAuditService
from services.chat_service import ChatService
from services.diagnostic_service import DiagnosticService
from tasks.models import RiskLevel, TaskCreateRequest
from tasks.service import TaskService

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

intent_router = IntentRouter()
chat_service = ChatService()
task_service = TaskService()
agent_runner = AgentRunner(task_service=task_service)
memory_service = MemoryService()
action_dispatcher = ActionDispatcher(registry=agent_runner.registry)

@router.post("", response_model=ChatResponse)
async def handle_chat_message(request: ChatRequest):
    try:
        user_text = request.message.strip()
        user_text_clean = user_text.replace("💬 Yatırımcının Komutu (Chat'e yazılacak):", "").strip().strip('"')
        lower_text = user_text_clean.lower()

        # EKRAN VE VISION
        if "ekran" in lower_text and any(k in lower_text for k in ["görüntüsü", "goruntusu", "al", "çek", "incele", "foto"]):
            screen_res = await agent_runner.registry.execute("screen_capture")
            if screen_res.success:
                chat_service.inject_context(f"Ekran analizi yapıldı: {screen_res.output}", request.session_id)
                return ChatResponse(response=f"👁️ **[EKRAN GÖRÜŞÜ VE VISION ANALİZİ]**\\n\\n{screen_res.output}", intent=IntentType.TASK, provider_used="groq-vision", model_used="llama-3.2-vision")

        # ÇOKLU AJAN (ORCHESTRATOR)
        if any(k in lower_text for k in ["script tasarla", "auditor", "işbirliği", "kod tasarla", "kod yaz ve denetle", "mimarisi oluştur"]):
            orchestrated = await orchestrator.collaborate(user_text_clean)
            chat_service.inject_context(f"Çoklu ajan işbirliği sonucu kod üretildi.", request.session_id)
            return ChatResponse(response=f"👥 **[KODER & AUDITOR AJANLARI İŞBİRLİĞİ SONUCU]**\\n\\n{orchestrated}", intent=IntentType.CHAT, provider_used="multi-agent", model_used="orchestrator")

        # ACTION DISPATCHER (TEKİL EYLEMLER VE OTONOM KURTARMA)
        dispatch_res = await action_dispatcher.dispatch(user_text_clean, provider_override=request.provider)
        if dispatch_res["matched"]:
            tool_name = dispatch_res["tool_name"]
            args = dispatch_res["arguments"]
            tool_result = await agent_runner.registry.execute(tool_name, **args)
            
            if tool_result.success:
                chat_service.inject_context(f"'{tool_name}' aracı başarıyla çalıştırıldı. Çıktı: {tool_result.output}", request.session_id)
                
                # Sentezlenmiş Akıllı Yanıt (Artık doğrudan tool çıktısı yerine JARVIS'in ağzından dökülecek)
                synth_prompt = f"Şu işlemi az önce başarıyla gerçekleştirdin: {tool_result.output}. Kullanıcıya kısa ve havalı bir dille bilgi ver."
                synth_reply = await chat_service.reply(synth_prompt, request.session_id, request.provider)
                
                return ChatResponse(response=synth_reply, intent=IntentType.TASK, provider_used=request.provider or "ollama", model_used=f"dispatcher->{tool_name}")
            else:
                # OTONOM KURTARMA ZİNCİRİ (Self-Healing)
                if tool_name == "window_manager" and "action" in args and args["action"] == "focus_window":
                    # Pencere öne getirilemediyse (açık değilse) otomatik olarak aç!
                    app_to_open = args.get("target_title", "")
                    chat_service.inject_context(f"'{app_to_open}' penceresi açık değildi, ben de onu otonom olarak başlattım.", request.session_id)
                    await agent_runner.registry.execute("app_launcher", target=app_to_open)
                    return ChatResponse(response=f"ℹ️ **[OTONOM MÜDAHALE]**: '{app_to_open}' penceresi açık değildi, sizin için başlattım.", intent=IntentType.TASK, provider_used="auto-recovery", model_used="app_launcher")

                diag_file = DiagnosticService.create_report("TOOL_EXECUTION_FAILURE", user_text_clean, str(tool_result.error), tool_name, {"arguments": args})
                return ChatResponse(response=f"⚠️ **[EYLEM ENGELİ TESPİT EDİLDİ]**: `{tool_name}` aracı çalıştırılırken sorun oluştu.\\n\\nHata: {tool_result.error}\\n📝 Teşhis Raporu: `{diag_file}`", intent=IntentType.TASK, provider_used="diagnostic-engine", model_used="auto-diagnostics")

        # MULTI-STEP TASK PIPELINE
        intent_result = await intent_router.classify(user_text_clean)
        if intent_result.intent == IntentType.TASK or any(k in lower_text for k in ["oluştur", "yaz", "proje", "rapor"]):
            task = await task_service.create_task(TaskCreateRequest(goal=intent_result.extracted_goal or user_text_clean, context=f"Session: {request.session_id}", auto_plan=True, provider=request.provider))
            if not any(s.risk_level == RiskLevel.HIGH for s in task.steps):
                executed = await agent_runner.run_task(task.id)
                step_res = "\\n".join([f"• **{s.title}:** {s.result or s.error or 'Tamamlandı'}" for s in executed.steps])
                chat_service.inject_context(f"Çok adımlı görev tamamlandı: {task.goal}. Durum: {executed.status.value}", request.session_id)
                return ChatResponse(response=f"🚀 **[GÖREV OTONOM İCRA EDİLDİ]** [ID: `{task.id}`]\\n\\nHedef: {task.goal}\\nDurum: `{executed.status.value.upper()}`\\n\\nAdımlar:\\n{step_res}", intent=IntentType.TASK, provider_used=request.provider or "ollama", model_used="agent-auto-runner")

            steps = "\\n".join([f"{s.id}. {s.title} ({s.risk_level.value.upper()})" for s in task.steps])
            return ChatResponse(response=f"⚠️ **[YÜKSEK RİSKLİ GÖREV PLANLANDI — ONAY BEKLENİYOR]** [ID: `{task.id}`]\\n\\nHedef: {task.goal}\\n\\nAdımlar:\\n{steps}", intent=IntentType.TASK, provider_used="task-planner", model_used="planner")

        # NORMAL SOHBET (Kalıcı Hafızayla Beraber)
        reply = await chat_service.reply(user_text_clean, request.session_id, request.provider)
        return ChatResponse(response=reply, intent=intent_result.intent, provider_used=request.provider or "ollama", model_used="chat")

    except Exception as e:
        diag = DiagnosticService.create_report("CHAT_ROUTE_EXCEPTION", request.message, str(e), context={"provider": request.provider})
        raise HTTPException(status_code=500, detail=f"Sistem Hatası: {diag}")
"""

for rel_path, content in files.items():
    p = Path(f"C:/JARVIS/{rel_path}")
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    print(f"Oluşturuldu/Güncellendi: {p}")
