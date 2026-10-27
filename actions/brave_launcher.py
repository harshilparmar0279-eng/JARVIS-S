"""
Brave browser launcher for JARVIS.

Ensures YouTube and explicit Brave commands ALWAYS open in the Brave browser,
supporting system-wide, per-user, and registry-based installations on Windows,
macOS, and Linux. Never falls back to Chrome or Windows default browser for YouTube.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional

_OS = platform.system()


def find_brave_executable() -> Optional[str]:
    """Find installed Brave executable across all standard system and user paths."""
    if _OS == "Windows":
        # 1. Standard install paths
        prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        prog_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local_app_data = os.environ.get("LOCALAPPDATA", "")

        candidates = [
            Path(prog_files) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
            Path(prog_files_x86) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
            Path(local_app_data) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
        ]
        for p in candidates:
            if p.is_file():
                return str(p)

        # 2. Windows Registry
        try:
            import winreg
            reg_paths = [
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\brave.exe",
                r"SOFTWARE\Clients\StartMenuInternet\Brave\shell\open\command",
                r"SOFTWARE\Clients\StartMenuInternet\Brave-Browser\shell\open\command",
            ]
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                for subkey in reg_paths:
                    try:
                        k = winreg.OpenKey(hive, subkey)
                        val, _ = winreg.QueryValueEx(k, "")
                        winreg.CloseKey(k)
                        if val:
                            exe = val.strip().strip('"').split('"')[0].split(" --")[0].strip()
                            if exe and Path(exe).is_file():
                                return exe
                    except Exception:
                        continue
        except Exception:
            pass

        # 3. PATH
        resolved = shutil.which("brave.exe") or shutil.which("brave")
        if resolved:
            return resolved

    elif _OS == "Darwin":
        mac_paths = [
            Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
            Path.home() / "Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ]
        for p in mac_paths:
            if p.is_file():
                return str(p)
        resolved = shutil.which("brave")
        if resolved:
            return resolved

    elif _OS == "Linux":
        for b in ("brave-browser", "brave"):
            resolved = shutil.which(b)
            if resolved:
                return resolved

    return None


def is_youtube_target(url_or_query: str) -> bool:
    """Return True if the target URL or query is YouTube."""
    if not url_or_query:
        return False
    t = url_or_query.strip().lower()
    if any(k in t for k in ("youtube.com", "youtu.be", "m.youtube.com")):
        return True
    # Natural words / queries
    if t in ("youtube", "open youtube", "youtube kholo", "brave mein youtube kholo"):
        return True
    return False


def open_in_brave(url: str = "https://www.youtube.com/") -> tuple[bool, str]:
    """Launch Brave directly with the given URL (prefers existing session).
    Does NOT use the Windows default URL handler.
    """
    target_url = url.strip() or "https://www.youtube.com/"
    if not (target_url.startswith("http://") or target_url.startswith("https://")):
        target_url = "https://" + target_url

    exe = find_brave_executable()
    if not exe:
        return (
            False,
            "Brave browser is not installed or could not be found on this system. "
            "Please install Brave browser to open YouTube in Brave."
        )

    try:
        # Launch directly without shell; Chromium browsers on Windows attach to existing session
        subprocess.Popen(
            [exe, target_url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True, f"Opened {target_url} in Brave."
    except Exception as exc:
        return False, f"Failed to launch Brave ({exe}): {exc}"
