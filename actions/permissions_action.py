"""
actions/permissions_action.py — Check and report hardware permissions and system device access.
"""
from __future__ import annotations

from core.permission_checker import check_all_permissions, open_settings_uri

TOOL = {
    "name": "check_device_permissions",
    "description": "Verify microphone, speaker, and camera access and Windows privacy permissions. Reports any blocked devices and provides direct instructions to resolve them.",
    "parameters": {
        "type": "object",
        "properties": {
            "open_settings_if_blocked": {
                "type": "boolean",
                "description": "If true, automatically opens the relevant Windows Privacy Settings page if a permission is missing."
            }
        },
        "required": []
    }
}


def execute(open_settings_if_blocked: bool = False) -> str:
    res = check_all_permissions()
    lines = []
    if res["all_ok"]:
        return "All necessary permissions (Microphone, Audio Output, and Camera) are active and functioning properly, sir."

    lines.append("Permission and Device Diagnostics:")
    for comp in ("microphone", "speaker", "camera"):
        item = res.get(comp, {})
        status = "✓ OK" if item.get("ok") else "✗ BLOCKED"
        lines.append(f"- {comp.capitalize()}: {status} — {item.get('message', '')}")
        if not item.get("ok") and item.get("guidance"):
            lines.append(f"  Action: {item.get('guidance')}")
            if open_settings_if_blocked and item.get("settings_uri"):
                open_settings_uri(item["settings_uri"])

    return "\n".join(lines)
