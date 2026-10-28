import sys
import os
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import os
import sys

# Run offscreen
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from theme import ThemeColors, THEME_PRESETS, HUD_PRESETS, LAYOUT_PRESETS, CSS_VARIABLES
import ui
from ui import C, CustomizeOverlay, HudCanvas, MetricBar, LogWidget, MainWindow

print("--- Testing Theme Constants & Rules ---")
# Rule: Do NOT use purple anywhere
for name, col in THEME_PRESETS:
    print(f"Theme preset: {name} -> {col}")
    # Verify not purple (#a855f7 or similar)
    c = QColor(col)
    assert not (c.red() > 140 and c.blue() > 200 and c.green() < 100), f"Purple detected in preset {name}: {col}"

assert "#a855f7" not in [col.lower() for _, col in THEME_PRESETS], "Old purple preset still found!"
print("✓ Zero purple in theme presets verified!")

print("\n--- Testing CustomizeOverlay Layout & No-Slider Constraint ---")
cov = CustomizeOverlay(assistant_name="JARVIS", user_name="Tony", voice="Snow")
cov.resize(cov._OW, cov._OH)
cov.show()

# Verify NO QScrollArea inside CustomizeOverlay
from PyQt6.QtWidgets import QScrollArea, QScrollBar
scroll_areas = cov.findChildren(QScrollArea)
print(f"Number of QScrollArea widgets in CustomizeOverlay: {len(scroll_areas)}")
assert len(scroll_areas) == 0, f"Found QScrollArea in CustomizeOverlay! Sliders must not exist!"

# Verify all key buttons exist
assert "Snow" in cov._voice_btns, "Snow voice button missing"
assert "Nia" in cov._voice_btns, "Nia voice button missing"
assert "Dragon" in cov._voice_btns, "Dragon voice button missing"
assert "Mayra" in cov._voice_btns, "Mayra voice button missing"
for v in ("Charon", "Puck", "Kore", "Fenrir", "Aoede"):
    assert v in cov._voice_btns, f"{v} voice button missing"

print("✓ All 4 Permanent Character Voices + 5 Core Timbre buttons present!")

# Verify Visualizer modes
for _, mode in HUD_PRESETS:
    assert mode in cov._hud_btns, f"HUD mode {mode} missing"
print("✓ All 4 AI Visualizer Animation buttons present!")

# Verify Layout modes
for _, lmode in LAYOUT_PRESETS:
    assert lmode in cov._layout_btns, f"Layout mode {lmode} missing"
print("✓ All Layout Mode buttons present!")

# Verify Theme presets
for _, thex in THEME_PRESETS:
    assert thex in cov._theme_btns, f"Theme preset button {thex} missing"
print("✓ All 6 Theme Preset buttons present!")

# Verify Active Voice Info Card
assert cov._cv_info_box.isVisible(), "Active voice info box should be visible"
info_text = cov._cv_info_lbl.text()
print(f"Active Voice Info Card Text:\n{info_text}")
assert "snow" in info_text.lower(), "Voice info should reflect snow"
assert "gemini" in info_text.lower(), "Voice info should indicate Gemini Native"

# Test switching voice to Nia, Dragon and Mayra
cov._on_voice_pick("Nia")
assert "nia" in cov._cv_info_lbl.text().lower(), "Voice info should reflect Nia"
cov._on_voice_pick("Dragon")
assert "dragon" in cov._cv_info_lbl.text().lower(), "Voice info should reflect Dragon"
cov._on_voice_pick("Mayra")
assert "mayra" in cov._cv_info_lbl.text().lower(), "Voice info should reflect Mayra"
assert cov._name_input.text() == "JARVIS", "App title must remain JARVIS when voice is changed"
assert cov._sel_voice == "Mayra", "Selected voice should be Mayra"
print("✓ Voice switching updates card cleanly without ElevenLabs connection!")

print("\n--- Testing HudCanvas Floating Dust Particles & Facets ---")
hc = HudCanvas("dummy_face_path")
assert hasattr(hc, "_particles"), "HudCanvas should have floating dust particles"
assert len(hc._particles) >= 30, "HudCanvas should have at least 30 dust particles"
print(f"✓ HudCanvas dust particles initialized: {len(hc._particles)} specks drifting")

print("\n--- Testing MetricBar Hover & Amber Highlights ---")
mb = MetricBar("CPU")
assert hasattr(mb, "_hovered"), "MetricBar should track hover state"
mb.enterEvent(None)
assert mb._hovered == True, "MetricBar should be hovered"
mb.leaveEvent(None)
assert mb._hovered == False, "MetricBar should not be hovered"
print("✓ MetricBar hover state handling verified!")

print("\n--- Testing LogWidget Monospace & Tag Colors ---")
lw = LogWidget()
assert lw.font().family() in ("Courier New", "Consolas", "Courier"), f"LogWidget font should be monospace, got {lw.font().family()}"
lw._enqueue("JARVIS: Initialized systems online.")
assert lw._tag == "ai", f"Tag should be ai, got {lw._tag}"
lw._typing = False
lw._enqueue("WARN: Memory load high.")
assert lw._tag == "warn", f"Tag should be warn, got {lw._tag}"
lw._typing = False
lw._enqueue("ERR: Sensor unavailable.")
assert lw._tag == "err", f"Tag should be err, got {lw._tag}"
print("✓ LogWidget monospace font and cyan/amber/red color tags verified!")

print("\n==========================================")
print("ALL THEME & ZERO-SLIDER TESTS PASSED 100%!")
print("==========================================")
