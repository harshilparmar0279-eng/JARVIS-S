"""
run_phone_app.py — One-click runner for JARVIS Phone App via Free Cloudflare Tunnel
"""

import os
import re
import sys
import time
import socket
import asyncio
import threading
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CLOUDFLARED_EXE = BASE_DIR / "cloudflared.exe"


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def ensure_dashboard_running():
    """Ensure dashboard server is listening on port 8000."""
    if is_port_in_use(8000):
        print("[Dashboard] Port 8000 is already active (JARVIS is running).")
        return None

    print("[Dashboard] Starting JARVIS Dashboard backend on port 8000...")
    from dashboard.server import DashboardServer
    srv = DashboardServer()

    def run_srv():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(srv.serve())

    t = threading.Thread(target=run_srv, daemon=True)
    t.start()
    time.sleep(2)
    return srv


def print_qr_code(url: str):
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        print("\n--- SCAN WITH PHONE CAMERA ---")
        qr.print_ascii(invert=True)
        print("------------------------------\n")
    except Exception:
        pass


def main():
    if not CLOUDFLARED_EXE.exists():
        print(f"[Error] cloudflared.exe not found at {CLOUDFLARED_EXE}")
        sys.exit(1)

    ensure_dashboard_running()

    print("[Cloudflare] Launching secure tunnel to port 8000...")
    cmd = [str(CLOUDFLARED_EXE), "tunnel", "--url", "http://localhost:8000"]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="ignore",
    )

    tunnel_url = None
    url_regex = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

    for line in proc.stdout:
        match = url_regex.search(line)
        if match:
            tunnel_url = match.group(0)
            break

    if tunnel_url:
        print("\n" + "=" * 65)
        print("   JARVIS PHONE APP IS READY FOR 5G / REMOTE USE!   ")
        print("=" * 65)
        print(f"\n   LINK: {tunnel_url}\n")
        print("=" * 65)
        print("HOW TO INSTALL AS SEPARATE APP ON PHONE:")
        print("1. Phone ke Chrome ya Brave browser me yeh link kholein.")
        print("2. Browser ke menu (⋮) me jakar 'Install app' ya 'Add to Home screen' dabayein.")
        print("3. Phone par JARVIS ka alag app icon ban jayega!")
        print("=" * 65 + "\n")
        print_qr_code(tunnel_url)
        print("[Status] Tunnel is LIVE! Press Ctrl+C to stop.\n")
    else:
        print("[Warning] Could not extract tunnel URL automatically.")

    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\n[Status] Stopping tunnel...")
        proc.terminate()


if __name__ == "__main__":
    main()
