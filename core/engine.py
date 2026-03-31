"""
Engine — wires the mouse hook and keyboard hook to the key simulator
using the current configuration.  Sits between the hook layer and the UI.
Supports per-application auto-switching of profiles for both devices.
"""

import threading
from core.mouse_hook import MouseHook, MouseEvent
from core.keyboard_hid import KeyboardHidListener
from core.keyboard_hook import KeyboardHook
from core.bolt_mux import BoltMultiplexer
from core.key_simulator import ACTIONS, execute_action
from core.config import (
    load_config, get_active_mappings, get_profile_for_app,
    BUTTON_TO_EVENTS, GESTURE_DIRECTION_BUTTONS, save_config,
)
from core.app_detector import AppDetector
from core.logi_devices import clamp_dpi
from core.logi_keyboards import CID_DISPLAY_NAMES, NON_DIVERTABLE_CIDS


class Engine:
    """
    Core logic: reads config, installs the mouse hook,
    dispatches actions when mapped buttons are pressed,
    and auto-switches profiles when the foreground app changes.
    """

    def __init__(self):
        self.hook = MouseHook()
        self.cfg = load_config()
        self._enabled = True
        self._hscroll_accum = 0
        self._current_profile: str = (
            self.cfg.get("devices", {}).get("mouse", {}).get("active_profile", "default")
        )
        self._current_kb_profile: str = (
            self.cfg.get("devices", {}).get("keyboard", {}).get("active_profile", "default")
        )
        self._app_detector = AppDetector(self._on_app_change)
        self._profile_change_cb = None       # UI callback
        self._connection_change_cb = None   # UI callback for device status
        self._battery_read_cb = None        # UI callback for battery level
        self._dpi_read_cb = None            # UI callback for current DPI
        self._debug_cb = None               # UI callback for debug messages
        self._gesture_event_cb = None       # UI callback for structured gesture events
        self._debug_events_enabled = bool(
            self.cfg.get("devices", {}).get("mouse", {}).get("settings", {}).get("debug_mode", False)
        )
        self._battery_poll_stop = threading.Event()
        self._lock = threading.Lock()
        self.hook.set_debug_callback(self._emit_debug)
        self.hook.set_gesture_callback(self._emit_gesture_event)
        self._setup_hooks()
        self.hook.set_connection_change_callback(self._on_connection_change)

        # Bolt multiplexer — shared connection for mouse + keyboard on same receiver
        self._bolt_mux = None
        self._bolt_mouse_channel = None
        self._bolt_keyboard_channel = None

        # Keyboard support
        self.keyboard_hook = KeyboardHook()
        self._keyboard_hid = KeyboardHidListener(
            on_key_diverted=self._on_keyboard_key_event,
            on_connect=self._on_keyboard_connect,
            on_disconnect=self._on_keyboard_disconnect,
        )
        self._keyboard_connection_cb = None
        self._keyboard_battery_cb = None
        self._keyboard_battery_poll_stop = threading.Event()
        self._setup_keyboard_hooks()

        # Apply persisted DPI setting
        dpi = self.cfg.get("devices", {}).get("mouse", {}).get("settings", {}).get("dpi", 1000)
        try:
            if hasattr(self.hook, "set_dpi"):
                self.hook.set_dpi(dpi)
        except Exception as e:
            print(f"[Engine] Failed to set DPI: {e}")

    # ------------------------------------------------------------------
    # Hook wiring
    # ------------------------------------------------------------------
    def _setup_hooks(self):
        """Register callbacks and block events for all mapped buttons."""
        mappings = get_active_mappings(self.cfg)

        # Apply scroll inversion settings to the hook
        settings = self.cfg.get("devices", {}).get("mouse", {}).get("settings", {})
        self.hook.invert_vscroll = settings.get("invert_vscroll", False)
        self.hook.invert_hscroll = settings.get("invert_hscroll", False)
        self.hook.debug_mode = self._debug_events_enabled
        self.hook.configure_gestures(
            enabled=any(mappings.get(key, "none") != "none"
                        for key in GESTURE_DIRECTION_BUTTONS),
            threshold=settings.get("gesture_threshold", 50),
            deadzone=settings.get("gesture_deadzone", 40),
            timeout_ms=settings.get("gesture_timeout_ms", 3000),
            cooldown_ms=settings.get("gesture_cooldown_ms", 500),
        )
        self._emit_mapping_snapshot("Hook mappings refreshed", mappings)

        for btn_key, action_id in mappings.items():
            events = list(BUTTON_TO_EVENTS.get(btn_key, ()))

            for evt_type in events:
                if evt_type.endswith("_up"):
                    if action_id != "none":
                        self.hook.block(evt_type)
                    continue

                if action_id != "none":
                    self.hook.block(evt_type)

                    if "hscroll" in evt_type:
                        self.hook.register(evt_type, self._make_hscroll_handler(action_id))
                    else:
                        self.hook.register(evt_type, self._make_handler(action_id))

    def _make_handler(self, action_id):
        def handler(event):
            if self._enabled:
                self._emit_debug(
                    f"Mapped {event.event_type} -> {action_id} "
                    f"({self._action_label(action_id)})"
                )
                if event.event_type.startswith("gesture_"):
                    self._emit_gesture_event({
                        "type": "mapped",
                        "event_name": event.event_type,
                        "action_id": action_id,
                        "action_label": self._action_label(action_id),
                    })
                execute_action(action_id)
        return handler

    def _make_hscroll_handler(self, action_id):
        def handler(event):
            if not self._enabled:
                return
            self._emit_debug(
                f"Mapped {event.event_type} -> {action_id} "
                f"({self._action_label(action_id)})"
            )
            execute_action(action_id)
        return handler

    # ------------------------------------------------------------------
    # Keyboard hook wiring
    # ------------------------------------------------------------------
    def _setup_keyboard_hooks(self):
        """Register keyboard key->action mappings from config."""
        mappings = get_active_mappings(self.cfg, device="keyboard")
        self.keyboard_hook.reset()
        mapped_cids: set[int] = set()
        for cid_str, action_id in mappings.items():
            if action_id == "none":
                continue
            try:
                cid = int(cid_str, 16) if isinstance(cid_str, str) else int(cid_str)
            except (ValueError, TypeError):
                continue
            mapped_cids.add(cid)
            self.keyboard_hook.register(cid, self._make_keyboard_handler(action_id))
        # Tell the HID listener to only divert keys that have mappings
        # (unmapped keys like Caps Lock keep their normal OS behaviour)
        if self._keyboard_hid.connected and hasattr(self._keyboard_hid, 'divert_cids'):
            self._keyboard_hid.divert_cids(mapped_cids)

    def _make_keyboard_handler(self, action_id):
        def handler(cid, pressed):
            if pressed and self._enabled:
                self._emit_debug(
                    f"Keyboard CID 0x{cid:04X} -> {action_id} "
                    f"({self._action_label(action_id)})"
                )
                execute_action(action_id)
        return handler

    def _on_keyboard_key_event(self, cid: int, pressed: bool):
        """Called by KeyboardHidListener when a diverted key is pressed/released."""
        if pressed:
            self.keyboard_hook.on_key_event(cid, True)
        else:
            self.keyboard_hook.on_key_event(cid, False)

    def _on_keyboard_connect(self):
        if self._keyboard_connection_cb:
            try:
                self._keyboard_connection_cb(True)
            except Exception:
                pass
        # Start battery polling
        self._keyboard_battery_poll_stop = threading.Event()
        threading.Thread(
            target=self._keyboard_battery_poll_loop,
            args=(self._keyboard_battery_poll_stop,),
            daemon=True,
            name="KeyboardBatteryPoll",
        ).start()

    def _on_keyboard_disconnect(self):
        self._keyboard_battery_poll_stop.set()
        if self._keyboard_connection_cb:
            try:
                self._keyboard_connection_cb(False)
            except Exception:
                pass

    def _keyboard_battery_poll_loop(self, stop_event):
        if stop_event.wait(1):
            return
        while not stop_event.is_set():
            level = self._keyboard_hid.read_battery()
            if stop_event.is_set():
                return
            if level is not None and self._keyboard_battery_cb:
                try:
                    self._keyboard_battery_cb(level)
                except Exception:
                    pass
            if stop_event.wait(300):
                return

    # ------------------------------------------------------------------
    # Per-app auto-switching
    # ------------------------------------------------------------------
    def _on_app_change(self, exe_name: str):
        """Called by AppDetector when foreground window changes."""
        target_mouse = get_profile_for_app(self.cfg, exe_name, device="mouse")
        target_kb = get_profile_for_app(self.cfg, exe_name, device="keyboard")

        mouse_changed = target_mouse != self._current_profile
        kb_changed = target_kb != self._current_kb_profile

        if mouse_changed:
            print(f"[Engine] App changed to {exe_name} -> mouse profile '{target_mouse}'")
            self._switch_profile(target_mouse)
        if kb_changed:
            print(f"[Engine] App changed to {exe_name} -> keyboard profile '{target_kb}'")
            self._switch_keyboard_profile(target_kb)

    def _switch_profile(self, profile_name: str):
        with self._lock:
            self.cfg["devices"]["mouse"]["active_profile"] = profile_name
            self._current_profile = profile_name
            # Lightweight: just re-wire callbacks, keep hook + HID++ alive
            self.hook.reset_bindings()
            self._setup_hooks()
            self._emit_debug(f"Active mouse profile -> {profile_name}")
        # Notify UI (if connected)
        if self._profile_change_cb:
            try:
                self._profile_change_cb(profile_name)
            except Exception:
                pass

    def _switch_keyboard_profile(self, profile_name: str):
        with self._lock:
            self.cfg["devices"]["keyboard"]["active_profile"] = profile_name
            self._current_kb_profile = profile_name
            self._setup_keyboard_hooks()
            self._emit_debug(f"Active keyboard profile -> {profile_name}")

    def set_profile_change_callback(self, cb):
        """Register a callback ``cb(profile_name)`` invoked on auto-switch."""
        self._profile_change_cb = cb

    def set_debug_callback(self, cb):
        """Register ``cb(message: str)`` invoked for debug events."""
        self._debug_cb = cb

    def set_gesture_event_callback(self, cb):
        """Register ``cb(event: dict)`` invoked for structured gesture debug events."""
        self._gesture_event_cb = cb

    def set_debug_enabled(self, enabled):
        enabled = bool(enabled)
        self.cfg.setdefault("devices", {}).setdefault("mouse", {}).setdefault("settings", {})["debug_mode"] = enabled
        self._debug_events_enabled = enabled
        self.hook.debug_mode = enabled
        if enabled:
            self._emit_debug(f"Debug enabled on profile {self._current_profile}")
            self._emit_mapping_snapshot(
                "Current mappings", get_active_mappings(self.cfg)
            )

    def set_debug_events_enabled(self, enabled):
        self._debug_events_enabled = bool(enabled)
        self.hook.debug_mode = self._debug_events_enabled

    def _action_label(self, action_id):
        return ACTIONS.get(action_id, {}).get("label", action_id)

    def _emit_debug(self, message):
        if not self._debug_events_enabled:
            return
        if self._debug_cb:
            try:
                self._debug_cb(message)
            except Exception:
                pass

    def _emit_gesture_event(self, event):
        if not self._debug_events_enabled:
            return
        if self._gesture_event_cb:
            try:
                self._gesture_event_cb(event)
            except Exception:
                pass

    def _emit_mapping_snapshot(self, prefix, mappings):
        if not self._debug_events_enabled:
            return
        interesting = [
            "gesture",
            "gesture_left",
            "gesture_right",
            "gesture_up",
            "gesture_down",
            "xbutton1",
            "xbutton2",
        ]
        summary = ", ".join(f"{key}={mappings.get(key, 'none')}" for key in interesting)
        self._emit_debug(f"{prefix}: {summary}")

    def _on_connection_change(self, connected):
        self._battery_poll_stop.set()
        if self._connection_change_cb:
            try:
                self._connection_change_cb(connected)
            except Exception:
                pass
        if connected:
            self._battery_poll_stop = threading.Event()
            threading.Thread(
                target=self._battery_poll_loop,
                args=(self._battery_poll_stop,),
                daemon=True,
                name="BatteryPoll",
            ).start()

    def _battery_poll_loop(self, stop_event):
        """Read battery on connect and refresh it periodically until disconnected."""
        if stop_event.wait(1):
            return
        while not stop_event.is_set():
            hg = self.hook._hid_gesture
            if hg:
                level = hg.read_battery()
                if stop_event.is_set():
                    return
                if level is not None and self._battery_read_cb:
                    try:
                        self._battery_read_cb(level)
                    except Exception:
                        pass
            if stop_event.wait(300):
                return

    def set_battery_callback(self, cb):
        """Register ``cb(level: int)`` invoked when battery level is read (0-100)."""
        self._battery_read_cb = cb

    def set_connection_change_callback(self, cb):
        """Register ``cb(connected: bool)`` invoked on device connect/disconnect."""
        self._connection_change_cb = cb

    @property
    def device_connected(self):
        return self.hook.device_connected

    @property
    def connected_device(self):
        return getattr(self.hook, "connected_device", None)

    @property
    def enabled(self):
        return self._enabled

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_dpi(self, dpi_value):
        """Send DPI change to the mouse via HID++."""
        dpi = clamp_dpi(dpi_value, self.connected_device)
        self.cfg.setdefault("devices", {}).setdefault("mouse", {}).setdefault("settings", {})["dpi"] = dpi
        save_config(self.cfg)
        # Try via the hook's HidGestureListener
        hg = self.hook._hid_gesture
        if hg:
            return hg.set_dpi(dpi)
        print("[Engine] No HID++ connection — DPI not applied")
        return False

    def reload_mappings(self):
        """
        Called by the UI when the user changes a mapping.
        Re-wire callbacks without tearing down the hook or HID++.
        """
        with self._lock:
            self.cfg = load_config()
            self._current_profile = (
                self.cfg.get("devices", {}).get("mouse", {}).get("active_profile", "default")
            )
            self._current_kb_profile = (
                self.cfg.get("devices", {}).get("keyboard", {}).get("active_profile", "default")
            )
            self.hook.reset_bindings()
            self._setup_hooks()
            self._setup_keyboard_hooks()
            self._emit_debug(f"reload_mappings mouse={self._current_profile} keyboard={self._current_kb_profile}")

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)

    def _try_bolt_multiplexer(self):
        """Try to open a shared Bolt receiver connection for both devices."""
        from core.hidpp import FEAT_BACKLIGHT2, FEAT_REPROG_V4
        mux = BoltMultiplexer()
        if not mux.open():
            return
        print("[Engine] Bolt receiver opened — scanning device indices…")
        indices = mux.scan_device_indices()
        if not indices:
            print("[Engine] No devices found on Bolt receiver")
            mux.stop()
            return

        # Identify which index is mouse vs keyboard by probing for BACKLIGHT2
        # (keyboards have it, mice don't)
        mouse_idx = None
        keyboard_idx = None
        for idx in indices:
            channel = mux.get_channel(idx)
            # Quick probe: find REPROG_V4 then BACKLIGHT2
            # We need to send IRoot queries through the multiplexer
            from core.hidpp import LONG_ID, LONG_LEN, MY_SW, parse_report
            import time

            def _probe_feature(feat_id):
                buf = [0] * LONG_LEN
                buf[0] = LONG_ID
                buf[1] = idx
                buf[2] = 0x00  # IRoot
                buf[3] = ((0 & 0x0F) << 4) | (MY_SW & 0x0F)
                buf[4] = (feat_id >> 8) & 0xFF
                buf[5] = feat_id & 0xFF
                try:
                    mux._write(buf)
                except Exception:
                    return None
                deadline = time.time() + 1.0
                while time.time() < deadline:
                    data = channel.read(64, 300)
                    if not data:
                        continue
                    parsed = parse_report(data)
                    if parsed and parsed[0] == idx:
                        _, r_feat, _, r_sw, r_params = parsed
                        if r_feat == 0xFF:
                            return None  # error
                        if r_sw == MY_SW and r_params and r_params[0] != 0:
                            return r_params[0]
                        return None
                return None

            reprog = _probe_feature(FEAT_REPROG_V4)
            if reprog is None:
                continue
            backlight = _probe_feature(FEAT_BACKLIGHT2)
            if backlight is not None:
                keyboard_idx = idx
                print(f"[Engine] Bolt index {idx} → keyboard (has BACKLIGHT2)")
            else:
                mouse_idx = idx
                print(f"[Engine] Bolt index {idx} → mouse (no BACKLIGHT2)")

        if mouse_idx is None and keyboard_idx is None:
            print("[Engine] No identifiable devices on Bolt receiver")
            mux.stop()
            return

        # Start the multiplexer reader thread
        mux.start()
        self._bolt_mux = mux

        if mouse_idx is not None:
            self._bolt_mouse_channel = mux.get_channel(mouse_idx)
            # Recreate the HidGestureListener on the mouse hook with shared channel
            self.hook._hid_gesture = type(self.hook._hid_gesture)(
                on_down=self.hook._hid_gesture._on_down,
                on_up=self.hook._hid_gesture._on_up,
                on_move=self.hook._hid_gesture._on_move,
                on_connect=self.hook._hid_gesture._on_connect,
                on_disconnect=self.hook._hid_gesture._on_disconnect,
                on_action_ring_down=self.hook._hid_gesture._on_action_ring_down,
                on_action_ring_up=self.hook._hid_gesture._on_action_ring_up,
                shared_dev=self._bolt_mouse_channel,
                shared_dev_idx=mouse_idx,
            ) if self.hook._hid_gesture else None

        if keyboard_idx is not None:
            self._bolt_keyboard_channel = mux.get_channel(keyboard_idx)
            self._keyboard_hid = KeyboardHidListener(
                on_key_diverted=self._on_keyboard_key_event,
                on_connect=self._on_keyboard_connect,
                on_disconnect=self._on_keyboard_disconnect,
                shared_dev=self._bolt_keyboard_channel,
                shared_dev_idx=keyboard_idx,
            )

    def start(self):
        # Try Bolt multiplexer first (shared connection for both devices)
        self._try_bolt_multiplexer()

        self.hook.start()
        self._keyboard_hid.start()
        self._app_detector.start()
        # Read current DPI from device on startup (don't overwrite it)
        def _read_dpi():
            import time
            time.sleep(3)  # give HID++ time to connect
            hg = self.hook._hid_gesture
            if hg:
                current = hg.read_dpi()
                if current is not None:
                    self.cfg.setdefault("devices", {}).setdefault("mouse", {}).setdefault("settings", {})["dpi"] = current
                    save_config(self.cfg)
                    if self._dpi_read_cb:
                        try:
                            self._dpi_read_cb(current)
                        except Exception:
                            pass
        threading.Thread(target=_read_dpi, daemon=True).start()

    def set_dpi_read_callback(self, cb):
        """Register a callback ``cb(dpi_value)`` invoked when DPI is read from device."""
        self._dpi_read_cb = cb

    def stop(self):
        self._battery_poll_stop.set()
        self._keyboard_battery_poll_stop.set()
        self._app_detector.stop()
        self.hook.stop()
        self._keyboard_hid.stop()
        if self._bolt_mux:
            self._bolt_mux.stop()
            self._bolt_mux = None

    # ------------------------------------------------------------------
    # Keyboard public API
    # ------------------------------------------------------------------
    def set_keyboard_connection_callback(self, cb):
        """Register ``cb(connected: bool)`` invoked on keyboard connect/disconnect."""
        self._keyboard_connection_cb = cb

    def set_keyboard_battery_callback(self, cb):
        """Register ``cb(level: int)`` invoked when keyboard battery level is read."""
        self._keyboard_battery_cb = cb

    @property
    def keyboard_connected(self):
        return self._keyboard_hid.connected

    @property
    def connected_keyboard(self):
        return self._keyboard_hid.connected_keyboard

    def reload_keyboard_mappings(self):
        """Reload config and re-wire keyboard hooks only."""
        with self._lock:
            self.cfg = load_config()
            self._current_kb_profile = (
                self.cfg.get("devices", {}).get("keyboard", {}).get("active_profile", "default")
            )
            self._setup_keyboard_hooks()
