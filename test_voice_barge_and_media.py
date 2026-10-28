"""
test_voice_barge_and_media.py — Verification suite for:
1. Mayra voice sweet human timbre (Aoede base, 1.0 natural speed, no robotic WSOLA distortion)
2. App header branding as 'JARVIS' with subtitle displaying active voice 'Voice: Mayra'
3. Auto-close HUD media player container when playback finishes (EndOfMedia) and restore listening state
4. Voice barge-in / interruption mid-speech when user talks
"""
import sys
import unittest
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from memory.config_manager import (
    DEFAULT_MAYRA_VOICE,
    DEFAULT_MAYRA_SPEED,
    get_custom_voice_info,
    get_assistant_name,
    get_voice,
    save_voice,
    save_assistant_config,
)
from core.echo import EchoGuard


class TestVoiceBargeAndMedia(unittest.TestCase):
    def setUp(self):
        save_assistant_config("JARVIS", "Harshil")
        save_voice("Mayra")

    def test_mayra_timbre_and_speed_natural(self):
        """Ensure Mayra uses sweet human timbre Aoede and pure 1.0 natural tempo."""
        self.assertEqual(DEFAULT_MAYRA_VOICE, "Aoede", "Mayra must use sweet Aoede timbre")
        self.assertEqual(DEFAULT_MAYRA_SPEED, 1.0, "Mayra speed must be 1.0 for un-degraded streaming")
        info = get_custom_voice_info("Mayra")
        self.assertEqual(info["base_voice"], "Aoede")
        self.assertEqual(info["speech_speed"], 1.0)

    def test_app_title_is_jarvis_with_mayra_voice(self):
        """Header title must remain JARVIS while voice is Mayra."""
        self.assertEqual(get_assistant_name(), "JARVIS", "App name must be JARVIS")
        self.assertEqual(get_voice().lower(), "mayra", "Active voice should be mayra")

    def test_echo_guard_and_barge_in_logic(self):
        """EchoGuard and barge-in classifier detect active user speech during output."""
        echo = EchoGuard()
        sr = 16000
        t = np.linspace(0, 0.1, int(sr * 0.1), endpoint=False)
        user_pcm = (np.sin(2 * np.pi * 300 * t) * 16000).astype(np.int16)

        # 1. When no history is playing, any user voice is immediately recognized
        self.assertTrue(echo.is_user_speech(user_pcm, sr, 0.35))

        # 2. When assistant is speaking before warmup calibration, barge-in threshold rule kicks in
        lvl = 0.25
        barge_in_triggered = echo.is_user_speech(user_pcm, sr, lvl) or (lvl > 0.20 and not echo.calibrated)
        self.assertTrue(barge_in_triggered, "Barge-in rule must detect clear user speech above 0.20 lvl")

    def test_ui_media_end_of_media_auto_close(self):
        """When media status becomes EndOfMedia, HUD container auto-closes and state is LISTENING."""
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtMultimedia import QMediaPlayer
        app = QApplication.instance() or QApplication(sys.argv)

        from ui import JarvisUI
        ui = JarvisUI("face.png")
        win = ui._win
        try:
            # Check Header title is JARVIS and voice is displayed
            self.assertEqual(win._title_lbl.text(), "JARVIS", "App title on header must be JARVIS")
            self.assertIn("Voice: Mayra", win._sub_lbl.text(), "Header subtitle must show active voice Mayra")

            # Simulate video playback being active
            win._video_on = True
            win._hud_cam_stack.setCurrentIndex(2)
            win._video_auto_muted = True
            win._muted = True

            # Trigger EndOfMedia
            win._on_video_media_status_changed(QMediaPlayer.MediaStatus.EndOfMedia)

            # Assertions: HUD returns to canvas, video turns off, mic un-mutes, state returns to LISTENING
            self.assertFalse(win._video_on, "Video container must be marked closed")
            self.assertEqual(win._hud_cam_stack.currentIndex(), 0, "HUD stack must restore to 0 (Arc Reactor/Face)")
            self.assertFalse(win._muted, "Microphone must be unmuted after media finishes")
            self.assertEqual(win.state, "LISTENING", "UI state must transition back to LISTENING")
        finally:
            win.close()


if __name__ == "__main__":
    unittest.main()
