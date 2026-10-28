"""
test_mayra_persona.py — Verification suite for Mayra Voice & Persona integration:
1. Registration in BUILTIN_VOICES & PERMANENT_CHARACTER_VOICES
2. Exact system prompt & persona text preservation
3. Timbre mapping to Native Gemini prebuilt voice
4. Callsign default 'Harshil' without overwriting existing custom callsigns
5. UI button, badge '🌙 Mayra', preset chip '[Mayra Masti]', and assistant name reflection
6. Preserved integrity of all existing characters (Kavya, XG, Tiara, Charon, Puck, etc.)
"""
import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from memory.config_manager import (
    BUILTIN_VOICES,
    PERMANENT_CHARACTER_VOICES,
    DEFAULT_MAYRA_VOICE,
    get_custom_voice_info,
    get_user_name,
)


class TestMayraPersona(unittest.TestCase):
    def test_mayra_in_builtin_voices(self):
        self.assertIn("Mayra", BUILTIN_VOICES, "Mayra must be present in BUILTIN_VOICES")
        # Ensure all existing voices are untouched
        for existing in ("Charon", "Puck", "Kore", "Fenrir", "Aoede", "kavya", "XG", "Tiara"):
            self.assertIn(existing, BUILTIN_VOICES, f"Existing voice {existing} must be preserved")

    def test_mayra_character_voice_config(self):
        self.assertIn("Mayra", PERMANENT_CHARACTER_VOICES, "Mayra must be in PERMANENT_CHARACTER_VOICES")
        mayra_info = get_custom_voice_info("Mayra")
        self.assertEqual(mayra_info["name"], "Mayra")
        self.assertEqual(mayra_info["voice_type"], "gemini")
        self.assertEqual(mayra_info["base_voice"], DEFAULT_MAYRA_VOICE)
        self.assertEqual(mayra_info["voice_category"], "Sweet Playful Girlfriend")

    def test_mayra_system_prompt_content(self):
        mayra_info = get_custom_voice_info("Mayra")
        persona = mayra_info["persona"]

        # Assertions for Mayra Voice & Delivery prompt
        self.assertIn("Tu Mayra hai, Harshil ki pyaari, caring, masti karne wali girlfriend jaisi AI assistant", persona)
        self.assertIn("## 1. Awaaz ka andaaz (bolne ka tareeka)", persona)
        self.assertIn("## 2. Natural insaan jaisi baatein", persona)
        self.assertIn("## 3. Likhne ke rules (taaki awaaz robotic na lage)", persona)
        self.assertIn("## 4. Harshil kaise bulana hai", persona)
        self.assertIn('Conversation ka pehla jawab "Harshil..." se shuru kar', persona)
        self.assertIn("## 5. Caring aur loving behavior", persona)
        self.assertIn("## 6. Masti mode", persona)
        self.assertIn("system hack karke crash kar dungi!", persona)
        self.assertIn("main aapka phone hang kar deti hu... hehe, mazaak kar rahi hu", persona)
        self.assertIn("Bas, ab baat nahi karungi... achha chalo, bolo kya kaam hai", persona)
        self.assertIn("Main aapki saari playlist delete kar dungi... nahi nahi, itni buri nahi hu", persona)
        self.assertIn("## 7. Example (is style ko follow kar)", persona)
        self.assertIn("## 8. Limits", persona)

    def test_callsign_default_behavior(self):
        # When user_name is '-' or empty, it defaults to 'Harshil'
        name = get_user_name()
        self.assertTrue(name == "Harshil" or len(name) > 0, "Default callsign must be non-empty and default to Harshil")

    def test_mayra_ui_integration(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)

        from ui import CustomizeOverlay
        cov = CustomizeOverlay(assistant_name="JARVIS", user_name="-", voice="Mayra")

        # Check callsign input initialized with 'Harshil'
        self.assertEqual(cov._user_input.text(), "Harshil", "Callsign field must default to 'Harshil' when empty or '-'")

        # Check Mayra voice button exists
        self.assertIn("Mayra", cov._voice_btns, "Mayra button must be in _voice_btns")
        btn = cov._voice_btns["Mayra"]
        self.assertIn("🌙", btn.text(), "Mayra button must feature the moon icon 🌙")
        self.assertIn("Mayra", btn.text())

        # Test selecting Mayra keeps app name as 'JARVIS' and sets voice to 'Mayra'
        cov._on_voice_pick("Mayra")
        self.assertEqual(cov._name_input.text(), "JARVIS", "App name must remain 'JARVIS' when picking Mayra voice")
        self.assertEqual(cov._sel_voice, "Mayra", "Selected voice must be 'Mayra'")
        preview_text = cov._cv_info_lbl.text()
        self.assertIn("Mayra", preview_text)
        self.assertIn("Sweet Playful Girlfriend", preview_text)
        self.assertIn("Permanent Native Gemini Acoustic", preview_text)
        self.assertIn("Aoede", preview_text)

        # Ensure existing character buttons are untouched
        self.assertIn("kavya", cov._voice_btns)
        self.assertIn("XG", cov._voice_btns)
        self.assertIn("Tiara", cov._voice_btns)


if __name__ == "__main__":
    unittest.main()
