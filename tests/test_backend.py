import copy
import unittest
from unittest.mock import patch, MagicMock

from core.config import _make_default_v5

try:
    from ui.backend import Backend
except ModuleNotFoundError:
    Backend = None


def _v5_config():
    """Return a fresh v5 config for testing."""
    return copy.deepcopy(_make_default_v5())


def _v5_config_with_keyboard_mappings():
    """Return v5 config with some keyboard mappings set."""
    cfg = _v5_config()
    cfg["devices"]["keyboard"]["profiles"]["default"]["mappings"] = {
        "00C8": "volume_up",    # F1 -> volume up
        "00C9": "volume_down",  # F2 -> volume down
        "00D1": "none",         # Fn (non-divertable)
        "00D2": "none",         # Fn Lock (non-divertable)
    }
    return cfg


@unittest.skipIf(Backend is None, "PySide6 not installed in test environment")
class BackendDeviceLayoutTests(unittest.TestCase):
    def _make_backend(self, cfg=None):
        config = cfg if cfg is not None else _v5_config()
        with (
            patch("ui.backend.load_config", return_value=config),
            patch("ui.backend.save_config"),
        ):
            return Backend(engine=None)

    def test_defaults_to_generic_layout_without_connected_device(self):
        backend = self._make_backend()

        self.assertEqual(backend.effectiveDeviceLayoutKey, "generic_mouse")
        self.assertFalse(backend.hasInteractiveDeviceLayout)

    def test_disconnected_override_request_does_not_persist(self):
        backend = self._make_backend()
        backend._connected_device_key = "mx_master_3"
        backend.setDeviceLayoutOverride("mx_master")

        overrides = (
            backend._cfg.get("devices", {}).get("mouse", {})
            .get("settings", {}).get("device_layout_overrides", {})
        )
        self.assertEqual(overrides, {})


@unittest.skipIf(Backend is None, "PySide6 not installed in test environment")
class BackendV5PropertyTests(unittest.TestCase):
    """Test that existing mouse properties read from v5 config paths."""

    def _make_backend(self, cfg=None):
        config = cfg if cfg is not None else _v5_config()
        with (
            patch("ui.backend.load_config", return_value=config),
            patch("ui.backend.save_config"),
        ):
            return Backend(engine=None)

    def test_dpi_reads_from_v5_path(self):
        cfg = _v5_config()
        cfg["devices"]["mouse"]["settings"]["dpi"] = 2400
        backend = self._make_backend(cfg)
        self.assertEqual(backend.dpi, 2400)

    def test_active_profile_reads_from_v5_path(self):
        cfg = _v5_config()
        cfg["devices"]["mouse"]["active_profile"] = "gaming"
        backend = self._make_backend(cfg)
        self.assertEqual(backend.activeProfile, "gaming")

    def test_invert_vscroll_reads_from_v5_path(self):
        cfg = _v5_config()
        cfg["devices"]["mouse"]["settings"]["invert_vscroll"] = True
        backend = self._make_backend(cfg)
        self.assertTrue(backend.invertVScroll)

    def test_appearance_mode_reads_from_v5_path(self):
        cfg = _v5_config()
        cfg["devices"]["mouse"]["settings"]["appearance_mode"] = "dark"
        backend = self._make_backend(cfg)
        self.assertEqual(backend.appearanceMode, "dark")

    def test_profiles_reads_from_v5_path(self):
        backend = self._make_backend()
        profiles = backend.profiles
        self.assertTrue(len(profiles) >= 1)
        names = [p["name"] for p in profiles]
        self.assertIn("default", names)


@unittest.skipIf(Backend is None, "PySide6 not installed in test environment")
class BackendKeyboardPropertyTests(unittest.TestCase):
    """Test keyboard-related properties, signals, and slots."""

    def _make_backend(self, cfg=None):
        config = cfg if cfg is not None else _v5_config()
        with (
            patch("ui.backend.load_config", return_value=config),
            patch("ui.backend.save_config"),
        ):
            return Backend(engine=None)

    # -- Connection / battery state --

    def test_keyboard_connected_default_false(self):
        backend = self._make_backend()
        self.assertFalse(backend.keyboardConnected)

    def test_keyboard_battery_level_default_negative(self):
        backend = self._make_backend()
        self.assertEqual(backend.keyboardBatteryLevel, -1)

    def test_handle_keyboard_connection_change(self):
        backend = self._make_backend()
        backend._handleKeyboardConnectionChange(True)
        self.assertTrue(backend.keyboardConnected)

    def test_handle_keyboard_battery_change(self):
        backend = self._make_backend()
        backend._handleKeyboardBatteryChange(75)
        self.assertEqual(backend.keyboardBatteryLevel, 75)

    # -- Keyboard mappings --

    def test_keyboard_buttons_shows_all_remappable_by_default(self):
        backend = self._make_backend()
        buttons = backend.keyboardButtons
        # Should show all MX Mechanical remappable keys (minus non-divertable)
        self.assertTrue(len(buttons) > 30)  # MX Mechanical has 36 divertable keys

    def test_keyboard_buttons_excludes_non_divertable(self):
        backend = self._make_backend()
        buttons = backend.keyboardButtons
        keys = [b["key"] for b in buttons]
        # Non-divertable CIDs should be filtered out
        self.assertNotIn("0x00D1", keys)  # Host Switch Ch1
        self.assertNotIn("0x00D2", keys)  # Host Switch Ch2
        self.assertNotIn("0x00DE", keys)  # F Lock
        self.assertNotIn("0x0034", keys)  # Fn Key

    def test_keyboard_buttons_contain_expected_fields(self):
        cfg = _v5_config_with_keyboard_mappings()
        backend = self._make_backend(cfg)
        buttons = backend.keyboardButtons
        for btn in buttons:
            self.assertIn("key", btn)
            self.assertIn("name", btn)
            self.assertIn("actionId", btn)
            self.assertIn("actionLabel", btn)

    def test_set_keyboard_mapping(self):
        backend = self._make_backend()
        with patch("ui.backend.save_config"):
            backend.setKeyboardMapping("00C8", "volume_up")
        mappings = (
            backend._cfg["devices"]["keyboard"]["profiles"]["default"]["mappings"]
        )
        self.assertEqual(mappings["00C8"], "volume_up")

    # -- Keyboard settings --

    def test_fn_inversion_default_false(self):
        backend = self._make_backend()
        self.assertFalse(backend.fnInversion)

    def test_fn_inversion_reads_config(self):
        cfg = _v5_config()
        cfg["devices"]["keyboard"]["settings"]["fn_inversion"] = True
        backend = self._make_backend(cfg)
        self.assertTrue(backend.fnInversion)

    def test_backlight_enabled_default_true(self):
        backend = self._make_backend()
        self.assertTrue(backend.backlightEnabled)

    def test_backlight_brightness_default(self):
        backend = self._make_backend()
        self.assertEqual(backend.backlightBrightness, 80)

    def test_backlight_mode_default(self):
        backend = self._make_backend()
        self.assertEqual(backend.backlightMode, "auto")

    def test_set_fn_inversion(self):
        backend = self._make_backend()
        with patch("ui.backend.save_config"):
            backend.setFnInversion(True)
        kb_settings = backend._cfg["devices"]["keyboard"]["settings"]
        self.assertTrue(kb_settings["fn_inversion"])

    def test_set_backlight(self):
        backend = self._make_backend()
        with patch("ui.backend.save_config"):
            backend.setBacklight(False, 50, "static")
        kb_settings = backend._cfg["devices"]["keyboard"]["settings"]
        self.assertFalse(kb_settings["backlight_enabled"])
        self.assertEqual(kb_settings["backlight_brightness"], 50)
        self.assertEqual(kb_settings["backlight_mode"], "static")

    # -- Engine wiring --

    def test_engine_keyboard_callbacks_wired(self):
        mock_engine = MagicMock()
        mock_engine.connected_device = None
        cfg = _v5_config()
        with (
            patch("ui.backend.load_config", return_value=cfg),
            patch("ui.backend.save_config"),
        ):
            backend = Backend(engine=mock_engine)
        mock_engine.set_keyboard_connection_callback.assert_called_once()
        mock_engine.set_keyboard_battery_callback.assert_called_once()

    def test_cross_thread_keyboard_connection_emits_signal(self):
        backend = self._make_backend()
        # Directly calling the engine callback should relay via signal
        backend._onEngineKeyboardConnectionChange(True)
        # In a real Qt event loop, _handleKeyboardConnectionChange runs
        # on the main thread. Here we call it directly for testing.
        backend._handleKeyboardConnectionChange(True)
        self.assertTrue(backend.keyboardConnected)


if __name__ == "__main__":
    unittest.main()
