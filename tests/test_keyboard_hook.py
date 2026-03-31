import unittest
from unittest.mock import MagicMock

from core.keyboard_hook import KeyboardHook


class KeyboardHookTests(unittest.TestCase):
    def test_register_and_dispatch(self):
        hook = KeyboardHook()
        handler = MagicMock()
        hook.register(0x010A, handler)
        hook.on_key_event(0x010A, True)
        handler.assert_called_once_with(0x010A, True)

    def test_dispatch_unregistered_cid_is_noop(self):
        hook = KeyboardHook()
        hook.on_key_event(0x010A, True)  # Should not raise

    def test_register_multiple_cids(self):
        hook = KeyboardHook()
        h1 = MagicMock()
        h2 = MagicMock()
        hook.register(0x010A, h1)
        hook.register(0x0108, h2)
        hook.on_key_event(0x010A, True)
        hook.on_key_event(0x0108, False)
        h1.assert_called_once_with(0x010A, True)
        h2.assert_called_once_with(0x0108, False)

    def test_reset_clears_handlers(self):
        hook = KeyboardHook()
        handler = MagicMock()
        hook.register(0x010A, handler)
        hook.reset()
        hook.on_key_event(0x010A, True)
        handler.assert_not_called()

    def test_handler_exception_is_caught(self):
        hook = KeyboardHook()
        handler = MagicMock(side_effect=RuntimeError("test error"))
        hook.register(0x010A, handler)
        # Should not raise, error is caught internally
        hook.on_key_event(0x010A, True)
        handler.assert_called_once()

    def test_key_release_event(self):
        hook = KeyboardHook()
        handler = MagicMock()
        hook.register(0x010A, handler)
        hook.on_key_event(0x010A, False)
        handler.assert_called_once_with(0x010A, False)
