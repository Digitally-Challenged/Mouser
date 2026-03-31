import unittest
from core.keyboard_layouts import get_keyboard_layout, KEYBOARD_LAYOUTS


class KeyboardLayoutTests(unittest.TestCase):
    def test_mx_mechanical_layout_exists(self):
        layout = get_keyboard_layout("mx_mechanical")
        self.assertEqual(layout["key"], "mx_mechanical")
        self.assertTrue(layout["interactive"])
        self.assertTrue(len(layout["hotspots"]) > 0)

    def test_mx_mechanical_mini_layout_exists(self):
        layout = get_keyboard_layout("mx_mechanical_mini")
        self.assertEqual(layout["key"], "mx_mechanical_mini")
        self.assertTrue(layout["interactive"])

    def test_unknown_layout_returns_generic(self):
        layout = get_keyboard_layout("nonexistent")
        self.assertEqual(layout["key"], "generic_keyboard")
        self.assertFalse(layout["interactive"])

    def test_layout_returns_deep_copy(self):
        l1 = get_keyboard_layout("mx_mechanical")
        l2 = get_keyboard_layout("mx_mechanical")
        l1["hotspots"].clear()
        self.assertTrue(len(l2["hotspots"]) > 0)

    def test_all_hotspots_have_required_fields(self):
        for key, layout in KEYBOARD_LAYOUTS.items():
            for hs in layout["hotspots"]:
                self.assertIn("buttonKey", hs, f"Missing buttonKey in {key}")
                self.assertIn("label", hs, f"Missing label in {key}")
                self.assertIn("normX", hs, f"Missing normX in {key}")
                self.assertIn("normY", hs, f"Missing normY in {key}")
                self.assertIn("region", hs, f"Missing region in {key}")

    def test_none_returns_generic(self):
        layout = get_keyboard_layout(None)
        self.assertEqual(layout["key"], "generic_keyboard")
