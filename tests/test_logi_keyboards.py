import unittest

from core.logi_keyboards import (
    CID_DISPLAY_NAMES,
    MX_MECHANICAL_CIDS,
    MX_MECHANICAL_FN_ROW,
    MX_MECHANICAL_MINI_CIDS,
    MX_MECHANICAL_MINI_FN_ROW,
    build_connected_keyboard_info,
    resolve_keyboard,
)


class ResolveKeyboardTests(unittest.TestCase):
    def test_resolve_by_ble_pid_mx_mechanical(self):
        kb = resolve_keyboard(product_id=0xB366)

        self.assertIsNotNone(kb)
        self.assertEqual(kb.key, "mx_mechanical")
        self.assertEqual(kb.display_name, "MX Mechanical")

    def test_resolve_by_ble_pid_mx_mechanical_mini(self):
        kb = resolve_keyboard(product_id=0xB367)

        self.assertIsNotNone(kb)
        self.assertEqual(kb.key, "mx_mechanical_mini")
        self.assertEqual(kb.display_name, "MX Mechanical Mini")

    def test_resolve_by_codename(self):
        kb = resolve_keyboard(product_name="MX MCHNCL")

        self.assertIsNotNone(kb)
        self.assertEqual(kb.key, "mx_mechanical")

    def test_resolve_unknown_returns_none(self):
        kb = resolve_keyboard(product_id=0xFFFF, product_name="Unknown Keyboard X9")

        self.assertIsNone(kb)


class CidTableTests(unittest.TestCase):
    def test_mx_mechanical_cids_count(self):
        self.assertEqual(len(MX_MECHANICAL_CIDS), 41)

    def test_mx_mechanical_mini_cids_count(self):
        self.assertEqual(len(MX_MECHANICAL_MINI_CIDS), 32)

    def test_all_cid_names_are_non_empty_strings(self):
        for cid, name in {**MX_MECHANICAL_CIDS, **MX_MECHANICAL_MINI_CIDS}.items():
            self.assertIsInstance(name, str, msg=f"CID 0x{cid:04X} name is not a string")
            self.assertTrue(name, msg=f"CID 0x{cid:04X} has an empty name")

    def test_all_display_names_are_non_empty_strings(self):
        for cid, label in CID_DISPLAY_NAMES.items():
            self.assertIsInstance(label, str, msg=f"CID 0x{cid:04X} display name is not a string")
            self.assertTrue(label, msg=f"CID 0x{cid:04X} display name is empty")

    def test_fn_row_cids_are_subset_of_mx_mechanical_remappable_cids(self):
        kb = resolve_keyboard(product_id=0xB366)
        self.assertIsNotNone(kb)
        for cid in MX_MECHANICAL_FN_ROW:
            self.assertIn(cid, kb.remappable_cids, msg=f"CID 0x{cid:04X} not in remappable_cids")

    def test_fn_row_cids_are_subset_of_mx_mechanical_mini_remappable_cids(self):
        kb = resolve_keyboard(product_id=0xB367)
        self.assertIsNotNone(kb)
        for cid in MX_MECHANICAL_MINI_FN_ROW:
            self.assertIn(cid, kb.remappable_cids, msg=f"CID 0x{cid:04X} not in remappable_cids")


class KeyboardCapabilitiesTests(unittest.TestCase):
    def test_mx_mechanical_has_backlight(self):
        kb = resolve_keyboard(product_id=0xB366)

        self.assertIsNotNone(kb)
        self.assertTrue(kb.has_backlight)

    def test_mx_mechanical_has_fn_inversion(self):
        kb = resolve_keyboard(product_id=0xB366)

        self.assertIsNotNone(kb)
        self.assertTrue(kb.has_fn_inversion)

    def test_mx_mechanical_mini_has_backlight(self):
        kb = resolve_keyboard(product_id=0xB367)

        self.assertIsNotNone(kb)
        self.assertTrue(kb.has_backlight)

    def test_mx_mechanical_mini_has_fn_inversion(self):
        kb = resolve_keyboard(product_id=0xB367)

        self.assertIsNotNone(kb)
        self.assertTrue(kb.has_fn_inversion)


class BuildConnectedKeyboardInfoTests(unittest.TestCase):
    def test_known_device_uses_catalog_data(self):
        info = build_connected_keyboard_info(
            product_id=0xB366,
            product_name="MX Mechanical",
            transport="Bluetooth Low Energy",
            source="iokit-enumerate",
        )

        self.assertEqual(info.key, "mx_mechanical")
        self.assertEqual(info.display_name, "MX Mechanical")
        self.assertEqual(info.product_id, 0xB366)
        self.assertEqual(info.transport, "Bluetooth Low Energy")
        self.assertEqual(info.source, "iokit-enumerate")
        self.assertTrue(info.has_backlight)
        self.assertTrue(info.has_fn_inversion)
        self.assertEqual(len(info.remappable_cids), 41)

    def test_unknown_device_falls_back_to_generic(self):
        info = build_connected_keyboard_info(
            product_id=0xBEEF,
            product_name="Mystery Logitech Keyboard",
        )

        self.assertEqual(info.display_name, "Mystery Logitech Keyboard")
        self.assertEqual(info.key, "mystery_logitech_keyboard")
        self.assertEqual(info.ui_layout, "generic_keyboard")
        self.assertEqual(info.remappable_cids, {})

    def test_unknown_device_no_pid_no_name_fallback(self):
        info = build_connected_keyboard_info()

        self.assertEqual(info.display_name, "Logitech keyboard")
        self.assertEqual(info.ui_layout, "generic_keyboard")

    def test_unknown_device_pid_only_formats_name(self):
        info = build_connected_keyboard_info(product_id=0xBEEF)

        self.assertEqual(info.display_name, "Logitech PID 0xBEEF")
        self.assertEqual(info.product_id, 0xBEEF)


if __name__ == "__main__":
    unittest.main()
