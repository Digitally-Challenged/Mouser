"""
Known Logitech keyboard metadata for Mouser's keyboard remapping support.

Mirrors the structure of logi_devices.py for mice. Catalogs HID++ keyboards,
providing enough structure to identify connected devices, surface the right
model name in the UI, and associate per-device CID remapping tables.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


# ---------------------------------------------------------------------------
# CID tables
# ---------------------------------------------------------------------------

# Full-size MX Mechanical (BLE PID 0xB366) — 41 CIDs
MX_MECHANICAL_CIDS: dict[int, str] = {
    0x00C7: "escape",
    0x00C8: "f1",
    0x00C9: "f2",
    0x00CA: "f3",
    0x00CB: "f4",
    0x00CC: "f5",
    0x00CD: "f6",
    0x00CE: "f7",
    0x00CF: "f8",
    0x00D0: "f9",
    0x00D5: "f10",
    0x00D6: "f11",
    0x00D7: "f12",
    0x010A: "brightness_down",
    0x010B: "brightness_up",
    0x010C: "mission_control",
    0x010D: "launchpad",
    0x010E: "dictation",
    0x010F: "do_not_disturb",
    0x0110: "prev_track",
    0x0111: "play_pause",
    0x0112: "next_track",
    0x0113: "mute",
    0x0114: "volume_down",
    0x0115: "volume_up",
    0x0116: "screen_lock",
    0x0117: "emoji",
    0x0118: "calculator",
    0x0119: "show_desktop",
    0x011A: "lock_pc",
    0x011D: "insert",
    0x011E: "right_option",
    0x000A: "backspace",
    0x006E: "delete_forward",
    0x00D4: "right_ctrl",
    0x006F: "end",
    0x00D1: "fn",
    0x00D2: "fn_lock",
    0x00D3: "smart_action",
    0x00DE: "easy_switch",
    0x0034: "gesture_button",
}

# MX Mechanical Mini (BLE PID 0xB367) — 32 CIDs
# Drops: brightness_{down,up}, prev_track, play_pause, next_track,
#        calculator, show_desktop, lock_pc, insert, right_option, right_ctrl.
# Adds: right_option_2 (0x013C), play_pause_mini (0x0141).
MX_MECHANICAL_MINI_CIDS: dict[int, str] = {
    0x00C7: "escape",
    0x00C8: "f1",
    0x00C9: "f2",
    0x00CA: "f3",
    0x00CB: "f4",
    0x00CC: "f5",
    0x00CD: "f6",
    0x00CE: "f7",
    0x00CF: "f8",
    0x00D0: "f9",
    0x00D5: "f10",
    0x00D6: "f11",
    0x00D7: "f12",
    0x010C: "mission_control",
    0x010D: "launchpad",
    0x010E: "dictation",
    0x010F: "do_not_disturb",
    0x0113: "mute",
    0x0114: "volume_down",
    0x0115: "volume_up",
    0x0116: "screen_lock",
    0x0117: "emoji",
    0x000A: "backspace",
    0x006E: "delete_forward",
    0x006F: "end",
    0x00D1: "fn",
    0x00D2: "fn_lock",
    0x00D3: "smart_action",
    0x00DE: "easy_switch",
    0x0034: "gesture_button",
    0x013C: "right_option_2",
    0x0141: "play_pause_mini",
}

# CIDs that are reported by the device but cannot be remapped
NON_DIVERTABLE_CIDS: frozenset[int] = frozenset({
    0x00D1,  # fn
    0x00D2,  # fn_lock
    0x00D3,  # smart_action
    0x00DE,  # easy_switch
    0x0034,  # gesture_button
})

# Human-readable labels for the UI — covers all CIDs in both catalogs
CID_DISPLAY_NAMES: dict[int, str] = {
    0x000A: "Backspace",
    0x0034: "Gesture Button",
    0x006E: "Delete Forward",
    0x006F: "End",
    0x00C7: "Escape",
    0x00C8: "F1",
    0x00C9: "F2",
    0x00CA: "F3",
    0x00CB: "F4",
    0x00CC: "F5",
    0x00CD: "F6",
    0x00CE: "F7",
    0x00CF: "F8",
    0x00D0: "F9",
    0x00D1: "Fn",
    0x00D2: "Fn Lock",
    0x00D3: "Smart Action",
    0x00D4: "Right Ctrl",
    0x00D5: "F10",
    0x00D6: "F11",
    0x00D7: "F12",
    0x00DE: "Easy Switch",
    0x010A: "Brightness Down",
    0x010B: "Brightness Up",
    0x010C: "Mission Control",
    0x010D: "Launchpad",
    0x010E: "Dictation",
    0x010F: "Do Not Disturb",
    0x0110: "Previous Track",
    0x0111: "Play / Pause",
    0x0112: "Next Track",
    0x0113: "Mute",
    0x0114: "Volume Down",
    0x0115: "Volume Up",
    0x0116: "Screen Lock",
    0x0117: "Emoji",
    0x0118: "Calculator",
    0x0119: "Show Desktop",
    0x011A: "Lock PC",
    0x011B: "Caps Lock",
    0x011C: "Print Screen",
    0x011D: "Insert",
    0x011E: "Right Option",
    0x013C: "Right Option 2",
    0x0141: "Play / Pause (Mini)",
}

# F-row CID tuples in display order (left to right)
MX_MECHANICAL_FN_ROW: tuple[int, ...] = (
    0x00C7,  # Escape
    0x00C8,  # F1
    0x00C9,  # F2
    0x00CA,  # F3
    0x00CB,  # F4
    0x00CC,  # F5
    0x00CD,  # F6
    0x00CE,  # F7
    0x00CF,  # F8
    0x00D0,  # F9
    0x00D5,  # F10
    0x00D6,  # F11
    0x00D7,  # F12
)

MX_MECHANICAL_MINI_FN_ROW: tuple[int, ...] = (
    0x00C7,  # Escape
    0x00C8,  # F1
    0x00C9,  # F2
    0x00CA,  # F3
    0x00CB,  # F4
    0x00CC,  # F5
    0x00CD,  # F6
    0x00CE,  # F7
    0x00CF,  # F8
    0x00D0,  # F9
    0x00D5,  # F10
    0x00D6,  # F11
    0x00D7,  # F12
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LogiKeyboardSpec:
    key: str
    display_name: str
    ble_pids: tuple[int, ...] = ()
    codename: str = ""
    aliases: tuple[str, ...] = ()
    remappable_cids: dict[int, str] = None  # type: ignore[assignment]
    fn_row_cids: tuple[int, ...] = ()
    has_backlight: bool = False
    has_fn_inversion: bool = False
    ui_layout: str = "generic_keyboard"
    image_asset: str = "icons/keyboard-simple.svg"

    def __post_init__(self) -> None:
        # Replace None sentinel with empty dict (frozen dataclass workaround)
        if self.remappable_cids is None:
            object.__setattr__(self, "remappable_cids", {})

    def matches(self, product_id: int | None = None, product_name: str | None = None) -> bool:
        if product_id is not None and int(product_id) in self.ble_pids:
            return True
        normalized = _normalize_name(product_name)
        if not normalized:
            return False
        candidates = (self.display_name, self.key, self.codename, *self.aliases)
        return any(_normalize_name(c) == normalized for c in candidates)


@dataclass(frozen=True)
class ConnectedKeyboardInfo:
    key: str
    display_name: str
    product_id: int | None = None
    product_name: str | None = None
    transport: str | None = None
    source: str | None = None
    ui_layout: str = "generic_keyboard"
    image_asset: str = "icons/keyboard-simple.svg"
    remappable_cids: dict[int, str] = None  # type: ignore[assignment]
    fn_row_cids: tuple[int, ...] = ()
    has_backlight: bool = False
    has_fn_inversion: bool = False

    def __post_init__(self) -> None:
        if self.remappable_cids is None:
            object.__setattr__(self, "remappable_cids", {})


# ---------------------------------------------------------------------------
# Device catalog
# ---------------------------------------------------------------------------

KNOWN_KEYBOARDS: tuple[LogiKeyboardSpec, ...] = (
    LogiKeyboardSpec(
        key="mx_mechanical",
        display_name="MX Mechanical",
        ble_pids=(0xB366,),
        codename="MX MCHNCL",
        aliases=("Logitech MX Mechanical", "MX Mechanical for Mac"),
        remappable_cids=MX_MECHANICAL_CIDS,
        fn_row_cids=MX_MECHANICAL_FN_ROW,
        has_backlight=True,
        has_fn_inversion=True,
        ui_layout="mx_mechanical",
        image_asset="icons/keyboard-mx-mechanical.svg",
    ),
    LogiKeyboardSpec(
        key="mx_mechanical_mini",
        display_name="MX Mechanical Mini",
        ble_pids=(0xB367,),
        codename="MX MCHNCL MINI",
        aliases=("Logitech MX Mechanical Mini", "MX Mechanical Mini for Mac"),
        remappable_cids=MX_MECHANICAL_MINI_CIDS,
        fn_row_cids=MX_MECHANICAL_MINI_FN_ROW,
        has_backlight=True,
        has_fn_inversion=True,
        ui_layout="mx_mechanical_mini",
        image_asset="icons/keyboard-mx-mechanical-mini.svg",
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_name(value: object) -> str:
    if not value:
        return ""
    return " ".join(str(value).strip().lower().replace("_", " ").split())


def iter_known_keyboards() -> Iterable[LogiKeyboardSpec]:
    return KNOWN_KEYBOARDS


def resolve_keyboard(
    product_id: int | None = None,
    product_name: str | None = None,
) -> LogiKeyboardSpec | None:
    """Return the first matching LogiKeyboardSpec or None."""
    for kb in KNOWN_KEYBOARDS:
        if kb.matches(product_id=product_id, product_name=product_name):
            return kb
    return None


def build_connected_keyboard_info(
    product_id: int | None = None,
    product_name: str | None = None,
    transport: str | None = None,
    source: str | None = None,
) -> ConnectedKeyboardInfo:
    """Build runtime info for a connected keyboard.

    Falls back to a generic entry when the device is not in the catalog.
    """
    spec = resolve_keyboard(product_id=product_id, product_name=product_name)
    pid = int(product_id) if product_id not in (None, "") else None

    if spec:
        return ConnectedKeyboardInfo(
            key=spec.key,
            display_name=spec.display_name,
            product_id=pid,
            product_name=product_name or spec.display_name,
            transport=transport,
            source=source,
            ui_layout=spec.ui_layout,
            image_asset=spec.image_asset,
            remappable_cids=spec.remappable_cids,
            fn_row_cids=spec.fn_row_cids,
            has_backlight=spec.has_backlight,
            has_fn_inversion=spec.has_fn_inversion,
        )

    display_name = product_name or (
        f"Logitech PID 0x{pid:04X}" if pid is not None else "Logitech keyboard"
    )
    key = _normalize_name(display_name).replace(" ", "_") or "logitech_keyboard"
    return ConnectedKeyboardInfo(
        key=key,
        display_name=display_name,
        product_id=pid,
        product_name=product_name or display_name,
        transport=transport,
        source=source,
        ui_layout="generic_keyboard",
        image_asset="icons/keyboard-simple.svg",
    )
