"""
Keyboard visual layout registry for Mouser's interactive keyboard view.
"""

from __future__ import annotations

from copy import deepcopy


GENERIC_KEYBOARD_LAYOUT = {
    "key": "generic_keyboard",
    "label": "Generic keyboard",
    "image_asset": "icons/keyboard.svg",
    "image_width": 800,
    "image_height": 300,
    "interactive": False,
    "hotspots": [],
}

MX_MECHANICAL_LAYOUT = {
    "key": "mx_mechanical",
    "label": "MX Mechanical",
    "image_asset": "keyboard_mx_mechanical.svg",
    "image_width": 800,
    "image_height": 300,
    "interactive": True,
    "hotspots": [
        # F-row (12 keys)
        {"buttonKey": "0x00C7", "label": "F1\nBrightness -", "normX": 0.12, "normY": 0.10, "region": "fn_row"},
        {"buttonKey": "0x00C8", "label": "F2\nBrightness +", "normX": 0.17, "normY": 0.10, "region": "fn_row"},
        {"buttonKey": "0x00E2", "label": "F3\nBacklight -", "normX": 0.22, "normY": 0.10, "region": "fn_row"},
        {"buttonKey": "0x00E3", "label": "F4\nBacklight +", "normX": 0.27, "normY": 0.10, "region": "fn_row"},
        {"buttonKey": "0x0103", "label": "F5\nDictation", "normX": 0.34, "normY": 0.10, "region": "fn_row"},
        {"buttonKey": "0x0108", "label": "F6\nEmoji", "normX": 0.39, "normY": 0.10, "region": "fn_row"},
        {"buttonKey": "0x010A", "label": "F7\nSnipping", "normX": 0.44, "normY": 0.10, "region": "fn_row"},
        {"buttonKey": "0x011C", "label": "F8\nMic Mute", "normX": 0.49, "normY": 0.10, "region": "fn_row"},
        {"buttonKey": "0x00E4", "label": "F9\nPrev", "normX": 0.56, "normY": 0.10, "region": "fn_row"},
        {"buttonKey": "0x00E5", "label": "F10\nPlay/Pause", "normX": 0.61, "normY": 0.10, "region": "fn_row"},
        {"buttonKey": "0x00E6", "label": "F11\nNext", "normX": 0.66, "normY": 0.10, "region": "fn_row"},
        {"buttonKey": "0x00E7", "label": "F12\nMute", "normX": 0.71, "normY": 0.10, "region": "fn_row"},
        # Modifiers (bottom row)
        {"buttonKey": "0x010F", "label": "L Ctrl", "normX": 0.04, "normY": 0.90, "region": "modifiers"},
        {"buttonKey": "0x0110", "label": "L Win/Opt", "normX": 0.11, "normY": 0.90, "region": "modifiers"},
        {"buttonKey": "0x0111", "label": "L Alt/Cmd", "normX": 0.18, "normY": 0.90, "region": "modifiers"},
        {"buttonKey": "0x0112", "label": "R Alt/Cmd", "normX": 0.55, "normY": 0.90, "region": "modifiers"},
        {"buttonKey": "0x0113", "label": "R Win/Opt", "normX": 0.62, "normY": 0.90, "region": "modifiers"},
        {"buttonKey": "0x0114", "label": "R Ctrl", "normX": 0.72, "normY": 0.90, "region": "modifiers"},
        # Nav cluster
        {"buttonKey": "0x0116", "label": "Insert", "normX": 0.82, "normY": 0.25, "region": "nav"},
        {"buttonKey": "0x0117", "label": "Delete", "normX": 0.82, "normY": 0.42, "region": "nav"},
        {"buttonKey": "0x0118", "label": "Home", "normX": 0.88, "normY": 0.25, "region": "nav"},
        {"buttonKey": "0x0119", "label": "End", "normX": 0.88, "normY": 0.42, "region": "nav"},
        {"buttonKey": "0x011A", "label": "PgUp", "normX": 0.94, "normY": 0.25, "region": "nav"},
        {"buttonKey": "0x011B", "label": "PgDn", "normX": 0.94, "normY": 0.42, "region": "nav"},
        # Special keys
        {"buttonKey": "0x010D", "label": "Caps Lock", "normX": 0.06, "normY": 0.56, "region": "special"},
        {"buttonKey": "0x010B", "label": "` ~", "normX": 0.04, "normY": 0.25, "region": "special"},
        {"buttonKey": "0x010C", "label": "Tab", "normX": 0.05, "normY": 0.42, "region": "special"},
        {"buttonKey": "0x011E", "label": "\\", "normX": 0.70, "normY": 0.42, "region": "special"},
        # Utility keys
        {"buttonKey": "0x000A", "label": "Calc", "normX": 0.82, "normY": 0.10, "region": "utility"},
        {"buttonKey": "0x006E", "label": "Desktop", "normX": 0.88, "normY": 0.10, "region": "utility"},
        {"buttonKey": "0x00D4", "label": "Search", "normX": 0.94, "normY": 0.10, "region": "utility"},
        {"buttonKey": "0x006F", "label": "Lock", "normX": 0.78, "normY": 0.10, "region": "utility"},
    ],
}

MX_MECHANICAL_MINI_LAYOUT = {
    "key": "mx_mechanical_mini",
    "label": "MX Mechanical Mini",
    "image_asset": "keyboard_mx_mechanical_mini.svg",
    "image_width": 700,
    "image_height": 280,
    "interactive": True,
    "hotspots": [
        # Fn-row (Mini has fewer keys)
        {"buttonKey": "0x00E2", "label": "F4\nBacklight -", "normX": 0.27, "normY": 0.10, "region": "fn_row"},
        {"buttonKey": "0x00E3", "label": "F5\nBacklight +", "normX": 0.33, "normY": 0.10, "region": "fn_row"},
        {"buttonKey": "0x0103", "label": "F6\nDictation", "normX": 0.39, "normY": 0.10, "region": "fn_row"},
        {"buttonKey": "0x0108", "label": "F7\nEmoji", "normX": 0.45, "normY": 0.10, "region": "fn_row"},
        {"buttonKey": "0x010A", "label": "F8\nSnipping", "normX": 0.51, "normY": 0.10, "region": "fn_row"},
        {"buttonKey": "0x011C", "label": "F9\nMic Mute", "normX": 0.57, "normY": 0.10, "region": "fn_row"},
        {"buttonKey": "0x00D4", "label": "F10\nSearch", "normX": 0.63, "normY": 0.10, "region": "fn_row"},
        {"buttonKey": "0x0141", "label": "F11\nPlay", "normX": 0.69, "normY": 0.10, "region": "fn_row"},
        {"buttonKey": "0x00E7", "label": "F12\nMute", "normX": 0.75, "normY": 0.10, "region": "fn_row"},
        # Modifiers
        {"buttonKey": "0x010F", "label": "L Ctrl", "normX": 0.04, "normY": 0.90, "region": "modifiers"},
        {"buttonKey": "0x0110", "label": "L Win/Opt", "normX": 0.12, "normY": 0.90, "region": "modifiers"},
        {"buttonKey": "0x0111", "label": "L Alt/Cmd", "normX": 0.20, "normY": 0.90, "region": "modifiers"},
        {"buttonKey": "0x0112", "label": "R Alt/Cmd", "normX": 0.60, "normY": 0.90, "region": "modifiers"},
        {"buttonKey": "0x013C", "label": "R Win/Opt", "normX": 0.68, "normY": 0.90, "region": "modifiers"},
        {"buttonKey": "0x0115", "label": "R Shift", "normX": 0.80, "normY": 0.74, "region": "modifiers"},
        # Nav
        {"buttonKey": "0x0117", "label": "Del", "normX": 0.90, "normY": 0.10, "region": "nav"},
        {"buttonKey": "0x0118", "label": "Home", "normX": 0.90, "normY": 0.28, "region": "nav"},
        {"buttonKey": "0x0119", "label": "End", "normX": 0.90, "normY": 0.44, "region": "nav"},
        {"buttonKey": "0x011A", "label": "PgUp", "normX": 0.96, "normY": 0.28, "region": "nav"},
        {"buttonKey": "0x011B", "label": "PgDn", "normX": 0.96, "normY": 0.44, "region": "nav"},
        # Special
        {"buttonKey": "0x010D", "label": "Caps", "normX": 0.06, "normY": 0.56, "region": "special"},
        {"buttonKey": "0x010B", "label": "` ~", "normX": 0.04, "normY": 0.28, "region": "special"},
        {"buttonKey": "0x010C", "label": "Tab", "normX": 0.05, "normY": 0.42, "region": "special"},
        {"buttonKey": "0x011E", "label": "\\", "normX": 0.75, "normY": 0.42, "region": "special"},
    ],
}

KEYBOARD_LAYOUTS = {
    "mx_mechanical": MX_MECHANICAL_LAYOUT,
    "mx_mechanical_mini": MX_MECHANICAL_MINI_LAYOUT,
    "generic_keyboard": GENERIC_KEYBOARD_LAYOUT,
}


def get_keyboard_layout(layout_key: str | None = None) -> dict:
    layout = KEYBOARD_LAYOUTS.get(layout_key or "", GENERIC_KEYBOARD_LAYOUT)
    return deepcopy(layout)
