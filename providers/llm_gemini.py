"""
Google Gemini language model provider for the pipeline engine.

Enables using Google Gemini (via google-genai SDK and existing Gemini API Key)
in Modular Pipeline mode together with Whisper STT and ElevenLabs TTS.
"""
from __future__ import annotations

import asyncio
from importlib.util import find_spec
from typing import Any, AsyncIterator, Optional

from .base import DEFAULT_CAPS, Field, FunctionCall

MODELS = (
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
)
DEFAULT_MODEL = "gemini-3.5-flash-lite"


class GeminiLLM:
    """Speaks to Google Gemini via the official google-genai SDK."""

    def __init__(self, cfg: dict):
        from google import genai
        from memory.config_manager import get_gemini_key

        key = (cfg.get("api_key") or "").strip()
        if not key:
            key = get_gemini_key() or ""
        self.key = key
        self.model = (cfg.get("model") or DEFAULT_MODEL).strip()
        self._client = genai.Client(api_key=self.key)

        self.caps = dict(DEFAULT_CAPS)
        self.caps.update({
            "tools": bool(cfg.get("tools", True)),
            "tool_format": "gemini",
            "vision": bool(cfg.get("vision", True)),
            "max_tools": None,
            "max_tool_chars": None,
        })

    def _convert_messages(self, messages: list[dict]):
        from google.genai import types

        contents = []
        system_instruction = None

        for m in messages:
            role = m.get("role")
            content = m.get("content")

            if role == "system":
                system_instruction = content if isinstance(content, str) else str(content)
                continue

            if role == "tool":
                # Function response
                fn_name = m.get("name") or m.get("tool_call_id") or "tool"
                res_data = {"result": content} if isinstance(content, str) else (content or {})
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_function_response(name=fn_name, response=res_data)]
                    )
                )
                continue

            gemini_role = "user" if role == "user" else "model"
            parts = []

            # Handle assistant tool calls
            tool_calls = m.get("tool_calls")
            if tool_calls:
                for tc in tool_calls:
                    fn = tc.get("function") if isinstance(tc, dict) else None
                    name = fn.get("name") if fn else getattr(tc, "name", "")
                    args = fn.get("arguments") if fn else getattr(tc, "args", {})
                    if isinstance(args, str):
                        try:
                            import json
                            args = json.loads(args)
                        except Exception:
                            args = {"raw": args}
                    parts.append(types.Part.from_function_call(name=name, args=args or {}))

            if isinstance(content, str) and content:
                parts.append(types.Part.from_text(text=content))
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, str):
                        parts.append(types.Part.from_text(text=item))
                    elif isinstance(item, dict):
                        if item.get("type") == "text":
                            parts.append(types.Part.from_text(text=item.get("text", "")))
                        elif item.get("type") == "image_url":
                            url = item.get("image_url", {}).get("url", "")
                            if url.startswith("data:"):
                                meta, _, b64 = url.partition(",")
                                mime = meta.split(";")[0].replace("data:", "")
                                import base64
                                parts.append(types.Part.from_bytes(data=base64.b64decode(b64), mime_type=mime))

            if parts:
                contents.append(types.Content(role=gemini_role, parts=parts))

        return contents, system_instruction

    async def chat(self, messages: list[dict], tools: list = None) -> AsyncIterator[dict]:
        from google.genai import types

        contents, system_instruction = self._convert_messages(messages)
        if not contents:
            return

        gen_cfg_args: dict[str, Any] = {}
        if system_instruction:
            gen_cfg_args["system_instruction"] = system_instruction

        if tools and self.caps.get("tools"):
            gen_cfg_args["tools"] = [{"function_declarations": tools}]

        config = types.GenerateContentConfig(**gen_cfg_args) if gen_cfg_args else None

        candidates = [self.model]
        for m in MODELS:
            if m not in candidates:
                candidates.append(m)

        last_exc = None
        for cand in candidates:
            try:
                response_stream = await self._client.aio.models.generate_content_stream(
                    model=cand,
                    contents=contents,
                    config=config,
                )
                yielded = False
                async for chunk in response_stream:
                    if chunk.function_calls:
                        fn_calls = [
                            FunctionCall(id=fc.id or fc.name, name=fc.name, args=dict(fc.args or {}))
                            for fc in chunk.function_calls
                        ]
                        yield {"tool_calls": fn_calls}
                        yielded = True

                    if chunk.text:
                        yield {"text": chunk.text}
                        yielded = True
                return
            except Exception as e:
                last_exc = e
                if 'yielded' in locals() and yielded:
                    raise
                continue

        if last_exc:
            raise last_exc

    def models(self, timeout: float = 6.0) -> list[str]:
        return list(MODELS)

    def can_see(self) -> bool:
        return True


def _make(cfg: dict) -> GeminiLLM:
    return GeminiLLM(cfg)


PROVIDER = {
    "id": "gemini",
    "kind": "llm",
    "label": "Google Gemini",
    "hint": "Native Gemini intelligence · uses your existing Gemini API key",
    "requires": ("google.genai",),
    "catalog": (
        {"id": "gemini", "label": "Google Gemini",
         "note": "cloud · high speed · uses saved Gemini key", "local": False,
         "values": {"model": DEFAULT_MODEL}},
    ),
    "needs": (
        Field("api_key", "API key", kind="secret", required=False,
              hint="Leave blank to use your configured Gemini API key"),
        Field("model", "Model", kind="choice", choices=MODELS,
              default=DEFAULT_MODEL, required=False,
              hint="Fastest model for conversational voice"),
        Field("tools", "Enable tools", kind="bool", default=True, required=False, advanced=True),
    ),
    "caps": {"tools": True, "tool_format": "gemini", "vision": True},
    "factory": _make,
}


def available() -> bool:
    return find_spec("google.genai") is not None
