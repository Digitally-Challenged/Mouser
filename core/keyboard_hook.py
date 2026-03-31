"""
keyboard_hook.py — Keyboard event dispatch layer.

Receives diverted key events from KeyboardHidListener and dispatches
them to registered handlers (which execute actions via key_simulator).
"""

from __future__ import annotations


class KeyboardHook:
    """Maps diverted keyboard CID events to action handlers."""

    def __init__(self):
        self._handlers: dict[int, object] = {}  # cid → callable(cid, pressed)

    def register(self, cid: int, handler) -> None:
        """Register a handler for a specific CID."""
        self._handlers[cid] = handler

    def reset(self) -> None:
        """Clear all registered handlers."""
        self._handlers.clear()

    def on_key_event(self, cid: int, pressed: bool) -> None:
        """Called by KeyboardHidListener when a diverted key is pressed/released."""
        handler = self._handlers.get(cid)
        if handler:
            try:
                handler(cid, pressed)
            except Exception as e:
                print(f"[KeyboardHook] handler error for CID 0x{cid:04X}: {e}")
