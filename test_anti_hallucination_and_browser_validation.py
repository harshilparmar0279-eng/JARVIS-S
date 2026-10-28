import io
import sys
import unittest
from pathlib import Path
from actions.browser_control import validate_and_open_url, browser_control
from actions.chrome_launcher import launch_chrome
from core import outcome


class TestAntiHallucinationAndBrowserValidation(unittest.TestCase):
    """Test suite for browser anti-hallucination rules and URL validation."""

    def test_validate_and_open_url_blocks_blank_and_empty(self):
        """Ensure validate_and_open_url blocks empty, about:blank, and chrome://newtab/."""
        invalid_urls = ["", "about:blank", "chrome://newtab/", "about://blank", "   "]
        for target in invalid_urls:
            captured_stdout = io.StringIO()
            old_stdout = sys.stdout
            try:
                sys.stdout = captured_stdout
                res = validate_and_open_url(target)
            finally:
                sys.stdout = old_stdout

            output = captured_stdout.getvalue()
            self.assertFalse(res, f"Expected validate_and_open_url({target!r}) to return False")
            self.assertIn("Jarvis: Mujhe task clear nahi hai. Kripya specific website ya action batayein.", output)

    def test_validate_and_open_url_allows_valid_target(self):
        """Ensure validate_and_open_url permits valid URLs and logs opening message."""
        valid_url = "https://www.google.com"
        captured_stdout = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured_stdout
            res = validate_and_open_url(valid_url)
        finally:
            sys.stdout = old_stdout

        output = captured_stdout.getvalue()
        self.assertTrue(res)
        self.assertIn(f"Opening {valid_url}...", output)

    def test_browser_control_halts_on_about_blank(self):
        """Ensure browser_control action halts with clarification on about:blank or empty."""
        res_blank = browser_control(parameters={"action": "go_to", "url": "about:blank"})
        self.assertIn("Mujhe task clear nahi hai", res_blank)

        res_empty = browser_control(parameters={"action": "go_to", "url": ""})
        self.assertIn("Mujhe task clear nahi hai", res_empty)

    def test_launch_chrome_blocks_about_blank(self):
        """Ensure launch_chrome strictly halts when target URL is about:blank."""
        ok, msg = launch_chrome(profile_dir="", url="about:blank")
        self.assertFalse(ok)
        self.assertIn("Jarvis: Mujhe task clear nahi hai", msg)

    def test_system_prompt_contains_critical_rule(self):
        """Verify core/prompt.txt contains the exact critical anti-hallucination rule."""
        prompt_path = Path(__file__).resolve().parent / "core" / "prompt.txt"
        content = prompt_path.read_text(encoding="utf-8")
        expected_rule = (
            "CRITICAL RULE: You are a precise browser automation agent. "
            "If the user's command is unclear, ambiguous, or does not imply a specific website, DO NOT guess. "
            "Strictly DO NOT open 'about:blank'. DO NOT default to 'youtube.com' or any other popular site. "
            "If you do not know the exact URL required, immediately halt the browser action and ask the user for clarification."
        )
        self.assertIn(expected_rule, content)


if __name__ == "__main__":
    unittest.main()
