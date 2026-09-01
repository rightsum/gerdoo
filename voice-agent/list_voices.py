#!/usr/bin/env python3
"""
List the ElevenLabs voices this account can use, so ELEVEN_VOICE_ID can be set
to a real id instead of one copied off a web page.

Reads ELEVEN_API_KEY from .env. Run it via `make voices`.
"""

import json
import os
import ssl
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()

key = os.environ.get("ELEVEN_API_KEY", "")
if not key:
    sys.exit("ELEVEN_API_KEY is not set in .env")

# This python.org framework build ships without root certificates, so a plain
# urlopen fails with CERTIFICATE_VERIFY_FAILED. certifi is already present as a
# dependency of the LiveKit stack.
try:
    import certifi
    ctx = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    ctx = ssl.create_default_context()

req = urllib.request.Request(
    "https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": key}
)
try:
    with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
        voices = json.load(r).get("voices", [])
except urllib.error.HTTPError as e:
    sys.exit(f"ElevenLabs returned {e.code}: {e.reason}. Check ELEVEN_API_KEY.")
except Exception as e:
    sys.exit(f"could not reach ElevenLabs: {e}")

current = os.environ.get("ELEVEN_VOICE_ID", "")
print(f"{len(voices)} voices on this account\n")
for v in voices:
    labels = v.get("labels") or {}
    # Accent and gender matter more than anything else when picking a voice to
    # speak both Persian and English.
    desc = " ".join(
        str(labels[k]) for k in ("accent", "gender", "age", "description")
        if labels.get(k)
    )
    mark = "->" if v["voice_id"] == current else "  "
    print(f"{mark} {v['voice_id']}  {v['name']:<24} {desc}")

print("\nSet ELEVEN_VOICE_ID in .env to one of the ids above, then: make restart")
