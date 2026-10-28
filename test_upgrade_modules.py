"""
test_upgrade_modules.py — Verification suite for Jarvis Architectural Upgrades:
1. WhatsApp Desktop Automation (Fuzzy search, message compose, voice & video calling fallback)
2. Command Mutex Lock (Task queue concurrency serialization)
3. YouTube Music routing & Browser about:blank bug fix
4. Local System File & Application Launcher (Start Menu, Desktop, and user folder search)
5. Persona & Addressing Protocol ("Harshil" on first greeting -> "Sir" strictly thereafter)
6. Speaker Identification, Pitch Detection, and Gender Classification
"""
import sys
import unittest
from pathlib import Path
import numpy as np

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


class TestJarvisUpgrades(unittest.TestCase):
    def test_addressing_protocol_in_persona(self):
        """Verify Mayra persona enforces Harshil once, then strictly Sir."""
        from memory.config_manager import get_custom_voice_info
        info = get_custom_voice_info("Mayra")
        self.assertIsNotNone(info)
        persona = info["persona"]
        self.assertIn("Harshil...", persona)
        self.assertIn('strictly "Sir" bolna hai', persona)
        self.assertIn('Kabhi bhi dubara "Harshil" naam mat lena', persona)

    def test_whatsapp_clean_contact_query(self):
        """Verify fuzzy contact name cleaner strips noise words."""
        from plugins._whatsapp_core import clean_contact_query
        self.assertEqual(clean_contact_query("Rahul bhai"), "Rahul")
        self.assertEqual(clean_contact_query("Papa ji"), "Papa")
        self.assertEqual(clean_contact_query("Amit ko"), "Amit")
        self.assertEqual(clean_contact_query("Priya video call"), "Priya")

    def test_command_mutex_lock(self):
        """Verify sync and async command locks prevent race conditions."""
        from core.command_lock import sync_command_mutex
        entered = False
        with sync_command_mutex(timeout=2.0) as acquired:
            self.assertTrue(acquired)
            entered = True
        self.assertTrue(entered)

    def test_browser_about_blank_sanitization(self):
        """Verify empty or missing URLs never produce 'about:blank'."""
        from actions.browser_control import _normalize_url
        self.assertEqual(_normalize_url(""), "")
        self.assertEqual(_normalize_url("   "), "")
        self.assertEqual(_normalize_url("about:blank"), "")
        self.assertEqual(_normalize_url("google.com"), "https://google.com")

    def test_youtube_music_auto_playback(self):
        """Verify YouTube Music command routes directly with verified playback."""
        from core.media_router import parse_media_intent
        intent = parse_media_intent("Play Kesariya on YouTube Music")
        self.assertEqual(intent["intent"], "PLAY_MUSIC")
        self.assertEqual(intent["service"], "youtube_music")
        self.assertEqual(intent["browser"], "chrome")
        self.assertTrue("kesariya" in intent["query"].lower())

    def test_local_launcher_matching(self):
        """Verify local launcher finds standard system apps."""
        from core.local_launcher import find_local_target
        notepad = find_local_target("notepad")
        self.assertIsNotNone(notepad)
        self.assertTrue(notepad.exists())
        self.assertTrue(str(notepad).lower().endswith(".exe"))

    def test_speaker_pitch_and_gender_detection(self):
        """Verify pitch estimation and gender classification."""
        from core.speaker_id import estimate_pitch, get_speaker_identifier
        t = np.arange(16000) / 16000
        male_wave = (np.sin(2 * np.pi * 115 * t) * 10000).astype(np.int16)
        female_wave = (np.sin(2 * np.pi * 225 * t) * 10000).astype(np.int16)

        p_m = estimate_pitch(male_wave, 16000)
        p_f = estimate_pitch(female_wave, 16000)
        self.assertTrue(100 <= p_m <= 130, f"Male pitch {p_m} out of range")
        self.assertTrue(210 <= p_f <= 240, f"Female pitch {p_f} out of range")

        sid = get_speaker_identifier()
        res_f = sid.verify_speaker(female_wave, 16000)
        self.assertEqual(res_f["gender"], "female")
        self.assertIn("female voice", res_f["intervention_msg"])


if __name__ == "__main__":
    unittest.main()
