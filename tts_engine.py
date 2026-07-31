"""
WSDA TTS Engine -- ElevenLabs Integration
Generates narration MP3s from text.
"""

import os
import requests
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("wsda.tts")

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel
ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech"

if not ELEVENLABS_API_KEY:
    try:
        with open(".env", "r") as f:
            for line in f:
                if line.startswith("ELEVENLABS_API_KEY="):
                    ELEVENLABS_API_KEY = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass


def generate_narration(text: str, output_path: str, voice_id: Optional[str] = None) -> str:
    api_key = ELEVENLABS_API_KEY
    if not api_key:
        raise RuntimeError(
            "ELEVENLABS_API_KEY not found. Set it as an environment variable "
            "or in a .env file in your repo root."
        )

    voice = voice_id or ELEVENLABS_VOICE_ID
    url = f"{ELEVENLABS_URL}/{voice}"

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key,
    }

    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        }
    }

    logger.info(f"Generating TTS: '{text[:60]}...' -> {output_path}")
    response = requests.post(url, json=payload, headers=headers, timeout=60)

    if response.status_code != 200:
        raise RuntimeError(
            f"ElevenLabs API error {response.status_code}: {response.text}"
        )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "wb") as f:
        f.write(response.content)

    logger.info(f"Audio saved: {output_path} ({len(response.content)} bytes)")
    return output_path
