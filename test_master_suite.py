"""
test_master_suite.py — Automated verification across Issues 1 through 6.
"""
import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


class TestIssue1VoiceLifecycle(unittest.TestCase):
    def test_turn_tuning_defaults(self):
        from memory.config_manager import get_turn_tuning
        tt = get_turn_tuning()
        self.assertGreaterEqual(tt["silence_ms"], 800, "silence_ms should allow natural pauses (>= 800ms)")
        self.assertIn(tt["end_sensitivity"], ["default", "low", "high"])

    def test_tail_margin_constant(self):
        from main import _TAIL_MARGIN
        self.assertLessEqual(_TAIL_MARGIN, 0.15, "_TAIL_MARGIN should be tuned <= 0.15s to avoid dropping rapid replies")


class TestIssue2BraveYouTube(unittest.TestCase):
    def test_brave_resolver(self):
        from actions.brave_launcher import find_brave_executable, is_youtube_target
        brave_path = find_brave_executable()
        self.assertIsNotNone(brave_path, "Brave executable should be found on this system")
        self.assertTrue(Path(brave_path).exists(), f"Resolved Brave path must exist: {brave_path}")

        # Target detection
        self.assertTrue(is_youtube_target("https://www.youtube.com"))
        self.assertTrue(is_youtube_target("https://youtu.be/xyz"))
        self.assertTrue(is_youtube_target("youtube.com/watch?v=123"))
        self.assertTrue(is_youtube_target("open youtube"))
        self.assertTrue(is_youtube_target("youtube kholo"))
        self.assertFalse(is_youtube_target("https://google.com"))


class TestIssue3ChromeProfiles(unittest.TestCase):
    def test_chrome_discovery_and_matching(self):
        from actions.chrome_launcher import discover_chrome_profiles, match_profile, find_chrome_executable
        chrome_path = find_chrome_executable()
        self.assertIsNotNone(chrome_path, "Chrome executable should be found on this system")

        profiles = discover_chrome_profiles()
        self.assertIsInstance(profiles, list)
        self.assertGreater(len(profiles), 0, "Should discover at least one Chrome profile")

        # Test matching Default
        match = match_profile("Default")
        self.assertIsNotNone(match)
        self.assertEqual(match["dir_name"], "Default")


class TestIssue4WhatsAppActions(unittest.TestCase):
    def test_whatsapp_module_and_tool(self):
        from plugins._whatsapp_core import WhatsAppDesktopDriver
        from actions.whatsapp_actions import TOOL, whatsapp_actions
        self.assertEqual(TOOL["name"], "whatsapp_actions")
        self.assertTrue(callable(whatsapp_actions))
        driver = WhatsAppDesktopDriver()
        self.assertTrue(hasattr(driver, "search_contact"))
        self.assertTrue(hasattr(driver, "send_message_to"))
        self.assertTrue(hasattr(driver, "initiate_call"))


class TestIssue5ElevenLabsVoice(unittest.TestCase):
    def test_elevenlabs_validation(self):
        from memory.config_manager import get_provider_config, get_elevenlabs_fallback_enabled, save_elevenlabs_fallback_enabled
        from providers.tts_elevenlabs import validate_elevenlabs_credentials, test_voice_synthesis

        cfg = get_provider_config("elevenlabs")
        api_key = cfg.get("api_key", "")
        self.assertTrue(bool(api_key), "ElevenLabs API key should be present in configuration")

        # Validate with Roger (standard account voice)
        val = validate_elevenlabs_credentials(api_key, "CwhRBWXzGAHq8TQ4Fs17")
        self.assertTrue(val["valid"], f"Standard voice validation should succeed: {val}")

        # Validate with library voice - must return clear tier restriction, not silent success
        val_lib = validate_elevenlabs_credentials(api_key, "t65y7fZZv3UrpG7b4PUD")
        self.assertFalse(val_lib["valid"])
        self.assertEqual(val_lib.get("error_code"), "TIER_RESTRICTION")
        self.assertIn("Free users cannot use library voices", val_lib.get("error", ""))

        # Test synthesis output format
        ok, pcm, msg = test_voice_synthesis(api_key, "CwhRBWXzGAHq8TQ4Fs17", "eleven_flash_v2_5")
        self.assertTrue(ok, f"Synthesis test failed: {msg}")
        self.assertGreater(len(pcm), 10000, "Synthesis should return PCM bytes")

        # Test fallback configuration toggle
        curr = get_elevenlabs_fallback_enabled()
        save_elevenlabs_fallback_enabled(not curr)
        self.assertEqual(get_elevenlabs_fallback_enabled(), not curr)
        save_elevenlabs_fallback_enabled(curr)  # restore


class TestIssue6Permissions(unittest.TestCase):
    def test_permission_checker(self):
        from core.permission_checker import check_all_permissions
        res = check_all_permissions()
        self.assertIn("microphone", res)
        self.assertIn("speaker", res)
        self.assertIn("camera", res)
        self.assertTrue(res["microphone"]["ok"])
        self.assertTrue(res["speaker"]["ok"])
        self.assertTrue(res["camera"]["ok"])
        self.assertTrue(res["all_ok"])


if __name__ == "__main__":
    unittest.main()
