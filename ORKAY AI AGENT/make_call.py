"""
make_call.py — Trigger a test outbound call via Vobiz

Usage:
  python make_call.py +919XXXXXXXXX

Requires: server.py running + PUBLIC_BASE_URL set in .env
"""

import sys, os, requests
from dotenv import load_dotenv

load_dotenv()

AUTH_ID         = os.getenv("VOBIZ_AUTH_ID")
AUTH_SECRET     = os.getenv("VOBIZ_AUTH_SECRET")
FROM_NUMBER     = os.getenv("VOBIZ_FROM_NUMBER")
TRUNK_ID        = os.getenv("VOBIZ_TRUNK_ID", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

def make_call(to_number: str):
    url = f"https://api.vobiz.ai/api/v1/Account/{AUTH_ID}/Call/"
    payload = {
        "from":         FROM_NUMBER,
        "to":           to_number,
        "answer_url":   f"{PUBLIC_BASE_URL}/webhook/answer",
        "hangup_url":   f"{PUBLIC_BASE_URL}/webhook/hangup",
        "sip_trunk_id": TRUNK_ID,
    }
    print(f"Calling {to_number} via {FROM_NUMBER}...")
    resp = requests.post(url, headers={"X-Auth-ID": AUTH_ID, "X-Auth-Token": AUTH_SECRET}, json=payload, timeout=15)
    print(f"Status: {resp.status_code}")
    print(f"Result: {resp.text}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python make_call.py +919XXXXXXXXX")
        sys.exit(1)
    make_call(sys.argv[1])
