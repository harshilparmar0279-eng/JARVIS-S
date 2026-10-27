"""
ElevenLabs speech synthesis — the multilingual voice.

Official ElevenLabs API endpoints implemented:
- Voices list: https://api.elevenlabs.io/v1/voices
- Single voice: https://api.elevenlabs.io/v1/voices/{voice_id}
- Text-to-speech stream: https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream
- Models list: https://api.elevenlabs.io/v1/models
"""
from __future__ import annotations

import asyncio
import json
from importlib.util import find_spec
from typing import Any, AsyncIterator, Optional

from . import audio
from .base import DEFAULT_CAPS, Field

API = "https://api.elevenlabs.io/v1"

MODELS = (
    "eleven_flash_v2_5",        # fastest, multilingual
    "eleven_multilingual_v2",   # best quality, standard
    "eleven_turbo_v2_5",        # fast & rich
)
DEFAULT_MODEL = "eleven_flash_v2_5"

_PCM = "pcm_24000"
_MP3 = "mp3_44100_128"


def validate_elevenlabs_credentials(api_key: str, voice_id: str = "", model_id: str = "") -> dict:
    """Validate ElevenLabs API key, access to the specified voice ID, and model capability.
    Follows official ElevenLabs API documentation and returns actionable diagnostic details.
    """
    import httpx

    key = (api_key or "").strip()
    if not key:
        return {"valid": False, "error": "No ElevenLabs API key provided.", "error_code": "MISSING_KEY"}

    headers = {"xi-api-key": key, "Accept": "application/json"}

    # 1. Verify API Key validity & list accessible voices
    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.get(f"{API}/voices", headers=headers)
            if resp.status_code == 401:
                return {
                    "valid": False,
                    "error": "Authentication failed. The ElevenLabs API key was refused (HTTP 401).",
                    "error_code": "AUTH_FAILED"
                }
            if resp.status_code == 429:
                return {
                    "valid": False,
                    "error": "ElevenLabs rate limit reached or quota exhausted (HTTP 429).",
                    "error_code": "RATE_LIMIT"
                }
            if resp.status_code >= 500:
                return {
                    "valid": False,
                    "error": f"ElevenLabs service outage or error (HTTP {resp.status_code}).",
                    "error_code": "PROVIDER_OUTAGE"
                }
            if resp.status_code != 200:
                err_text = _message(resp.text)
                return {
                    "valid": False,
                    "error": f"ElevenLabs error ({resp.status_code}): {err_text}",
                    "error_code": f"HTTP_{resp.status_code}"
                }

            voices_data = resp.json().get("voices", [])
            voice_map = {v.get("voice_id"): v.get("name", "Unknown") for v in voices_data}

            # If voice_id specified, check specific voice
            vid = (voice_id or "").strip()
            voice_name = voice_map.get(vid, "")
            is_library_voice = False

            if vid:
                # Check voice directly
                v_resp = client.get(f"{API}/voices/{vid}", headers=headers)
                if v_resp.status_code == 404:
                    return {
                        "valid": False,
                        "error": f"Voice ID '{vid}' was not found on this ElevenLabs account.",
                        "error_code": "VOICE_NOT_FOUND"
                    }
                if v_resp.status_code == 200:
                    v_info = v_resp.json()
                    voice_name = v_info.get("name", voice_name or vid)
                    cat = (v_info.get("category") or "").lower()
                    if "library" in cat or "community" in cat or "shared" in cat:
                        is_library_voice = True

                # Perform quick pre-flight generation probe to check tier restrictions (e.g. 402 for library voices on free tier)
                probe_model = model_id or DEFAULT_MODEL
                probe_url = f"{API}/text-to-speech/{vid}/stream"
                probe_resp = client.post(
                    probe_url,
                    headers=headers,
                    params={"output_format": _PCM},
                    json={"text": "Test", "model_id": probe_model},
                    timeout=10.0
                )
                if probe_resp.status_code == 402:
                    body = probe_resp.text
                    clean_msg = _message(body)
                    return {
                        "valid": False,
                        "error": f"Tier restriction: {clean_msg}",
                        "error_code": "TIER_RESTRICTION",
                        "voice_name": voice_name,
                        "is_library_voice": True,
                    }
                elif probe_resp.status_code >= 400 and probe_resp.status_code not in (422,):
                    clean_msg = _message(probe_resp.text)
                    return {
                        "valid": False,
                        "error": f"Voice synthesis probe failed ({probe_resp.status_code}): {clean_msg}",
                        "error_code": f"PROBE_{probe_resp.status_code}",
                        "voice_name": voice_name
                    }

            # 2. Check model support if model_id provided
            mid = (model_id or "").strip()
            if mid:
                m_resp = client.get(f"{API}/models", headers=headers)
                if m_resp.status_code == 200:
                    models_list = m_resp.json()
                    m_dict = {m.get("model_id"): m for m in models_list if isinstance(m, dict)}
                    if mid in m_dict:
                        m_obj = m_dict[mid]
                        if not m_obj.get("can_do_text_to_speech", True):
                            return {
                                "valid": False,
                                "error": f"Model '{mid}' does not support text-to-speech.",
                                "error_code": "INVALID_MODEL"
                            }

            return {
                "valid": True,
                "voice_name": voice_name or vid or "Configured Voice",
                "voice_count": len(voices_data),
                "is_library_voice": is_library_voice,
                "model": mid or DEFAULT_MODEL,
                "details": f"Verified successfully with {len(voices_data)} voices available."
            }

    except Exception as e:
        return {
            "valid": False,
            "error": f"Network or connection error during ElevenLabs validation: {e}",
            "error_code": "NETWORK_ERROR"
        }


def test_voice_synthesis(api_key: str, voice_id: str, model_id: str = "", text: str = "") -> tuple[bool, bytes, str]:
    """Requests a short test sentence and returns (success, pcm_bytes, message)."""
    import httpx

    key = (api_key or "").strip()
    vid = (voice_id or "").strip()
    mid = (model_id or DEFAULT_MODEL).strip()
    phrase = (text or "").strip() or "Hello, this is your ElevenLabs voice test for JARVIS."

    if not key or not vid:
        return False, b"", "Missing API Key or Voice ID."

    url = f"{API}/text-to-speech/{vid}/stream"
    headers = {"xi-api-key": key, "Content-Type": "application/json"}
    payload = {
        "text": phrase,
        "model_id": mid,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
    }

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(url, headers=headers, params={"output_format": _PCM}, json=payload)
            if resp.status_code == 200:
                return True, resp.content, "Test audio generated successfully."
            
            # If PCM refused, try MP3
            if resp.status_code in (400, 422):
                resp_mp3 = client.post(url, headers=headers, params={"output_format": _MP3}, json=payload)
                if resp_mp3.status_code == 200:
                    pcm = _decode_mp3(resp_mp3.content)
                    return True, pcm, "Test audio generated successfully via MP3 decoding."
                err_msg = _message(resp_mp3.text)
                return False, b"", f"HTTP {resp_mp3.status_code}: {err_msg}"

            err_msg = _message(resp.text)
            return False, b"", f"HTTP {resp.status_code}: {err_msg}"
    except Exception as exc:
        return False, b"", f"Test voice request failed: {exc}"


class ElevenLabsTTS:
    def __init__(self, cfg: dict):
        self.key = (cfg.get("api_key") or "").strip()
        self.voice_id = (cfg.get("voice_id") or "").strip()
        self.model = (cfg.get("model") or DEFAULT_MODEL).strip()
        self.stability = _num(cfg.get("stability"), 0.5)
        self.similarity = _num(cfg.get("similarity"), 0.75)
        self.caps = dict(DEFAULT_CAPS)
        self.caps["audio_out"] = True
        self.base = API
        self._format: str | None = None

    # ── requests ─────────────────────────────────────────────────────────────
    def _headers(self) -> dict:
        return {"xi-api-key": self.key, "Content-Type": "application/json"}

    def _payload(self, text: str) -> dict:
        return {
            "text": text,
            "model_id": self.model,
            "voice_settings": {
                "stability": self.stability,
                "similarity_boost": self.similarity
            },
        }

    async def _stream_once(self, cl, text: str, fmt: str) -> AsyncIterator[bytes]:
        url = f"{API}/text-to-speech/{self.voice_id}/stream"
        async with cl.stream("POST", url, headers=self._headers(),
                             params={"output_format": fmt},
                             json=self._payload(text)) as r:
            if r.status_code >= 400:
                body = (await r.aread()).decode("utf-8", "replace")
                raise _HttpError(r.status_code, body)
            async for piece in r.aiter_bytes():
                if piece:
                    yield piece

    async def speak(self, text: str, voice: str = "") -> AsyncIterator[bytes]:
        import httpx

        if voice:
            self.voice_id = voice
        if not self.key:
            raise RuntimeError("no ElevenLabs API key is set")
        if not self.voice_id:
            raise RuntimeError("no ElevenLabs voice is chosen")
        text = (text or "").strip()
        if not text:
            return

        async with httpx.AsyncClient(timeout=60.0) as cl:
            fmt = self._format or _PCM
            try:
                async for piece in self._emit(cl, text, fmt):
                    yield piece
                self._format = fmt
                return
            except _HttpError as e:
                if fmt == _PCM and e.status in (400, 422):
                    self._format = _MP3
                else:
                    raise RuntimeError(f"{e.status} {_message(e.body)}") from None

            async for piece in self._emit(cl, text, _MP3):
                yield piece

    async def _emit(self, cl, text: str, fmt: str) -> AsyncIterator[bytes]:
        if fmt == _PCM:
            buf = b""
            async for piece in self._stream_once(cl, text, fmt):
                buf += piece
                while len(buf) >= 2400:
                    yield buf[:2400]
                    buf = buf[2400:]
            if buf:
                yield buf
            return

        mp3 = b""
        async for piece in self._stream_once(cl, text, fmt):
            mp3 += piece
        pcm = await asyncio.to_thread(_decode_mp3, mp3)
        for piece in audio.chunk(pcm):
            yield piece

    def voices(self) -> list[tuple[str, str]]:
        """(id, name) for every voice on the account."""
        import httpx
        with httpx.Client(timeout=15.0) as cl:
            r = cl.get(f"{API}/voices", headers={"xi-api-key": self.key})
            if r.status_code >= 400:
                raise RuntimeError(f"{r.status_code} {_message(r.text)}")
            return [(v.get("voice_id", ""), v.get("name", ""))
                    for v in (r.json().get("voices") or [])]

    def probe(self) -> tuple[bool, str]:
        if not self.key:
            return False, "No API key set."
        try:
            vs = self.voices()
        except Exception as e:
            msg = str(e)
            if "401" in msg:
                return False, "The key was refused."
            return False, msg[:120]
        if not self.voice_id:
            names = ", ".join(n for _, n in vs[:4])
            return False, f"Key works. Choose a voice — {len(vs)} available: {names}"
        name = next((n for i, n in vs if i == self.voice_id), self.voice_id)
        note = "" if find_spec("av") else \
            "  (MP3 fallback would need PyAV — only matters on a free tier)"
        return True, f"Ready: {name}, {self.model}{note}"


# ─────────────────────────────────────────────────────────────────────────────
class _HttpError(Exception):
    def __init__(self, status: int, body: str):
        super().__init__(f"{status}")
        self.status, self.body = status, body


def _num(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _message(body: str) -> str:
    """Extract clean error sentence from an ElevenLabs JSON error payload."""
    try:
        obj = json.loads(body)
        detail = obj.get("detail", obj)
        if isinstance(detail, dict):
            return str(detail.get("message") or detail.get("status") or detail)
        return str(detail)
    except Exception:
        return " ".join((body or "").split())[:200]


def _decode_mp3(data: bytes) -> bytes:
    """MP3 -> 24 kHz mono 16-bit PCM using PyAV or soundfile or miniaudio."""
    if find_spec("av") is not None:
        import io
        import av
        import numpy as np

        out = []
        with av.open(io.BytesIO(data)) as container:
            resampler = av.AudioResampler(format="s16", layout="mono", rate=audio.SPEAKER_RATE)
            for frame in container.decode(audio=0):
                for res in resampler.resample(frame):
                    out.append(res.to_ndarray().reshape(-1))
            for res in resampler.resample(None):
                out.append(res.to_ndarray().reshape(-1))
        if not out:
            return b""
        return np.concatenate(out).astype("<i2").tobytes()

    raise RuntimeError(
        "Raw PCM was not accepted by the tier and no MP3 decoder (PyAV) is installed. "
        "Run: pip install av"
    )


def _make(cfg: dict) -> ElevenLabsTTS:
    return ElevenLabsTTS(cfg)


PROVIDER = {
    "id": "elevenlabs",
    "kind": "tts",
    "label": "ElevenLabs",
    "hint": "One voice that speaks every language — needs a key and a connection",
    "requires": ("httpx",),
    "catalog": (
        {"id": "elevenlabs", "label": "ElevenLabs",
         "note": "cloud · one voice speaks every language", "local": False,
         "values": {}},
    ),
    "needs": (
        Field("api_key", "API key", kind="secret",
              hint="elevenlabs.io -> Profile -> API key"),
        Field("voice_id", "Voice", kind="choice", choices=(),
              hint="Press LIST to read the voices on your account"),
        Field("model", "Model", kind="choice", choices=MODELS,
              default=DEFAULT_MODEL, required=False,
              hint="flash is the quickest and still multilingual"),
        Field("stability", "Stability", kind="number", default=0.5,
              required=False, advanced=True, hint="0 to 1"),
        Field("similarity", "Similarity", kind="number", default=0.75,
              required=False, advanced=True, hint="0 to 1"),
    ),
    "caps": {"audio_out": True},
    "factory": _make,
}


def available() -> bool:
    return find_spec("httpx") is not None
