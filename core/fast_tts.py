"""
Ultra-fast, Lightweight Text-To-Speech (TTS) & Reply Module for JARVIS-S.

Uses Microsoft edge-tts (neural online voices) and pygame.mixer for low-latency,
zero-RAM playback that replaces heavy pyttsx3/gTTS engines.
"""
import os
import sys
import asyncio
import tempfile
import uuid
import pygame
import edge_tts
from core.ram_cleaner import release_unused_ram

# Fast neural voices mapped to assistant personalities
VOICE_MAP = {
    "aria": "en-US-AriaNeural",
    "guy": "en-US-GuyNeural",
    "swara": "hi-IN-SwaraNeural",
    "neerja": "en-IN-NeerjaNeural",
    "mayra": "hi-IN-SwaraNeural",
    "snow": "hi-IN-SwaraNeural",
    "nia": "en-IN-NeerjaNeural",
    "dragon": "en-US-JennyNeural",
    "charon": "en-GB-RyanNeural",
    "kavya": "hi-IN-SwaraNeural",
    "xg": "en-IN-NeerjaNeural",
    "tiara": "en-US-JennyNeural",
}

DEFAULT_FAST_VOICE = "en-US-AriaNeural"


def resolve_edge_voice(voice_name: str | None) -> str:
    """Resolve a voice name or character persona to a valid Edge TTS neural voice."""
    if not voice_name:
        return DEFAULT_FAST_VOICE
    v_clean = voice_name.strip().lower()
    if v_clean in VOICE_MAP:
        return VOICE_MAP[v_clean]
    if "neural" in v_clean:
        return voice_name.strip()
    return DEFAULT_FAST_VOICE


async def speak_fast(text: str, voice: str = DEFAULT_FAST_VOICE) -> bool:
    """
    Generate speech using edge-tts and play via pygame.mixer without blocking CPU.
    """
    if not text or not text.strip():
        return False

    v_target = resolve_edge_voice(voice)
    temp_file = os.path.join(tempfile.gettempdir(), f"jarvis_reply_{uuid.uuid4().hex[:8]}.mp3")

    try:
        # 1. Synthesize neural speech directly to temporary MP3
        communicate = edge_tts.Communicate(text, v_target)
        await communicate.save(temp_file)

        # 2. Fast lightweight playback using pygame.mixer
        if not pygame.mixer.get_init():
            pygame.mixer.init()

        pygame.mixer.music.load(temp_file)
        pygame.mixer.music.play()

        # Non-blocking async loop to wait for audio to finish without burning CPU
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.05)

        return True
    except Exception as e:
        print(f"[FastTTS] ⚠️ speak_fast error: {e}")
        return False
    finally:
        # 3. Clean up file handle, disk space, and trigger smart RAM release
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.unload()
        except Exception:
            pass
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass
        release_unused_ram()


def speak_fast_sync(text: str, voice: str = DEFAULT_FAST_VOICE) -> bool:
    """Synchronous wrapper for speak_fast."""
    try:
        return asyncio.run(speak_fast(text, voice))
    except RuntimeError:
        # If event loop is already running in current thread, run via task or thread
        import threading
        result = [False]
        def _runner():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result[0] = loop.run_until_complete(speak_fast(text, voice))
            loop.close()
        t = threading.Thread(target=_runner, daemon=True)
        t.start()
        t.join()
        return result[0]
