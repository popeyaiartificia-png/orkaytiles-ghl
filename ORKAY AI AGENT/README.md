# Orkay Tiles — AI Voice Agent

Outbound calling agent for Orkay Tiles India. Aria calls potential dealers, pitches the product, and logs results back to GHL.

## Stack
- **Telephony**: Vobiz (Indian VoIP)
- **STT**: Sarvam `saaras:v3`
- **LLM**: Sarvam `sarvam-105b` (Hindi/Hinglish)
- **TTS**: Sarvam `bulbul:v1` — Meera voice
- **CRM**: GoHighLevel (GHL)
- **Automation**: n8n

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Fill in your keys in .env
```

### 3. Get a public URL (pick one)
```bash
# Option A — Cloudflare (recommended, free)
cloudflared tunnel --url http://localhost:8000

# Option B — GitHub Codespaces
# Open repo in Codespaces → Ports tab → Forward 8000 → Make Public
```
Paste the URL into `.env` as `PUBLIC_BASE_URL`.

### 4. Start the server
```bash
python server.py
# OR double-click START_DASHBOARD.bat on Windows
```

### 5. Open dashboard
Go to **http://localhost:8000**

## n8n Integration
Import `n8n_workflow.json` into your n8n instance. Set these env vars in n8n:
- `AGENT_SERVER_URL` = your public URL
- `GHL_API_KEY` = your GHL private integration token

## Files
| File | Purpose |
|------|---------|
| `server.py` | FastAPI server — webhooks + dashboard API |
| `dashboard.html` | Web dashboard UI |
| `make_call.py` | CLI tool to trigger a test call |
| `n8n_workflow.json` | n8n automation workflow |
| `START_DASHBOARD.bat` | One-click start on Windows |
