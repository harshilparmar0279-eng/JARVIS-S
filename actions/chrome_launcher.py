"""
Chrome profile resolution and launcher for JARVIS.

Discovers local Google Chrome profiles from Chrome's User Data metadata (Local State).
Maintains persistent account-to-profile directory mappings and requires selecting
the Google account when opening Chrome unless specified.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional

_OS = platform.system()

def _get_base_dir() -> Path:
    return Path(__file__).resolve().parent.parent

CONFIG_PATH = _get_base_dir() / "config" / "chrome_profiles.json"


def find_chrome_executable() -> Optional[str]:
    """Find installed Chrome executable across standard paths and registry."""
    if _OS == "Windows":
        prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        prog_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local_app_data = os.environ.get("LOCALAPPDATA", "")

        candidates = [
            Path(prog_files) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(prog_files_x86) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(local_app_data) / "Google" / "Chrome" / "Application" / "chrome.exe",
        ]
        for p in candidates:
            if p.is_file():
                return str(p)

        try:
            import winreg
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    k = winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")
                    val, _ = winreg.QueryValueEx(k, "")
                    winreg.CloseKey(k)
                    if val and Path(val).is_file():
                        return val
                except Exception:
                    pass
        except Exception:
            pass

        return shutil.which("chrome.exe") or shutil.which("chrome")

    elif _OS == "Darwin":
        mac_path = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        if mac_path.is_file():
            return str(mac_path)
        return shutil.which("google-chrome") or shutil.which("chrome")

    elif _OS == "Linux":
        for b in ("google-chrome", "google-chrome-stable", "chromium-browser", "chromium"):
            resolved = shutil.which(b)
            if resolved:
                return resolved

    return None


def get_chrome_user_data_dir() -> Path:
    if _OS == "Windows":
        return Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data"
    elif _OS == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
    else:
        return Path.home() / ".config" / "google-chrome"


def discover_chrome_profiles() -> list[dict]:
    """Inspect Local State in Chrome's User Data directory and extract profile info.
    Does NOT read sensitive user credentials, cookies, or history.
    """
    user_data = get_chrome_user_data_dir()
    local_state_file = user_data / "Local State"
    profiles = []

    if local_state_file.is_file():
        try:
            data = json.loads(local_state_file.read_text(encoding="utf-8"))
            info_cache = data.get("profile", {}).get("info_cache", {})
            for dir_name, info in info_cache.items():
                if not isinstance(info, dict):
                    continue
                email = (info.get("user_name") or "").strip()
                name = (info.get("name") or "").strip()
                gaia_name = (info.get("gaia_name") or "").strip()
                profiles.append({
                    "dir_name": dir_name,
                    "email": email,
                    "name": name,
                    "gaia_name": gaia_name,
                    "display": f"{name} ({email})" if email and name and email.lower() != name.lower() else (email or name or dir_name)
                })
        except Exception as e:
            print(f"[ChromeLauncher] Error reading Local State: {e}")

    # Fallback to directory scan if Local State wasn't parseable
    if not profiles and user_data.is_dir():
        for d in user_data.iterdir():
            if d.is_dir() and (d.name == "Default" or d.name.startswith("Profile ")):
                profiles.append({
                    "dir_name": d.name,
                    "email": "",
                    "name": d.name,
                    "gaia_name": "",
                    "display": d.name
                })

    # Save to persistent mapping file
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps({"profiles": profiles}, indent=2), encoding="utf-8")
    except Exception:
        pass

    return profiles


def match_profile(query: str, profiles: Optional[list[dict]] = None) -> Optional[dict]:
    """Match account query (email, name, or dir_name) against available profiles."""
    if not query:
        return None
    q = query.strip().lower()
    if not profiles:
        profiles = discover_chrome_profiles()

    # 1. Exact email match
    for p in profiles:
        if p.get("email") and p["email"].lower() == q:
            return p

    # 2. Email prefix / username match (e.g. 'harshilparmar0279' matching 'harshilparmar0279@gmail.com')
    for p in profiles:
        em = p.get("email", "").lower()
        if em and ("@" in em) and (em.split("@")[0] == q):
            return p

    # 3. Exact profile name match
    for p in profiles:
        if p.get("name") and p["name"].lower() == q:
            return p

    # 4. Exact directory name match
    for p in profiles:
        if p.get("dir_name") and p["dir_name"].lower() == q:
            return p

    # 5. Substring match on email or name
    for p in profiles:
        if q in p.get("email", "").lower() or q in p.get("name", "").lower():
            return p

    return None


def format_available_accounts(profiles: list[dict]) -> str:
    lines = []
    for p in profiles:
        lines.append(f"• {p['display']}")
    return "\n".join(lines)


def launch_chrome(profile_dir: str, url: str = "") -> tuple[bool, str]:
    """Launch Chrome with the given profile directory and destination URL."""
    from core.command_lock import sync_command_mutex

    exe = find_chrome_executable()
    if not exe:
        return False, "Google Chrome is not installed or executable not found."

    clean_url = (url or "").strip()
    if clean_url.lower() in ("about:blank", "blank"):
        clean_url = ""

    args = [exe]
    if profile_dir:
        args.append(f"--profile-directory={profile_dir}")
    if clean_url:
        args.append(clean_url)

    try:
        with sync_command_mutex(timeout=15.0):
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            dest_label = clean_url if clean_url else "default session"
            return True, f"Opened Chrome (profile: {profile_dir or 'default'}) with {dest_label}."
    except Exception as e:
        return False, f"Failed to launch Chrome: {e}"
