#!/usr/bin/env python3
import os, requests

key = os.environ.get("ELEVENLABS_API_KEY", "sk_4433936bcb2ce938b270c4efae75305996b73eeb6790bed9")
voice = os.environ.get("ELEVENLABS_VOICE_ID", "E5wNdHqDxPAZRB8qRbQh")

print(f"Key: {key[:20]}...")
print(f"Voice: {voice}")

# Test 1: List voices
r = requests.get("https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": key})
print(f"\nList voices: {r.status_code}")
if r.status_code == 200:
    voices = r.json().get("voices", [])
    for v in voices:
        if v["voice_id"] == voice:
            print(f"  ✓ Found your voice: {v['name']}")
            break
    else:
        print(f"  ✗ Voice {voice} NOT FOUND in your account")
        print(f"  Available: {[v['voice_id'] for v in voices[:5]]}")
else:
    print(f"  Error: {r.text[:200]}")

# Test 2: Synthesize one word
r = requests.post(
    f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
    headers={"xi-api-key": key, "Content-Type": "application/json"},
    json={"text": "Hello, this is a test.", "model_id": "eleven_v3"}
)
print(f"\nSynthesize: {r.status_code}")
if r.status_code == 200:
    with open("test_voice.mp3", "wb") as f:
        f.write(r.content)
    print("  ✓ Saved test_voice.mp3 — play it to confirm it's your voice")
else:
    print(f"  Error: {r.text[:300]}")
