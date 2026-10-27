"""
core/desktop_shortcut.py — Idempotent Windows Desktop Shortcut Creator for JARVIS.

Detects Desktop dynamically, finds the venv pythonw.exe (or python.exe),
config/jarvis.ico, and creates or updates a Desktop shortcut named 'Jarvis.lnk'.
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def get_desktop_dir() -> Optional[Path]:
    """Dynamically detects the user's Windows Desktop directory without hardcoding."""
    if platform.system() != "Windows":
        d = Path.home() / "Desktop"
        return d if d.is_dir() else None

    # 1. Query Windows User Shell Folders registry (supports OneDrive Desktop redirection)
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        )
        val, _ = winreg.QueryValueEx(key, "Desktop")
        winreg.CloseKey(key)
        expanded = os.path.expandvars(val)
        if Path(expanded).is_dir():
            return Path(expanded)
    except Exception:
        pass

    # 2. Check USERPROFILE env var
    user_prof = os.environ.get("USERPROFILE")
    if user_prof:
        d = Path(user_prof) / "Desktop"
        if d.is_dir():
            return d

    # 3. Path.home() / "Desktop"
    d = Path.home() / "Desktop"
    if d.is_dir():
        return d

    return None


def find_target_executable(base_dir: Path) -> Path:
    """Finds the best python interpreter in venv or system."""
    venv_pythonw = base_dir / ".venv" / "Scripts" / "pythonw.exe"
    if venv_pythonw.is_file():
        return venv_pythonw

    venv_python = base_dir / ".venv" / "Scripts" / "python.exe"
    if venv_python.is_file():
        return venv_python

    # Fallback to current sys.executable or sibling pythonw
    cur_exec = Path(sys.executable)
    cur_w = cur_exec.parent / "pythonw.exe"
    if cur_w.is_file():
        return cur_w

    return cur_exec


def create_desktop_shortcut(force: bool = False) -> tuple[bool, str]:
    """
    Creates or updates the Windows desktop shortcut for JARVIS.
    Idempotent: skips re-creating if valid shortcut already exists and force=False.
    Returns: (success: bool, message: str)
    """
    if platform.system() != "Windows":
        return False, "Desktop shortcuts are only supported on Windows."

    desktop = get_desktop_dir()
    if not desktop or not desktop.is_dir():
        return False, "Could not locate Desktop directory."

    shortcut_file = desktop / "Jarvis.lnk"
    base_dir = get_base_dir()
    entry_point = base_dir / "main.py"
    target_exe = find_target_executable(base_dir)

    icon_path = base_dir / "config" / "jarvis.ico"
    if not icon_path.is_file():
        icon_path = target_exe  # Fallback to exe icon if jarvis.ico is missing

    # Idempotency check: if shortcut already exists and force is False
    if shortcut_file.is_file() and not force:
        try:
            cmd = [
                "powershell", "-NoProfile", "-Command",
                f"$w = New-Object -ComObject WScript.Shell; $s = $w.CreateShortcut('{str(shortcut_file)}'); Write-Output $s.TargetPath"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and str(target_exe).lower() in res.stdout.strip().lower():
                return True, f"Desktop shortcut already exists at {shortcut_file}"
        except Exception:
            pass

    # Build PowerShell script to create shortcut via WScript.Shell
    ps_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{str(shortcut_file)}')
$Shortcut.TargetPath = '{str(target_exe)}'
$Shortcut.Arguments = '"{str(entry_point)}"'
$Shortcut.WorkingDirectory = '{str(base_dir)}'
$Shortcut.IconLocation = '{str(icon_path)},0'
$Shortcut.Description = 'JARVIS AI Desktop Assistant'
$Shortcut.Save()
"""
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=10
        )
        if res.returncode == 0 and shortcut_file.is_file():
            return True, f"Jarvis Desktop shortcut successfully created at {shortcut_file}"
        else:
            err = res.stderr.strip() or res.stdout.strip()
            return False, f"Failed to create desktop shortcut: {err}"
    except Exception as e:
        return False, f"Exception while creating desktop shortcut: {e}"
