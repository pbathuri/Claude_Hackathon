"""
live_test.py — interactive live tester for the /chat endpoint.

Run from inside or outside the container:

  # text-only turns (no mic needed)
  python live_test.py

  # with a WAV file for the first turn
  python live_test.py --audio path/to/audio.wav

  # hit a non-default host
  python live_test.py --url http://localhost:8000

Controls during an interactive session:
  - Type your message and press Enter  → text turn
  - Type 'audio <path>'               → send a WAV file
  - Type 'quit' or Ctrl-C             → exit
"""

import argparse
import base64
import json
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("[Error] httpx not installed. Run: pip install httpx")
    sys.exit(1)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _pretty_json(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)


def _save_audio(b64: str, turn: int) -> Path:
    """Decode base64 PCM and save as a raw .pcm file next to this script."""
    out = Path(f"turn_{turn:02d}_response.pcm")
    out.write_bytes(base64.b64decode(b64))
    print(f"    [Audio] Saved raw PCM → {out}")
    print(f"    [Audio] Play with: ffplay -f s16le -ar 22050 -ac 1 {out}")
    return out


def _check_health(base_url: str) -> bool:
    try:
        r = httpx.get(f"{base_url}/health", timeout=5)
        r.raise_for_status()
        data = r.json()
        print("── Health ──────────────────────────────────────────")
        print(f"  smart_llm    : {data.get('smart_llm')}")
        print(f"  whisper_model: {data.get('whisper_model')}")
        print(f"  piper        : {data.get('piper_host')}:{data.get('piper_port')} ({data.get('piper_voice')})")
        print("────────────────────────────────────────────────────\n")
        return True
    except Exception as exc:
        print(f"[Error] Health check failed — is the server running? ({exc})")
        return False


# ── Single turn ───────────────────────────────────────────────────────────────
def send_turn(
    base_url: str,
    text: str | None,
    audio_path: str | None,
    symptoms: list,
    message_history: list,
    turn: int,
) -> dict | None:
    """Send one turn to /chat. Returns the parsed response dict or None on error."""

    data = {
        "symptoms":        json.dumps(symptoms),
        "message_history": json.dumps(message_history),
    }
    files = {}

    if audio_path:
        p = Path(audio_path)
        if not p.exists():
            print(f"[Error] Audio file not found: {p}")
            return None
        files["audio"] = (p.name, p.read_bytes(), "audio/wav")
        print(f"\n── Turn {turn} (audio: {p.name}) ──────────────────────────")
    else:
        data["text"] = text or ""
        print(f"\n── Turn {turn} (text) ──────────────────────────────────────")

    t0 = time.perf_counter()
    try:
        with httpx.Client(timeout=120) as client:
            r = client.post(f"{base_url}/chat", data=data, files=files or None)
    except httpx.ConnectError:
        print(f"[Error] Could not connect to {base_url} — is the server running?")
        return None
    except httpx.TimeoutException:
        print("[Error] Request timed out — model may still be loading.")
        return None

    elapsed = time.perf_counter() - t0

    if r.status_code != 200:
        print(f"[Error] HTTP {r.status_code}: {r.text}")
        return None

    resp = r.json()

    print(f"  Transcript      : {resp.get('transcript') or '(none)'}")
    print(f"  Assistant       : {resp.get('message')}")
    print(f"  Symptoms        : {resp.get('symptoms')}")
    print(f"  Complete        : {resp.get('conversation_complete')}")
    print(f"  Turns so far    : {resp.get('turns')}")
    print(f"  Round-trip      : {elapsed:.2f}s")

    if resp.get("audio"):
        _save_audio(resp["audio"], turn)
    else:
        print("  [Audio]         : (no audio returned)")

    return resp


# ── Multi-turn conversation runner ────────────────────────────────────────────
def run_script(base_url: str, turns: list[dict]) -> None:
    """
    Run a pre-defined list of turns non-interactively.
    Each turn dict: {"text": "..."} or {"audio": "path/to/file.wav"}
    """
    symptoms:        list = []
    message_history: list = []

    for i, turn_def in enumerate(turns, start=1):
        resp = send_turn(
            base_url,
            text=turn_def.get("text"),
            audio_path=turn_def.get("audio"),
            symptoms=symptoms,
            message_history=message_history,
            turn=i,
        )
        if resp is None:
            print("[Abort] Stopping script due to error.")
            return

        symptoms        = resp.get("symptoms", symptoms)
        message_history = resp.get("message_history", message_history)

        if resp.get("conversation_complete"):
            print("\n[Done] Conversation marked complete by the model.")
            return

    print("\n[Done] All scripted turns sent.")


def run_interactive(base_url: str, first_audio: str | None) -> None:
    """Interactive REPL — type messages or 'audio <path>'."""
    symptoms:        list = []
    message_history: list = []
    turn = 0

    print("Interactive mode. Commands:")
    print("  <message>        → text turn")
    print("  audio <path>     → send a WAV file")
    print("  state            → print current symptoms + history")
    print("  quit             → exit\n")

    # Optional first audio turn
    if first_audio:
        turn += 1
        resp = send_turn(base_url, None, first_audio, symptoms, message_history, turn)
        if resp:
            symptoms        = resp.get("symptoms", symptoms)
            message_history = resp.get("message_history", message_history)
            if resp.get("conversation_complete"):
                print("\n[Done] Conversation complete.")
                return

    while True:
        try:
            raw = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not raw:
            continue
        if raw.lower() == "quit":
            break
        if raw.lower() == "state":
            print("Symptoms :", symptoms)
            print("History  :", _pretty_json(message_history))
            continue

        audio_path = None
        text_input  = raw
        if raw.lower().startswith("audio "):
            audio_path = raw[6:].strip()
            text_input  = None

        turn += 1
        resp = send_turn(
            base_url, text_input, audio_path, symptoms, message_history, turn
        )
        if resp is None:
            continue

        symptoms        = resp.get("symptoms", symptoms)
        message_history = resp.get("message_history", message_history)

        if resp.get("conversation_complete"):
            print("\n[Done] The model has collected enough symptoms.")
            print("Final symptom list:", symptoms)
            break


# ── Predefined smoke-test script ──────────────────────────────────────────────
SMOKE_TEST = [
    {"text": "Hi, I've been feeling really tired lately."},
    {"text": "I also have a headache and a low fever, around 37.8."},
    {"text": "The headache is mostly at the front, started two days ago."},
    {"text": "No nausea, but I've lost my appetite."},
    {"text": "No, I don't think I've been exposed to anyone sick."},
]


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Live tester for /chat endpoint")
    parser.add_argument("--url",    default="http://localhost:8000", help="API base URL")
    parser.add_argument("--audio",  default=None,  help="WAV file for the first turn")
    parser.add_argument("--smoke",  action="store_true", help="Run the built-in smoke test script")
    parser.add_argument("--script", default=None, help="Path to a JSON turns file")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")
    print(f"Target: {base_url}\n")

    if not _check_health(base_url):
        sys.exit(1)

    if args.smoke:
        print("── Smoke test ──────────────────────────────────────")
        run_script(base_url, SMOKE_TEST)

    elif args.script:
        turns_file = Path(args.script)
        if not turns_file.exists():
            print(f"[Error] Script file not found: {turns_file}")
            sys.exit(1)
        turns = json.loads(turns_file.read_text())
        print(f"── Running script: {turns_file} ({len(turns)} turns) ──")
        run_script(base_url, turns)

    else:
        run_interactive(base_url, first_audio=args.audio)


if __name__ == "__main__":
    main()
