"""
core/permission_checker.py — Verify system access, hardware devices, and Windows privacy permissions.

Covers:
- Microphone permission and device capture readiness
- Audio output / speaker availability
- Camera access and OpenCV capture readiness
- Windows Settings deep links for missing permissions
"""
from __future__ import annotations

import os
import platform
import subprocess
import threading
from typing import Dict, Any


def open_settings_uri(uri: str) -> bool:
    """Open a Windows ms-settings: URI to guide the user directly to the relevant settings page."""
    if platform.system().lower() != "windows":
        return False
    try:
        os.startfile(uri)
        return True
    except Exception:
        try:
            subprocess.run(["cmd", "/c", "start", uri], check=False, shell=True)
            return True
        except Exception:
            return False


def check_microphone_access() -> dict[str, Any]:
    """Test whether microphone devices are detected and capture stream can be opened."""
    try:
        import sounddevice as sd
    except ImportError:
        return {
            "status": "error",
            "ok": False,
            "message": "sounddevice library is not installed.",
            "guidance": "Install required dependencies: pip install sounddevice"
        }

    try:
        devs = sd.query_devices()
        input_devs = [d for d in devs if d.get("max_input_channels", 0) > 0]
        if not input_devs:
            return {
                "status": "missing_hardware",
                "ok": False,
                "message": "No microphone or input audio device detected by the operating system.",
                "guidance": "Connect a microphone or headset and verify Windows Sound Settings (ms-settings:sound).",
                "settings_uri": "ms-settings:sound"
            }

        # Attempt opening a momentary input stream
        with sd.InputStream(channels=1, samplerate=16000, blocksize=512):
            pass

        return {
            "status": "ok",
            "ok": True,
            "message": f"Microphone access verified ({len(input_devs)} input device(s) detected).",
            "device_count": len(input_devs)
        }
    except Exception as e:
        err_str = str(e).lower()
        if "access" in err_str or "permission" in err_str or "unauthorized" in err_str:
            return {
                "status": "permission_denied",
                "ok": False,
                "message": "Microphone access blocked by Windows Privacy Settings.",
                "guidance": "Go to Windows Settings -> Privacy & security -> Microphone. Turn ON 'Microphone access' and ensure desktop apps are allowed.",
                "settings_uri": "ms-settings:privacy-microphone"
            }
        return {
            "status": "stream_error",
            "ok": False,
            "message": f"Could not open microphone stream: {e}",
            "guidance": "Check Windows Sound Settings -> Input device volume and permissions (ms-settings:sound).",
            "settings_uri": "ms-settings:sound"
        }


def check_audio_output() -> dict[str, Any]:
    """Test whether audio output devices are detected and playback stream can be opened."""
    try:
        import sounddevice as sd
    except ImportError:
        return {
            "status": "error",
            "ok": False,
            "message": "sounddevice library is not installed.",
            "guidance": "Install required dependencies: pip install sounddevice"
        }

    try:
        devs = sd.query_devices()
        output_devs = [d for d in devs if d.get("max_output_channels", 0) > 0]
        if not output_devs:
            return {
                "status": "missing_hardware",
                "ok": False,
                "message": "No speaker or output audio device detected.",
                "guidance": "Connect speakers or headphones and check Windows Sound Settings (ms-settings:sound).",
                "settings_uri": "ms-settings:sound"
            }

        with sd.OutputStream(channels=1, samplerate=24000, blocksize=512):
            pass

        return {
            "status": "ok",
            "ok": True,
            "message": f"Audio output verified ({len(output_devs)} output device(s) detected).",
            "device_count": len(output_devs)
        }
    except Exception as e:
        return {
            "status": "stream_error",
            "ok": False,
            "message": f"Could not open audio output stream: {e}",
            "guidance": "Check Windows Sound Settings -> Output device volume and exclusive mode settings (ms-settings:sound).",
            "settings_uri": "ms-settings:sound"
        }


def check_camera_access() -> dict[str, Any]:
    """Test whether OpenCV can open camera capture device index 0."""
    try:
        import cv2
    except ImportError:
        return {
            "status": "error",
            "ok": False,
            "message": "OpenCV (cv2) is not installed.",
            "guidance": "Install OpenCV with: pip install opencv-python"
        }

    try:
        backend = cv2.CAP_DSHOW if platform.system().lower() == "windows" else cv2.CAP_ANY
        cap = cv2.VideoCapture(0, backend)
        if not cap.isOpened():
            cap.release()
            return {
                "status": "inaccessible",
                "ok": False,
                "message": "Camera index 0 could not be opened or is blocked by privacy settings.",
                "guidance": "Go to Windows Settings -> Privacy & security -> Camera. Ensure 'Camera access' is ON and desktop apps are allowed.",
                "settings_uri": "ms-settings:privacy-webcam"
            }

        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None or frame.size == 0:
            return {
                "status": "no_frame",
                "ok": False,
                "message": "Camera opened but returned no video frame (may be in use by another application).",
                "guidance": "Close other applications using the webcam and verify camera settings (ms-settings:privacy-webcam).",
                "settings_uri": "ms-settings:privacy-webcam"
            }

        return {
            "status": "ok",
            "ok": True,
            "message": "Camera access and frame capture verified successfully."
        }
    except Exception as e:
        return {
            "status": "error",
            "ok": False,
            "message": f"Error accessing camera: {e}",
            "guidance": "Check Windows Settings -> Privacy & security -> Camera (ms-settings:privacy-webcam).",
            "settings_uri": "ms-settings:privacy-webcam"
        }


def check_all_permissions() -> dict[str, Any]:
    """Run full diagnostic check across microphone, audio output, and camera."""
    mic = check_microphone_access()
    spk = check_audio_output()
    cam = check_camera_access()

    all_ok = mic.get("ok", False) and spk.get("ok", False) and cam.get("ok", False)

    return {
        "all_ok": all_ok,
        "microphone": mic,
        "speaker": spk,
        "camera": cam,
    }
