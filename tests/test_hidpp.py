import unittest
import unittest.mock

from core import hidpp


class ParseReportTests(unittest.TestCase):
    """Test parse_report with various input formats."""

    def test_with_report_id_short(self):
        """Report-ID present (0x10): byte 0 is skipped."""
        raw = [0x10, 0xFF, 0x04, 0xA5, 0x01, 0x02, 0x03]
        result = hidpp.parse_report(raw)
        self.assertIsNotNone(result)
        dev, feat, func, sw, params = result
        self.assertEqual(dev, 0xFF)
        self.assertEqual(feat, 0x04)
        self.assertEqual(func, 0x0A)  # (0xA5 >> 4) & 0x0F
        self.assertEqual(sw, 0x05)    # 0xA5 & 0x0F
        self.assertEqual(list(params), [0x01, 0x02, 0x03])

    def test_with_report_id_long(self):
        """Report-ID present (0x11): byte 0 is skipped."""
        raw = [0x11, 0xFF, 0x06, 0x3A] + [0x00] * 16
        result = hidpp.parse_report(raw)
        self.assertIsNotNone(result)
        dev, feat, func, sw, params = result
        self.assertEqual(dev, 0xFF)
        self.assertEqual(feat, 0x06)
        self.assertEqual(func, 0x03)
        self.assertEqual(sw, 0x0A)

    def test_without_report_id(self):
        """Windows hidapi strips report-ID: byte 0 is device-index directly."""
        raw = [0xFF, 0x04, 0xA5, 0x01, 0x02, 0x03]
        result = hidpp.parse_report(raw)
        self.assertIsNotNone(result)
        dev, feat, func, sw, params = result
        self.assertEqual(dev, 0xFF)
        self.assertEqual(feat, 0x04)
        self.assertEqual(func, 0x0A)
        self.assertEqual(sw, 0x05)
        self.assertEqual(list(params), [0x01, 0x02, 0x03])

    def test_too_short(self):
        """Buffers shorter than 4 bytes return None."""
        self.assertIsNone(hidpp.parse_report([0x10, 0xFF, 0x04]))
        self.assertIsNone(hidpp.parse_report([0xFF, 0x04]))

    def test_empty(self):
        """Empty or None input returns None."""
        self.assertIsNone(hidpp.parse_report([]))
        self.assertIsNone(hidpp.parse_report(None))
        self.assertIsNone(hidpp.parse_report(b""))


class HexBytesTests(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(hidpp.hex_bytes([0x0A, 0xFF, 0x00]), "0A FF 00")

    def test_empty(self):
        self.assertEqual(hidpp.hex_bytes([]), "-")
        self.assertEqual(hidpp.hex_bytes(None), "-")

    def test_single_byte(self):
        self.assertEqual(hidpp.hex_bytes([0x42]), "42")


class FormatFlagsTests(unittest.TestCase):
    def test_single_flag(self):
        result = hidpp.format_flags(0x0020, hidpp.KEY_FLAG_BITS)
        self.assertEqual(result, "divertable")

    def test_multiple_flags(self):
        result = hidpp.format_flags(0x0030, hidpp.KEY_FLAG_BITS)
        self.assertIn("reprogrammable", result)
        self.assertIn("divertable", result)

    def test_no_flags(self):
        result = hidpp.format_flags(0x0000, hidpp.KEY_FLAG_BITS)
        self.assertEqual(result, "none")


class FormatCidTests(unittest.TestCase):
    def test_known_cid(self):
        result = hidpp.format_cid(0x00C3)
        self.assertIn("Mouse Gesture Button", result)
        self.assertIn("0x00C3", result)

    def test_unknown_cid(self):
        result = hidpp.format_cid(0x9999)
        self.assertEqual(result, "0x9999")


class ConstantsTests(unittest.TestCase):
    """Verify all shared constants have expected values."""

    def test_logi_vid(self):
        self.assertEqual(hidpp.LOGI_VID, 0x046D)

    def test_report_ids(self):
        self.assertEqual(hidpp.SHORT_ID, 0x10)
        self.assertEqual(hidpp.LONG_ID, 0x11)

    def test_report_lengths(self):
        self.assertEqual(hidpp.SHORT_LEN, 7)
        self.assertEqual(hidpp.LONG_LEN, 20)

    def test_bt_dev_idx(self):
        self.assertEqual(hidpp.BT_DEV_IDX, 0xFF)

    def test_feature_ids(self):
        self.assertEqual(hidpp.FEAT_IROOT, 0x0000)
        self.assertEqual(hidpp.FEAT_REPROG_V4, 0x1B04)
        self.assertEqual(hidpp.FEAT_ADJ_DPI, 0x2201)
        self.assertEqual(hidpp.FEAT_UNIFIED_BATT, 0x1004)
        self.assertEqual(hidpp.FEAT_BATTERY_STATUS, 0x1000)

    def test_keyboard_feature_ids(self):
        self.assertEqual(hidpp.FEAT_BACKLIGHT2, 0x1982)
        self.assertEqual(hidpp.FEAT_FN_INVERSION, 0x40A3)
        self.assertEqual(hidpp.FEAT_DISABLE_KEYS, 0x4521)

    def test_my_sw(self):
        self.assertEqual(hidpp.MY_SW, 0x0A)

    def test_hidpp_error_names_populated(self):
        self.assertIn(0x01, hidpp.HIDPP_ERROR_NAMES)
        self.assertEqual(hidpp.HIDPP_ERROR_NAMES[0x09], "UNSUPPORTED")

    def test_known_cid_names_has_mouse_and_keyboard_entries(self):
        # Mouse CIDs
        self.assertIn(0x00C3, hidpp.KNOWN_CID_NAMES)
        self.assertIn(0x01A0, hidpp.KNOWN_CID_NAMES)
        # Keyboard CIDs
        self.assertIn(0x00C7, hidpp.KNOWN_CID_NAMES)
        self.assertIn(0x0141, hidpp.KNOWN_CID_NAMES)

    def test_key_flag_bits_is_tuple(self):
        self.assertIsInstance(hidpp.KEY_FLAG_BITS, tuple)
        self.assertGreater(len(hidpp.KEY_FLAG_BITS), 0)

    def test_mapping_flag_bits_is_tuple(self):
        self.assertIsInstance(hidpp.MAPPING_FLAG_BITS, tuple)
        self.assertGreater(len(hidpp.MAPPING_FLAG_BITS), 0)


class BackendPreferenceTests(unittest.TestCase):
    def test_default_backend_uses_iokit_on_macos(self):
        self.assertEqual(hidpp._default_backend_preference("darwin"), "iokit")

    def test_default_backend_uses_auto_elsewhere(self):
        self.assertEqual(hidpp._default_backend_preference("win32"), "auto")
        self.assertEqual(hidpp._default_backend_preference("linux"), "auto")


class SetBackendPreferenceTests(unittest.TestCase):
    def setUp(self):
        # Save original preference so tests don't leak state
        self._original = hidpp.get_backend_preference()

    def tearDown(self):
        hidpp._BACKEND_PREFERENCE = self._original

    def test_set_auto(self):
        hidpp.set_backend_preference("auto")
        self.assertEqual(hidpp.get_backend_preference(), "auto")

    def test_set_invalid_raises(self):
        with self.assertRaises(ValueError):
            hidpp.set_backend_preference("invalid_backend")

    def test_get_returns_current(self):
        original = hidpp.get_backend_preference()
        self.assertIn(original, {"auto", "hidapi", "iokit"})


class VendorHidInfosTests(unittest.TestCase):
    def test_vendor_hid_infos_empty_when_no_backend(self):
        with unittest.mock.patch.object(hidpp, 'HIDAPI_OK', False), \
             unittest.mock.patch.object(hidpp, 'MAC_NATIVE_OK', False):
            result = hidpp.vendor_hid_infos()
            self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
