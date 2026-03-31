"""Tests for core.engine — multi-device orchestration."""

import unittest
from unittest.mock import MagicMock, patch, call


def _v5_config():
    """Return a minimal v5 config for testing."""
    return {
        "version": 5,
        "devices": {
            "mouse": {
                "active_profile": "default",
                "profiles": {
                    "default": {
                        "label": "Default",
                        "apps": [],
                        "mappings": {
                            "middle": "none",
                            "gesture": "none",
                            "gesture_left": "none",
                            "gesture_right": "none",
                            "gesture_up": "none",
                            "gesture_down": "none",
                            "xbutton1": "none",
                            "xbutton2": "none",
                            "hscroll_left": "none",
                            "hscroll_right": "none",
                            "action_ring": "none",
                        },
                    }
                },
                "settings": {
                    "dpi": 1000,
                    "debug_mode": False,
                    "invert_hscroll": False,
                    "invert_vscroll": False,
                    "gesture_threshold": 50,
                    "gesture_deadzone": 40,
                    "gesture_timeout_ms": 3000,
                    "gesture_cooldown_ms": 500,
                    "hscroll_threshold": 1,
                },
            },
            "keyboard": {
                "active_profile": "default",
                "profiles": {
                    "default": {
                        "label": "Default",
                        "apps": [],
                        "mappings": {},
                    }
                },
                "settings": {"fn_inversion": False},
            },
        },
    }


# Shared patch decorators — order matters: bottom decorator = first positional arg
_PATCHES = [
    patch("core.engine.load_config"),
    patch("core.engine.AppDetector"),
    patch("core.engine.MouseHook"),
    patch("core.engine.KeyboardHook"),
    patch("core.engine.KeyboardHidListener"),
]


def _apply_patches(fn):
    """Stack all five patches onto a test method.

    Patches are applied bottom-up: last in _PATCHES becomes the outermost
    decorator and therefore the *last* positional arg injected.  We iterate
    forward so that _PATCHES[0] (load_config) ends up outermost, giving
    the arg order: mock_kb_hid, mock_kb_hook, mock_mouse, mock_app, mock_load.
    """
    for p in _PATCHES:
        fn = p(fn)
    return fn


class EngineMultiDeviceTests(unittest.TestCase):
    """Verify Engine creates and manages both mouse + keyboard subsystems."""

    @_apply_patches
    def test_engine_creates_keyboard_components(
        self, mock_load, mock_app, mock_mouse, mock_kb_hook, mock_kb_hid
    ):
        mock_load.return_value = _v5_config()
        from core.engine import Engine

        engine = Engine()
        self.assertIsNotNone(engine.keyboard_hook)
        mock_kb_hid.assert_called_once()
        mock_kb_hook.assert_called_once()

    @_apply_patches
    def test_keyboard_connection_callback(
        self, mock_load, mock_app, mock_mouse, mock_kb_hook, mock_kb_hid
    ):
        mock_load.return_value = _v5_config()
        from core.engine import Engine

        engine = Engine()
        cb = MagicMock()
        engine.set_keyboard_connection_callback(cb)
        engine._on_keyboard_connect()
        cb.assert_called_once_with(True)

    @_apply_patches
    def test_keyboard_disconnect_callback(
        self, mock_load, mock_app, mock_mouse, mock_kb_hook, mock_kb_hid
    ):
        mock_load.return_value = _v5_config()
        from core.engine import Engine

        engine = Engine()
        cb = MagicMock()
        engine.set_keyboard_connection_callback(cb)
        engine._on_keyboard_disconnect()
        cb.assert_called_once_with(False)

    @_apply_patches
    def test_keyboard_key_event_dispatches(
        self, mock_load, mock_app, mock_mouse, mock_kb_hook_cls, mock_kb_hid
    ):
        mock_load.return_value = _v5_config()
        from core.engine import Engine

        engine = Engine()
        # Register a handler on the real KeyboardHook instance
        handler = MagicMock()
        engine.keyboard_hook.register(0x010A, handler)
        engine._on_keyboard_key_event(0x010A, True)
        engine.keyboard_hook.on_key_event.assert_called_once_with(0x010A, True)

    @_apply_patches
    def test_keyboard_connected_property(
        self, mock_load, mock_app, mock_mouse, mock_kb_hook, mock_kb_hid
    ):
        mock_load.return_value = _v5_config()
        from core.engine import Engine

        engine = Engine()
        mock_kb_hid.return_value.connected = False
        self.assertFalse(engine.keyboard_connected)

    @_apply_patches
    def test_connected_keyboard_property(
        self, mock_load, mock_app, mock_mouse, mock_kb_hook, mock_kb_hid
    ):
        mock_load.return_value = _v5_config()
        from core.engine import Engine

        engine = Engine()
        sentinel = object()
        mock_kb_hid.return_value.connected_keyboard = sentinel
        self.assertIs(engine.connected_keyboard, sentinel)

    @_apply_patches
    def test_start_starts_keyboard_hid(
        self, mock_load, mock_app, mock_mouse, mock_kb_hook, mock_kb_hid
    ):
        mock_load.return_value = _v5_config()
        from core.engine import Engine

        engine = Engine()
        engine.start()
        mock_kb_hid.return_value.start.assert_called_once()

    @_apply_patches
    def test_stop_stops_keyboard_hid(
        self, mock_load, mock_app, mock_mouse, mock_kb_hook, mock_kb_hid
    ):
        mock_load.return_value = _v5_config()
        from core.engine import Engine

        engine = Engine()
        engine.stop()
        mock_kb_hid.return_value.stop.assert_called_once()

    @_apply_patches
    def test_reload_mappings_refreshes_keyboard(
        self, mock_load, mock_app, mock_mouse, mock_kb_hook_cls, mock_kb_hid
    ):
        mock_load.return_value = _v5_config()
        from core.engine import Engine

        engine = Engine()
        # Reset call counts after __init__
        engine.keyboard_hook.reset.reset_mock()
        engine.reload_mappings()
        engine.keyboard_hook.reset.assert_called()

    @_apply_patches
    def test_reload_keyboard_mappings(
        self, mock_load, mock_app, mock_mouse, mock_kb_hook_cls, mock_kb_hid
    ):
        mock_load.return_value = _v5_config()
        from core.engine import Engine

        engine = Engine()
        engine.keyboard_hook.reset.reset_mock()
        engine.reload_keyboard_mappings()
        engine.keyboard_hook.reset.assert_called()

    @_apply_patches
    def test_app_change_switches_keyboard_profile(
        self, mock_load, mock_app, mock_mouse, mock_kb_hook_cls, mock_kb_hid
    ):
        cfg = _v5_config()
        cfg["devices"]["keyboard"]["profiles"]["vscode"] = {
            "label": "VS Code",
            "apps": ["Code.exe"],
            "mappings": {"010A": "volume_up"},
        }
        mock_load.return_value = cfg
        from core.engine import Engine

        engine = Engine()
        engine.keyboard_hook.reset.reset_mock()
        # Simulate app change to Code.exe
        engine._on_app_change("Code.exe")
        # keyboard profile should have switched
        self.assertEqual(engine._current_kb_profile, "vscode")

    @_apply_patches
    def test_v5_config_paths_used(
        self, mock_load, mock_app, mock_mouse, mock_kb_hook, mock_kb_hid
    ):
        mock_load.return_value = _v5_config()
        from core.engine import Engine

        engine = Engine()
        self.assertEqual(engine._current_profile, "default")
        self.assertEqual(engine._current_kb_profile, "default")

    @_apply_patches
    def test_set_keyboard_battery_callback(
        self, mock_load, mock_app, mock_mouse, mock_kb_hook, mock_kb_hid
    ):
        mock_load.return_value = _v5_config()
        from core.engine import Engine

        engine = Engine()
        cb = MagicMock()
        engine.set_keyboard_battery_callback(cb)
        self.assertIs(engine._keyboard_battery_cb, cb)


if __name__ == "__main__":
    unittest.main()
