"""
make_call.py — Trigger a test outbound call via Vobiz

Usage:
  python make_call.py +919XXXXXXXXX

This script calls Vobiz API directly to initiate an outbound call.
Your server.py must be running + ngrok must be active first.
"""

import sys
import os
import requests
from dotenv import load_dotenv

load_dotenv()

VOBIZ_AUTH_ID     = os.getenv("VOBIZ_AUTH_ID")
VOBIZ_AUTH_SECRET = os.getenv("VOBIZ_AUTH_SECRET")
FROM_NUMBER       = os.getenv("VOBIZ_FROM_NUMBER")
PUBLIC_BASE_URL   = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")


def make_call(to_number: str, contact_id: str = ""):
    answer_url = f"{PUBLIC_BASE_URL}/webhook/answer"
    hangup_url = f"{PUBLIC_BASE_URL}/webhook/hangup"

    print(f"\n📞 Initiating call:")
    print(f"   From : {FROM_NUMBER}")
    print(f"   To   : {to_number}")
    print(f"   Hook : {answer_url}\n")

    resp = requests.post(
        "https://api.vobiz.ai/v1/Call",
        auth=(VOBIZ_AUTH_ID, VOBIZ_AUTH_SECRET),
        data={
            "From":                 FROM_NUMBER,
            "To":                   to_number,
            "Url":                  answer_url,
            "StatusCallbackUrl":    hangup_url,
            "StatusCallbackMethod": "POST",
        },
        timeout=15
    )

    print(f"Status : {resp.status_code}")
    try:
        result = resp.json()
        print(f"Result : {result}")
        call_uuid = (
            result.get("call_uuid")
            or result.get("CallUUID")
            or result.get("uuid", "N/A")
        )
        print(f"\n✅ Call UUID: {call_uuid}")
        print("   Watch server.py logs for STT → LLM → TTS activity.")
    except Exception:
        print(f"Raw response: {resp.text}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python make_call.py +919XXXXXXXXX")
        print("\nSteps before running:")
        print("  1. Start server:  python server.py")
        print("  2. Start ngrok:   ngrok http 8000")
        print("  3. Copy ngrok URL into .env → PUBLIC_BASE_URL")
        print("  4. Then run this script")
        sys.exit(1)

    to_number  = sys.argv[1]
    contact_id = sys.argv[2] if len(sys.argv) > 2 else ""
    make_call(to_number, contact_id)
