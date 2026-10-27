"""
WhatsApp actions for JARVIS: contact search, messaging, audio calls, and video calls.

Auto-discovered by core/action_loader.py. Uses verified desktop driver from plugins/_whatsapp_core.py.
"""
from __future__ import annotations

import os
import platform
import threading
from typing import Optional

from core import outcome
from plugins import _whatsapp_core as wa

_OS = platform.system()


def _log(player, message: str) -> None:
    if player and hasattr(player, "write_log"):
        try:
            player.write_log(message)
        except Exception:
            pass


def _say(player, instruction: str) -> None:
    if player and hasattr(player, "request_say"):
        try:
            player.request_say(instruction)
        except Exception:
            pass


def whatsapp_actions(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = (params.get("action") or "search").strip().lower()
    contact_name = (params.get("contact_name") or params.get("receiver") or "").strip()
    message_text = (params.get("message") or params.get("message_text") or "").strip()

    if not contact_name:
        return outcome.failed("whatsapp_actions", "No contact name was specified.")

    driver, why = wa.get()
    if driver is None:
        return outcome.failed("whatsapp_actions", f"WhatsApp automation unavailable: {why}")

    # 1. Contact Search
    if action == "search":
        _log(player, f"JARVIS: Searching for {contact_name} in WhatsApp…")
        ok, detail = driver.search_contact(contact_name)
        if ok:
            _log(player, f"JARVIS: {detail}")
            return outcome.done("whatsapp_actions", action="search", contact=contact_name, verified=True, detail=detail)
        else:
            _log(player, f"JARVIS: {detail}")
            _say(player, f"Tell the user in one short sentence: could not find {contact_name} in WhatsApp.")
            return outcome.failed("whatsapp_actions", detail, action="search", contact=contact_name)

    # 2. Send Message
    elif action == "send_message":
        if not message_text:
            msg = "Please specify what message you want to send."
            _log(player, f"JARVIS: {msg}")
            _say(player, "What message would you like me to send?")
            return outcome.failed("whatsapp_actions", msg, action="send_message", contact=contact_name, needs_message=True)

        _log(player, f"JARVIS: Sending message to {contact_name}…")
        ok, detail = driver.send_message_to(contact_name, message_text)
        if ok:
            _log(player, f"JARVIS: Sent to {contact_name}: {message_text}")
            return outcome.done("whatsapp_actions", action="send_message", contact=contact_name, verified=True, message=message_text)
        else:
            _log(player, f"JARVIS: {detail}")
            _say(player, f"Tell the user in one short sentence: message to {contact_name} failed - {detail}")
            return outcome.failed("whatsapp_actions", detail, action="send_message", contact=contact_name)

    # 3. Audio Call
    elif action in ("audio_call", "call", "voice_call"):
        _log(player, f"JARVIS: Initiating audio call to {contact_name}…")
        ok, detail = driver.initiate_call(contact_name, video=False)
        if ok:
            _log(player, f"JARVIS: {detail}")
            return outcome.done("whatsapp_actions", action="audio_call", contact=contact_name, status="ringing", verified=True)
        else:
            _log(player, f"JARVIS: {detail}")
            _say(player, f"Tell the user: audio call to {contact_name} failed - {detail}")
            return outcome.failed("whatsapp_actions", detail, action="audio_call", contact=contact_name)

    # 4. Video Call
    elif action in ("video_call", "video"):
        _log(player, f"JARVIS: Initiating video call to {contact_name}…")
        ok, detail = driver.initiate_call(contact_name, video=True)
        if ok:
            _log(player, f"JARVIS: {detail}")
            return outcome.done("whatsapp_actions", action="video_call", contact=contact_name, status="ringing", verified=True)
        else:
            _log(player, f"JARVIS: {detail}")
            _say(player, f"Tell the user: video call to {contact_name} failed - {detail}")
            return outcome.failed("whatsapp_actions", detail, action="video_call", contact=contact_name)

    else:
        return outcome.failed("whatsapp_actions", f"Unknown action: '{action}'. Use search, send_message, audio_call, or video_call.")


TOOL = {
    "name": "whatsapp_actions",
    "description": (
        "Controls WhatsApp on this computer: search for a contact, open their chat, "
        "send a text message, start a voice/audio call, or start a video call. "
        "Use whenever the user asks to search for someone on WhatsApp ('WhatsApp mein XYZ ko search karo'), "
        "send a WhatsApp message ('WhatsApp par message bhejo'), make a WhatsApp call ('WhatsApp call karo'), "
        "or make a video call ('WhatsApp video call karo'). "
        "If the user asks to message someone but has not provided the message content, ask them what they want to say."
    ),
    "tier": "core",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "search | send_message | audio_call | video_call"
            },
            "contact_name": {
                "type": "STRING",
                "description": "The person or contact name on WhatsApp"
            },
            "message": {
                "type": "STRING",
                "description": "The exact message content to send (required for send_message)"
            }
        },
        "required": ["action", "contact_name"]
    },
    "handler": whatsapp_actions,
}
