"""Tests for core.keyboard_hid — KeyboardHidListener."""

import unittest
from unittest.mock import MagicMock

from core.keyboard_hid import KeyboardHidListener, KEYBOARD_PIDS
from core.hidpp import LONG_ID, MY_SW


class TestKeyboardHidInit(unittest.TestCase):
    """Verify constructor stores callbacks correctly."""

    def test_callbacks_stored(self):
        on_key = MagicMock()
        on_conn = MagicMock()
        on_disc = MagicMock()
        listener = KeyboardHidListener(
            on_key_diverted=on_key,
            on_connect=on_conn,
            on_disconnect=on_disc,
        )
        self.assertIs(listener._on_key_diverted, on_key)
        self.assertIs(listener._on_connect, on_conn)
        self.assertIs(listener._on_disconnect, on_disc)

    def test_defaults_to_none(self):
        listener = KeyboardHidListener()
        self.assertIsNone(listener._on_key_diverted)
        self.assertIsNone(listener._on_connect)
        self.assertIsNone(listener._on_disconnect)
        self.assertFalse(listener.connected)
        self.assertIsNone(listener.connected_keyboard)


class TestKeyboardPids(unittest.TestCase):
    """Verify the known keyboard PID set."""

    def test_contains_mx_mechanical(self):
        self.assertIn(0xB366, KEYBOARD_PIDS)

    def test_contains_mx_mechanical_mini(self):
        self.assertIn(0xB367, KEYBOARD_PIDS)


def _build_report(dev_idx, feat_idx, func, sw, params):
    """Build a raw HID++ long report buffer."""
    buf = [0] * 20
    buf[0] = LONG_ID
    buf[1] = dev_idx
    buf[2] = feat_idx
    buf[3] = ((func & 0x0F) << 4) | (sw & 0x0F)
    for i, b in enumerate(params):
        if 4 + i < 20:
            buf[4 + i] = b & 0xFF
    return buf


class TestOnReportKeyDown(unittest.TestCase):
    """_on_report fires on_key_diverted(cid, True) when a diverted CID appears."""

    def test_key_down_fires_callback(self):
        on_key = MagicMock()
        listener = KeyboardHidListener(on_key_diverted=on_key)
        listener._feat_idx = 0x05
        listener._diverted_cids = {0x00C8}
        listener._held_cids = set()

        # CID 0x00C8 appears in report
        raw = _build_report(
            0xFF, 0x05, 0, MY_SW,
            [0x00, 0xC8, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
             0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        )
        listener._on_report(raw)

        on_key.assert_called_once_with(0x00C8, True)
        self.assertIn(0x00C8, listener._held_cids)


class TestOnReportKeyUp(unittest.TestCase):
    """_on_report fires on_key_diverted(cid, False) when a held CID disappears."""

    def test_key_up_fires_callback(self):
        on_key = MagicMock()
        listener = KeyboardHidListener(on_key_diverted=on_key)
        listener._feat_idx = 0x05
        listener._diverted_cids = {0x00C8}
        listener._held_cids = {0x00C8}  # already held

        # Empty report (all zeros = no CIDs pressed)
        raw = _build_report(
            0xFF, 0x05, 0, MY_SW,
            [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
             0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        )
        listener._on_report(raw)

        on_key.assert_called_once_with(0x00C8, False)
        self.assertNotIn(0x00C8, listener._held_cids)


class TestOnReportIgnoresNonDiverted(unittest.TestCase):
    """_on_report ignores CIDs that are not in the diverted set."""

    def test_non_diverted_cid_ignored(self):
        on_key = MagicMock()
        listener = KeyboardHidListener(on_key_diverted=on_key)
        listener._feat_idx = 0x05
        listener._diverted_cids = {0x00C8}  # only C8 diverted
        listener._held_cids = set()

        # CID 0x00CA appears but is NOT in diverted set
        raw = _build_report(
            0xFF, 0x05, 0, MY_SW,
            [0x00, 0xCA, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
             0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        )
        listener._on_report(raw)

        on_key.assert_not_called()


class TestOnReportIgnoresWrongFeatureIndex(unittest.TestCase):
    """_on_report ignores reports whose feature index does not match."""

    def test_wrong_feature_index_ignored(self):
        on_key = MagicMock()
        listener = KeyboardHidListener(on_key_diverted=on_key)
        listener._feat_idx = 0x05
        listener._diverted_cids = {0x00C8}
        listener._held_cids = set()

        # Feature index 0x07 != 0x05
        raw = _build_report(
            0xFF, 0x07, 0, MY_SW,
            [0x00, 0xC8, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
             0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        )
        listener._on_report(raw)

        on_key.assert_not_called()


class TestOnReportMultipleKeys(unittest.TestCase):
    """_on_report handles multiple simultaneous CIDs."""

    def test_two_keys_down(self):
        on_key = MagicMock()
        listener = KeyboardHidListener(on_key_diverted=on_key)
        listener._feat_idx = 0x05
        listener._diverted_cids = {0x00C8, 0x00C9}
        listener._held_cids = set()

        # Two CIDs: 0x00C8, 0x00C9
        raw = _build_report(
            0xFF, 0x05, 0, MY_SW,
            [0x00, 0xC8, 0x00, 0xC9, 0x00, 0x00, 0x00, 0x00,
             0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        )
        listener._on_report(raw)

        self.assertEqual(on_key.call_count, 2)
        called_cids = {call.args[0] for call in on_key.call_args_list}
        self.assertEqual(called_cids, {0x00C8, 0x00C9})
        for call in on_key.call_args_list:
            self.assertTrue(call.args[1])  # pressed=True

    def test_one_key_released_while_other_held(self):
        on_key = MagicMock()
        listener = KeyboardHidListener(on_key_diverted=on_key)
        listener._feat_idx = 0x05
        listener._diverted_cids = {0x00C8, 0x00C9}
        listener._held_cids = {0x00C8, 0x00C9}  # both held

        # Only 0x00C9 remains
        raw = _build_report(
            0xFF, 0x05, 0, MY_SW,
            [0x00, 0xC9, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
             0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        )
        listener._on_report(raw)

        # C8 released
        on_key.assert_called_once_with(0x00C8, False)


class TestOnReportIgnoresNonZeroFunction(unittest.TestCase):
    """_on_report ignores reports with function != 0."""

    def test_function_1_ignored(self):
        on_key = MagicMock()
        listener = KeyboardHidListener(on_key_diverted=on_key)
        listener._feat_idx = 0x05
        listener._diverted_cids = {0x00C8}
        listener._held_cids = set()

        # function=1 instead of 0
        raw = _build_report(
            0xFF, 0x05, 1, MY_SW,
            [0x00, 0xC8, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
             0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        )
        listener._on_report(raw)

        on_key.assert_not_called()


if __name__ == "__main__":
    unittest.main()
