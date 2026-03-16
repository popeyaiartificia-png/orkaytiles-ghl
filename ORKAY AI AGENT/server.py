"""
Orkay Tiles — AI Voice Agent Server + Dashboard
Stack: Vobiz → Sarvam STT → Sarvam 105B → Sarvam TTS
Dashboard: http://localhost:8000
"""

import os, re, uuid, json, base64, asyncio
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import httpx
from fastapi import FastAPI, Form, Request, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import Response, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

# ─── Credentials ─────────────────────────────────────────────────────────────
SARVAM_API_KEY  = os.getenv("SARVAM_API_KEY")
GHL_API_KEY     = os.getenv("GHL_API_KEY")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

SARVAM_STT_URL  = "https://api.sarvam.ai/speech-to-text"
SARVAM_TTS_URL  = "https://api.sarvam.ai/text-to-speech"
SARVAM_CHAT_URL = "https://api.sarvam.ai/v1/chat/completions"

BASE_DIR     = Path(__file__).parent
AUDIO_DIR    = BASE_DIR / "audio_cache";  AUDIO_DIR.mkdir(exist_ok=True)
HISTORY_FILE = BASE_DIR / "call_history.json"

# ─── In-memory state ──────────────────────────────────────────────────────────
call_sessions: dict[str, dict] = {}   # live calls
ws_clients:    list[WebSocket] = []   # dashboard WebSocket subscribers

# ─── Call History (persisted to JSON) ────────────────────────────────────────
def load_history() -> list:
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text())
    return []

def save_history(record: dict):
    h = load_history()
    h.insert(0, record)   # newest first
    h = h[:200]            # keep last 200
    HISTORY_FILE.write_text(json.dumps(h, ensure_ascii=False, indent=2))

# ─── WebSocket Broadcast ─────────────────────────────────────────────────────
async def broadcast(event: str, data: dict):
    dead = []
    for ws in ws_clients:
        try:
            await ws.send_text(json.dumps({"event": event, **data}))
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_clients.remove(ws)

# ─── System Prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Aria, a professional sales agent for Orkay Tiles — India's leading tile manufacturer from Morbi, Gujarat. You are making an outbound call to a potential dealer or distributor.

## About Orkay Tiles
- Since 1996 | 1,50,000 sqft/day capacity | 500+ designs
- Products: Ceramic Wall Tiles, GVT/PGVT, Porcelain, Large Format Slabs, Parking Tiles
- Certifications: ISO 9001:2015, BIS, CE, SONCAP
- Benefits: 25 KM exclusive territory, 12-15 day dispatch, export to 40+ countries

## Your Objectives (in order)
1. Greet warmly, introduce yourself and Orkay Tiles briefly
2. Confirm they are a tile dealer / builder / architect
3. Understand current tile sourcing (brands, monthly volume in sqft)
4. Pitch Orkay's key advantages (exclusive territory, quality, fast dispatch)
5. If interested → collect: Name, Business Name, City, Monthly sqft requirement
6. Close: schedule showroom visit OR send catalog on WhatsApp
7. If not interested → thank politely, end the call

## CRITICAL Rules (phone call — not chat)
- MAX 2 short sentences per response
- Speak naturally in Hinglish — match the caller's language
- If busy: "Bilkul samjha, kab call karun? Subah 10 baje?"
- If price asked: "Detail WhatsApp pe bhej deti hoon — aapka number confirm karein"
- When info collected, end with exactly: [CALL_COMPLETE] then a goodbye line
- When caller wants to end: [CALL_END] then polite goodbye

## Silent Data Collection
When you have collected info, append silently (not spoken):
[DATA:{"name":"...","business":"...","city":"...","volume":"...","interest":"high/medium/low"}]"""

GREETING_TEXT = "Hello! Main Aria bol rahi hoon Orkay Tiles ki taraf se — Morbi, Gujarat se. Kya main bas 2 minute le sakti hoon aapka? Hum India ke leading tile manufacturers hain aur aapke area mein authorized dealer dhundh rahe hain."

# ─── Sarvam STT ──────────────────────────────────────────────────────────────
async def transcribe(audio_url: str) -> str:
    async with httpx.AsyncClient(timeout=30) as c:
        audio = await c.get(audio_url)
        resp  = await c.post(
            SARVAM_STT_URL,
            headers={"api-subscription-key": SARVAM_API_KEY},
            files={"file": ("rec.wav", audio.content, "audio/wav")},
            data={"model": "saaras:v3", "mode": "transcribe", "language_code": "hi-IN"},
        )
        text = resp.json().get("transcript", "")
        print(f"[STT] {text}")
        return text

# ─── Sarvam LLM ──────────────────────────────────────────────────────────────
async def llm_reply(history: list) -> str:
    async with httpx.AsyncClient(timeout=30) as c:
        resp = await c.post(
            SARVAM_CHAT_URL,
            headers={"Authorization": f"Bearer {SARVAM_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "sarvam-105b",
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + history,
                "temperature": 0.7,
                "max_tokens": 150,
            },
        )
        reply = resp.json()["choices"][0]["message"]["content"]
        print(f"[LLM] {reply}")
        return reply

# ─── Sarvam TTS ──────────────────────────────────────────────────────────────
async def synthesize(text: str) -> str:
    clean = re.sub(r'\[DATA:.*?\]', '', text, flags=re.DOTALL)
    clean = clean.replace("[CALL_COMPLETE]", "").replace("[CALL_END]", "").strip()
    async with httpx.AsyncClient(timeout=30) as c:
        resp = await c.post(
            SARVAM_TTS_URL,
            headers={"api-subscription-key": SARVAM_API_KEY, "Content-Type": "application/json"},
            json={"inputs": [clean], "target_language_code": "hi-IN",
                  "speaker": "meera", "model": "bulbul:v1",
                  "sample_rate": 8000, "enable_preprocessing": True},
        )
        audio_bytes = base64.b64decode(resp.json().get("audios", [""])[0])
        fname = f"{uuid.uuid4().hex}.wav"
        (AUDIO_DIR / fname).write_bytes(audio_bytes)
        url = f"{PUBLIC_BASE_URL}/audio/{fname}"
        print(f"[TTS] {url}")
        return url

# ─── GHL ─────────────────────────────────────────────────────────────────────
async def ghl_update(contact_id: str, note: str, tags: list):
    if not contact_id: return
    h = {"Authorization": f"Bearer {GHL_API_KEY}", "Version": "2021-07-28"}
    async with httpx.AsyncClient(timeout=15) as c:
        await c.post(f"https://services.leadconnectorhq.com/contacts/{contact_id}/notes", headers=h, json={"body": note})
        if tags:
            await c.post(f"https://services.leadconnectorhq.com/contacts/{contact_id}/tags", headers=h, json={"tags": tags})

# ─── Post-call wrap-up ────────────────────────────────────────────────────────
async def wrap_up(session: dict):
    data     = session.get("collected_data", {})
    interest = data.get("interest", "unknown")
    history  = session.get("history", [])
    duration = int((datetime.utcnow() - session.get("started_at", datetime.utcnow())).total_seconds())

    transcript = "\n".join(
        f"{'Aria' if m['role']=='assistant' else 'Customer'}: {m['content']}"
        for m in history
    )
    note = f"📞 AI Call — Aria\nInterest: {interest.upper()}\n\n{transcript}"
    tags = ["ai-call-done"]
    if   interest == "high":   tags += ["hot-lead",  "call-interested"]
    elif interest == "medium": tags += ["warm-lead", "call-interested"]
    else:                      tags += ["call-not-interested"]

    await ghl_update(session.get("contact_id",""), note, tags)

    record = {
        "id":           session.get("call_uuid", uuid.uuid4().hex),
        "ts":           datetime.utcnow().isoformat(),
        "number":       session.get("contact_number",""),
        "contact_id":   session.get("contact_id",""),
        "contact_name": session.get("contact_name",""),
        "duration_s":   duration,
        "turns":        session.get("turn", 0),
        "interest":     interest,
        "collected":    data,
        "transcript":   transcript,
    }
    save_history(record)
    await broadcast("call_ended", {"call": record})
    print(f"[DONE] Saved call {record['id']}")

# ─── XML builder ─────────────────────────────────────────────────────────────
def vxml(audio_url: str, record_url: str = "", hangup: bool = False) -> Response:
    if hangup:
        xml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Play>{audio_url}</Play><Hangup/></Response>'
    else:
        xml = (f'<?xml version="1.0" encoding="UTF-8"?><Response>'
               f'<Play>{audio_url}</Play>'
               f'<Record action="{record_url}" method="POST" maxLength="15" timeout="3" finishOnKey="#"/>'
               f'</Response>')
    return Response(content=xml, media_type="application/xml")

# ─── FastAPI ──────────────────────────────────────────────────────────────────
app = FastAPI(title="Orkay AI Agent")
app.mount("/audio", StaticFiles(directory=str(AUDIO_DIR), check_dir=False), name="audio")

# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return FileResponse(BASE_DIR / "dashboard.html")

@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await ws.accept()
    ws_clients.append(ws)
    # send current state immediately
    await ws.send_text(json.dumps({
        "event":   "init",
        "active":  list(call_sessions.values()),
        "history": load_history()[:20],
        "stats":   compute_stats(),
    }))
    try:
        while True:
            await ws.receive_text()   # keep alive
    except WebSocketDisconnect:
        ws_clients.remove(ws)

@app.get("/api/history")
async def api_history():
    return load_history()

@app.get("/api/active")
async def api_active():
    return list(call_sessions.values())

@app.get("/api/stats")
async def api_stats():
    return compute_stats()

@app.get("/api/config")
async def api_config():
    return {
        "system_prompt":  SYSTEM_PROMPT,
        "greeting":       GREETING_TEXT,
        "stt_model":      "saaras:v3",
        "tts_speaker":    "meera",
        "llm_model":      "sarvam-105b",
        "language":       "hi-IN",
        "from_number":    os.getenv("VOBIZ_FROM_NUMBER"),
        "public_base_url": PUBLIC_BASE_URL,
    }

@app.post("/api/call/make")
async def api_make_call(request: Request):
    body         = await request.json()
    to_number    = body.get("to", "")
    contact_id   = body.get("contact_id", "")
    contact_name = body.get("name", "")

    if not to_number:
        return {"error": "Missing phone number"}

    auth_id     = os.getenv("VOBIZ_AUTH_ID")
    auth_secret = os.getenv("VOBIZ_AUTH_SECRET")
    from_number = os.getenv("VOBIZ_FROM_NUMBER")

    # Correct Vobiz endpoint: /api/v1/Account/{auth_id}/Call/
    vobiz_url = f"https://api.vobiz.ai/api/v1/Account/{auth_id}/Call/"

    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.post(
                vobiz_url,
                headers={
                    "X-Auth-ID":    auth_id,
                    "X-Auth-Token": auth_secret,
                    "Content-Type": "application/json",
                },
                json={
                    "from":       from_number,
                    "to":         to_number,
                    "answer_url": f"{PUBLIC_BASE_URL}/webhook/answer",
                    "hangup_url": f"{PUBLIC_BASE_URL}/webhook/hangup",
                    "ring_url":   f"{PUBLIC_BASE_URL}/webhook/hangup",
                    "sip_trunk_id": os.getenv("VOBIZ_TRUNK_ID", ""),
                },
            )
            print(f"[VOBIZ] {resp.status_code}: {resp.text[:200]}")
            result    = resp.json()
            call_uuid = result.get("call_uuid") or result.get("uuid", uuid.uuid4().hex)
    except Exception as e:
        print(f"[VOBIZ ERROR] {e}")
        return {"error": str(e)}

    session = {
        "call_uuid":      call_uuid,
        "history":        [],
        "contact_id":     contact_id,
        "contact_name":   contact_name,
        "contact_number": to_number,
        "turn":           0,
        "status":         "ringing",
        "started_at":     datetime.utcnow().isoformat(),
    }
    call_sessions[call_uuid] = session
    await broadcast("call_started", {"call_uuid": call_uuid, "number": to_number, "name": contact_name})

    return {"status": "initiated", "call_uuid": call_uuid, "vobiz": result}

def compute_stats() -> dict:
    history = load_history()
    total   = len(history)
    high    = sum(1 for c in history if c.get("interest") == "high")
    medium  = sum(1 for c in history if c.get("interest") == "medium")
    avg_dur = int(sum(c.get("duration_s", 0) for c in history) / total) if total else 0
    return {"total": total, "hot_leads": high, "warm_leads": medium, "avg_duration_s": avg_dur}

# ═══════════════════════════════════════════════════════════════════════════════
# VOBIZ WEBHOOKS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/webhook/answer")
async def on_answer(
    CallUUID: str = Form(default=""),
    From:     str = Form(default=""),
    To:       str = Form(default=""),
):
    call_uuid = CallUUID or uuid.uuid4().hex
    print(f"[ANSWER] {call_uuid} | {From} → {To}")

    if call_uuid not in call_sessions:
        call_sessions[call_uuid] = {
            "call_uuid": call_uuid, "history": [], "contact_id": "",
            "contact_name": "", "contact_number": To, "turn": 0,
            "status": "active", "started_at": datetime.utcnow(),
        }
    else:
        call_sessions[call_uuid]["status"] = "active"

    await broadcast("call_update", {"call_uuid": call_uuid, "status": "active", "turn": 0})

    greeting_url = await synthesize(GREETING_TEXT)
    record_url   = f"{PUBLIC_BASE_URL}/webhook/recording?call_uuid={call_uuid}"
    return vxml(greeting_url, record_url)


@app.post("/webhook/recording")
async def on_recording(
    request:          Request,
    background_tasks: BackgroundTasks,
    call_uuid:        str = "",
    CallUUID:         str = Form(default=""),
    RecordingUrl:     str = Form(default=""),
    Duration:         str = Form(default="0"),
):
    cid     = call_uuid or CallUUID
    session = call_sessions.get(cid)
    if not session:
        bye = await synthesize("Dhanyawad! Wapas call karein agar zaroorat ho.")
        return vxml(bye, hangup=True)

    session["turn"] += 1
    print(f"[REC] Turn {session['turn']} | {Duration}s")

    if session["turn"] > 12:
        bye_url = await synthesize("Bahut shukriya! Hamara team aapko jald contact karega. Have a great day!")
        background_tasks.add_task(wrap_up, dict(session))
        call_sessions.pop(cid, None)
        return vxml(bye_url, hangup=True)

    user_text = ""
    if RecordingUrl and int(Duration or "0") >= 1:
        user_text = await transcribe(RecordingUrl)

    if not user_text.strip():
        prompt_url = await synthesize("Kya aap mujhe sun pa rahe hain? Kuch bolein please.")
        return vxml(prompt_url, f"{PUBLIC_BASE_URL}/webhook/recording?call_uuid={cid}")

    session["history"].append({"role": "user", "content": user_text})
    reply = await llm_reply(session["history"])
    session["history"].append({"role": "assistant", "content": reply})

    # Parse collected data
    m = re.search(r'\[DATA:(.*?)\]', reply, re.DOTALL)
    if m:
        try: session["collected_data"] = json.loads(m.group(1))
        except: pass

    await broadcast("call_update", {
        "call_uuid":  cid,
        "turn":       session["turn"],
        "status":     "active",
        "user_said":  user_text,
        "aria_said":  re.sub(r'\[.*?\]', '', reply).strip(),
    })

    should_end = "[CALL_COMPLETE]" in reply or "[CALL_END]" in reply
    audio_url  = await synthesize(reply)

    if should_end:
        background_tasks.add_task(wrap_up, dict(session))
        call_sessions.pop(cid, None)
        return vxml(audio_url, hangup=True)

    return vxml(audio_url, f"{PUBLIC_BASE_URL}/webhook/recording?call_uuid={cid}")


@app.post("/webhook/hangup")
async def on_hangup(
    background_tasks: BackgroundTasks,
    CallUUID:         str = Form(default=""),
    Duration:         str = Form(default=""),
    HangupCause:      str = Form(default=""),
):
    session = call_sessions.pop(CallUUID, None)
    print(f"[HANGUP] {CallUUID} | {Duration}s | {HangupCause}")
    if session:
        background_tasks.add_task(wrap_up, dict(session))
    return Response(status_code=204)


# Also expose /call/initiate for n8n
@app.post("/call/initiate")
async def call_initiate(request: Request):
    return await api_make_call(request)


@app.get("/health")
async def health():
    return {"status": "ok", "public_url": PUBLIC_BASE_URL,
            "llm": "sarvam-105b", "stt": "saaras:v3", "tts": "bulbul:v1/meera"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
