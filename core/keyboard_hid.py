"""
keyboard_hid.py — Logitech HID++ keyboard listener for key diversion and features.

Connects to MX Mechanical keyboards via HID++ 2.0, discovers
REPROG_CONTROLS_V4, diverts remappable keys, reads backlight/Fn-inversion
state, and fires callbacks on diverted key events.

Architecture mirrors hid_gesture.py: background thread with
connect -> discover -> divert -> listen loop, plus a pending-command queue
for thread-safe operations from the UI thread.

Requires:  pip install hidapi
Falls back gracefully if the package or device are unavailable.
"""

import sys
import threading
import time

from core.logi_keyboards import (
    NON_DIVERTABLE_CIDS,
    build_connected_keyboard_info,
    resolve_keyboard,
)

from core.hidpp import (
    HIDAPI_OK, LONG_ID, LONG_LEN, BT_DEV_IDX,
    FEAT_REPROG_V4, FEAT_UNIFIED_BATT, FEAT_BATTERY_STATUS,
    FEAT_BACKLIGHT2, FEAT_FN_INVERSION, FEAT_DEVICE_NAME,
    BOLT_RECEIVER_PID,
    MY_SW,
    KEY_FLAG_BITS, MAPPING_FLAG_BITS, HIDPP_ERROR_NAMES, KNOWN_CID_NAMES,
    parse_report as _parse,
    hex_bytes as _hex_bytes,
    format_flags as _format_flags,
    format_cid as _format_cid,
    vendor_hid_infos,
)
import core.hidpp as _hidpp

_MAC_NATIVE_OK = _hidpp.MAC_NATIVE_OK
if _MAC_NATIVE_OK:
    _MacNativeHidDevice = _hidpp.MacNativeHidDevice

try:
    import hid as _hid
except ImportError:
    _hid = None

# ── Keyboard-specific constants ──────────────────────────────────

# BLE PIDs for direct Bluetooth connection
KEYBOARD_BLE_PIDS: frozenset = frozenset({0xB366, 0xB367})

# PIDs we should try (BLE direct + Bolt receiver which multiplexes devices)
KEYBOARD_CANDIDATE_PIDS: frozenset = frozenset({0xB366, 0xB367, BOLT_RECEIVER_PID})


# ── Listener class ───────────────────────────────────────────────

class KeyboardHidListener:
    """Background thread: diverts remappable keys and listens via HID++."""

    def __init__(self, on_key_diverted=None, on_connect=None, on_disconnect=None):
        self._on_key_diverted = on_key_diverted
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._dev = None
        self._thread = None
        self._running = False
        self._feat_idx = None           # REPROG_CONTROLS_V4 feature index
        self._backlight_idx = None      # BACKLIGHT2 feature index
        self._fn_inv_idx = None         # FN_INVERSION feature index
        self._battery_idx = None        # battery feature index
        self._battery_feature_id = None
        self._dev_idx = BT_DEV_IDX
        self._connected = False
        self._connected_keyboard = None
        self._diverted_cids: set = set()
        self._held_cids: set = set()

        # Pending command queue (thread-safe)
        self._pending_backlight_read = None
        self._backlight_read_result = None
        self._pending_backlight_write = None
        self._backlight_write_result = None
        self._pending_fn_read = None
        self._fn_read_result = None
        self._pending_fn_write = None
        self._fn_write_result = None
        self._pending_battery = None
        self._battery_result = None

    # ── public API ────────────────────────────────────────────────

    def start(self) -> bool:
        if not HIDAPI_OK and not _MAC_NATIVE_OK:
            print("[KeyboardHid] no HID backend available; install hidapi")
            return False
        if not HIDAPI_OK and _MAC_NATIVE_OK:
            print("[KeyboardHid] hidapi unavailable; using native macOS HID backend only")
        self._running = True
        self._thread = threading.Thread(
            target=self._main_loop, daemon=True, name="KeyboardHid")
        self._thread.start()
        return True

    def stop(self) -> None:
        self._running = False
        d = self._dev
        if d:
            try:
                d.close()
            except Exception:
                pass
            self._dev = None
        self._connected_keyboard = None
        if self._thread:
            self._thread.join(timeout=3)

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def connected_keyboard(self):
        return self._connected_keyboard

    # ── thread-safe public commands ───────────────────────────────

    def read_backlight(self):
        """Queue a backlight read. Returns dict or None. Thread-safe."""
        self._backlight_read_result = None
        self._pending_backlight_read = "read"
        for _ in range(30):
            if self._pending_backlight_read is None:
                return self._backlight_read_result
            time.sleep(0.1)
        print("[KeyboardHid] Backlight read timed out")
        return None

    def write_backlight(self, enabled: bool, brightness: int, mode: int,
                        timeout_hands_out: int, timeout_hands_in: int,
                        timeout_powered: int) -> bool:
        """Queue a backlight write. Returns True on success. Thread-safe."""
        self._backlight_write_result = None
        self._pending_backlight_write = {
            "enabled": enabled,
            "brightness": brightness,
            "mode": mode,
            "timeout_hands_out": timeout_hands_out,
            "timeout_hands_in": timeout_hands_in,
            "timeout_powered": timeout_powered,
        }
        for _ in range(30):
            if self._pending_backlight_write is None:
                return self._backlight_write_result is True
            time.sleep(0.1)
        print("[KeyboardHid] Backlight write timed out")
        return False

    def read_fn_inversion(self):
        """Queue an Fn-inversion read. Returns bool or None. Thread-safe."""
        self._fn_read_result = None
        self._pending_fn_read = "read"
        for _ in range(30):
            if self._pending_fn_read is None:
                return self._fn_read_result
            time.sleep(0.1)
        print("[KeyboardHid] Fn-inversion read timed out")
        return None

    def write_fn_inversion(self, inverted: bool) -> bool:
        """Queue an Fn-inversion write. Returns True on success. Thread-safe."""
        self._fn_write_result = None
        self._pending_fn_write = inverted
        for _ in range(30):
            if self._pending_fn_write is None:
                return self._fn_write_result is True
            time.sleep(0.1)
        print("[KeyboardHid] Fn-inversion write timed out")
        return False

    def read_battery(self):
        """Queue a battery read. Returns int (0-100) or None. Thread-safe."""
        self._battery_result = None
        self._pending_battery = "read"
        for _ in range(30):
            if self._pending_battery is None:
                return self._battery_result
            time.sleep(0.1)
        print("[KeyboardHid] Battery read timed out")
        return None

    # ── low-level HID++ I/O ───────────────────────────────────────

    def _tx(self, report_id: int, feat: int, func: int, params: list) -> None:
        """Transmit an HID++ long message."""
        buf = [0] * LONG_LEN
        buf[0] = LONG_ID
        buf[1] = self._dev_idx
        buf[2] = feat
        buf[3] = ((func & 0x0F) << 4) | (MY_SW & 0x0F)
        for i, b in enumerate(params):
            if 4 + i < LONG_LEN:
                buf[4 + i] = b & 0xFF
        self._dev.write(buf)

    def _rx(self, timeout_ms: int = 2000):
        """Read one HID input report (blocking with timeout)."""
        dev = self._dev
        if dev is None:
            return None
        d = dev.read(64, timeout_ms)
        return list(d) if d else None

    def _request(self, feat: int, func: int, params: list,
                 timeout_ms: int = 2000):
        """Send a long HID++ request, wait for matching response."""
        req_params = list(params)
        try:
            self._tx(LONG_ID, feat, func, req_params)
        except Exception as exc:
            print(f"[KeyboardHid] request tx failed feat=0x{feat:02X} "
                  f"func=0x{func:X} params=[{_hex_bytes(req_params)}]: {exc}")
            return None
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            try:
                raw = self._rx(min(500, timeout_ms))
            except Exception as exc:
                print(f"[KeyboardHid] request rx failed feat=0x{feat:02X} "
                      f"func=0x{func:X} params=[{_hex_bytes(req_params)}]: {exc}")
                return None
            if raw is None:
                continue
            msg = _parse(raw)
            if msg is None:
                continue
            _, r_feat, r_func, r_sw, r_params = msg

            # HID++ error
            if r_feat == 0xFF:
                code = r_params[1] if len(r_params) > 1 else 0
                code_name = HIDPP_ERROR_NAMES.get(code, "UNKNOWN")
                print(f"[KeyboardHid] HID++ error 0x{code:02X} ({code_name}) "
                      f"for feat=0x{feat:02X} func=0x{func:X} "
                      f"devIdx=0x{self._dev_idx:02X} "
                      f"req=[{_hex_bytes(req_params)}] "
                      f"resp=[{_hex_bytes(r_params)}]")
                return None

            expected_funcs = {func, (func + 1) & 0x0F}
            if r_feat == feat and r_sw == MY_SW and r_func in expected_funcs:
                return msg
        print(f"[KeyboardHid] request timeout feat=0x{feat:02X} "
              f"func=0x{func:X} devIdx=0x{self._dev_idx:02X} "
              f"params=[{_hex_bytes(req_params)}]")
        return None

    # ── feature helpers ───────────────────────────────────────────

    def _find_feature(self, feature_id: int):
        """Use IRoot (feature 0x0000) to discover a feature index."""
        hi = (feature_id >> 8) & 0xFF
        lo = feature_id & 0xFF
        resp = self._request(0x00, 0, [hi, lo, 0x00])
        if resp:
            _, _, _, _, p = resp
            if p and p[0] != 0:
                return p[0]
        return None

    def _query_device_name(self) -> str | None:
        """Query DEVICE_NAME (0x0005) to identify the device at current index."""
        name_idx = self._find_feature(FEAT_DEVICE_NAME)
        if name_idx is None:
            return None
        # getDeviceNameCount: function 0
        resp = self._request(name_idx, 0, [])
        if not resp:
            return None
        _, _, _, _, p = resp
        name_len = p[0] if p else 0
        if name_len == 0:
            return None
        # getDeviceName: function 1, param=charIndex
        name_bytes = bytearray()
        offset = 0
        while offset < name_len:
            resp = self._request(name_idx, 1, [offset])
            if not resp:
                break
            _, _, _, _, p = resp
            chunk = bytes(p).rstrip(b"\x00")
            if not chunk:
                break
            name_bytes.extend(chunk)
            offset += len(chunk)
        name = name_bytes[:name_len].decode("utf-8", errors="replace").strip()
        return name if name else None

    def _get_cid_reporting(self, cid: int):
        if self._feat_idx is None:
            return None
        hi = (cid >> 8) & 0xFF
        lo = cid & 0xFF
        return self._request(self._feat_idx, 2, [hi, lo])

    def _set_cid_reporting(self, cid: int, flags: int):
        if self._feat_idx is None:
            return None
        hi = (cid >> 8) & 0xFF
        lo = cid & 0xFF
        return self._request(self._feat_idx, 3, [hi, lo, flags, 0x00, 0x00])

    def _discover_and_divert_keys(self) -> bool:
        """Enumerate REPROG_V4 controls; divert all divertable+reprogrammable keys."""
        if self._feat_idx is None:
            return False
        resp = self._request(self._feat_idx, 0, [])
        if not resp:
            print("[KeyboardHid] Failed to read REPROG_V4 control count")
            return False
        _, _, _, _, params = resp
        count = params[0] if params else 0
        print(f"[KeyboardHid] REPROG_V4 exposes {count} controls")

        diverted_any = False
        for index in range(count):
            key_resp = self._request(self._feat_idx, 1, [index])
            if not key_resp:
                print(f"[KeyboardHid] Failed to read control info for index {index}")
                continue
            _, _, _, _, key_params = key_resp
            if len(key_params) < 9:
                print(f"[KeyboardHid] Short control info for index {index}: "
                      f"[{_hex_bytes(key_params)}]")
                continue

            cid = (key_params[0] << 8) | key_params[1]
            task = (key_params[2] << 8) | key_params[3]
            flags = key_params[4] | (key_params[8] << 8)
            pos = key_params[5]
            group = key_params[6]
            gmask = key_params[7]

            divertable = bool(flags & 0x0020)
            reprogrammable = bool(flags & 0x0010)

            print(
                f"[KeyboardHid] Control idx={index} "
                f"cid={_format_cid(cid)} task=0x{task:04X} "
                f"flags=0x{flags:04X}[{_format_flags(flags, KEY_FLAG_BITS)}] "
                f"group={group} gmask=0x{gmask:02X} pos={pos}"
            )

            if cid in NON_DIVERTABLE_CIDS:
                print(f"[KeyboardHid]   Skipping {_format_cid(cid)} (non-divertable)")
                continue
            if not (divertable and reprogrammable):
                print(f"[KeyboardHid]   Skipping {_format_cid(cid)} "
                      f"(not divertable+reprogrammable)")
                continue

            # Divert: set divert + persist-divert bits
            result = self._set_cid_reporting(cid, 0x03)
            if result is not None:
                self._diverted_cids.add(cid)
                diverted_any = True
                print(f"[KeyboardHid]   Diverted {_format_cid(cid)}: OK")
            else:
                print(f"[KeyboardHid]   Divert {_format_cid(cid)}: FAILED")

        print(f"[KeyboardHid] Diverted {len(self._diverted_cids)} keys total")
        return diverted_any

    def _undivert_all(self) -> None:
        """Restore default key behaviour for all diverted keys (best-effort)."""
        if self._feat_idx is None or self._dev is None:
            return
        for cid in list(self._diverted_cids):
            hi = (cid >> 8) & 0xFF
            lo = cid & 0xFF
            try:
                self._tx(LONG_ID, self._feat_idx, 3,
                         [hi, lo, 0x02, 0x00, 0x00])
            except Exception:
                pass
        self._diverted_cids.clear()

    # ── backlight commands (applied on listener thread) ───────────

    def _apply_pending_backlight_read(self) -> None:
        if self._backlight_idx is None or self._dev is None:
            self._backlight_read_result = None
            self._pending_backlight_read = None
            return
        resp = self._request(self._backlight_idx, 0, [])
        if resp:
            _, _, _, _, p = resp
            # BACKLIGHT2 getBacklightConfig response:
            # p[0] = enabled (1/0), p[1] = options, p[2] = mode, p[3] = brightness
            enabled = bool(p[0]) if len(p) > 0 else False
            options = p[1] if len(p) > 1 else 0
            mode = p[2] if len(p) > 2 else 0
            brightness = p[3] if len(p) > 3 else 0
            self._backlight_read_result = {
                "enabled": enabled,
                "options": options,
                "mode": mode,
                "brightness": brightness,
            }
            print(f"[KeyboardHid] Backlight: enabled={enabled} mode={mode} "
                  f"brightness={brightness}")
        else:
            self._backlight_read_result = None
            print("[KeyboardHid] Backlight read FAILED")
        self._pending_backlight_read = None

    def _apply_pending_backlight_write(self) -> None:
        cmd = self._pending_backlight_write
        if cmd is None:
            return
        if self._backlight_idx is None or self._dev is None:
            self._backlight_write_result = False
            self._pending_backlight_write = None
            return
        enabled_byte = 0x01 if cmd["enabled"] else 0x00
        params = [
            enabled_byte,
            cmd["mode"] & 0xFF,
            cmd["brightness"] & 0xFF,
            cmd["timeout_hands_out"] & 0xFF,
            cmd["timeout_hands_in"] & 0xFF,
            cmd["timeout_powered"] & 0xFF,
        ]
        resp = self._request(self._backlight_idx, 1, params)
        if resp:
            print("[KeyboardHid] Backlight write: OK")
            self._backlight_write_result = True
        else:
            print("[KeyboardHid] Backlight write: FAILED")
            self._backlight_write_result = False
        self._pending_backlight_write = None

    # ── Fn-inversion commands (applied on listener thread) ────────

    def _apply_pending_fn_read(self) -> None:
        if self._fn_inv_idx is None or self._dev is None:
            self._fn_read_result = None
            self._pending_fn_read = None
            return
        resp = self._request(self._fn_inv_idx, 0, [])
        if resp:
            _, _, _, _, p = resp
            inverted = bool(p[0]) if p else False
            self._fn_read_result = inverted
            print(f"[KeyboardHid] Fn-inversion: {inverted}")
        else:
            self._fn_read_result = None
            print("[KeyboardHid] Fn-inversion read FAILED")
        self._pending_fn_read = None

    def _apply_pending_fn_write(self) -> None:
        if self._pending_fn_write is None:
            return
        inverted = self._pending_fn_write
        if self._fn_inv_idx is None or self._dev is None:
            self._fn_write_result = False
            self._pending_fn_write = None
            return
        val = 0x01 if inverted else 0x00
        resp = self._request(self._fn_inv_idx, 1, [val])
        if resp:
            print(f"[KeyboardHid] Fn-inversion write ({inverted}): OK")
            self._fn_write_result = True
        else:
            print(f"[KeyboardHid] Fn-inversion write ({inverted}): FAILED")
            self._fn_write_result = False
        self._pending_fn_write = None

    # ── battery command (applied on listener thread) ──────────────

    def _apply_pending_read_battery(self) -> None:
        if self._battery_idx is None or self._dev is None:
            self._battery_result = None
            self._pending_battery = None
            return

        if self._battery_feature_id == FEAT_UNIFIED_BATT:
            resp = self._request(self._battery_idx, 1, [])
        else:
            resp = self._request(self._battery_idx, 0, [])

        if resp:
            _, _, _, _, params = resp
            level = params[0] if params else None
            if level is not None and 0 <= level <= 100:
                print(f"[KeyboardHid] Battery: {level}%")
                self._battery_result = level
            else:
                self._battery_result = None
        else:
            self._battery_result = None
        self._pending_battery = None

    # ── notification handling ─────────────────────────────────────

    def _on_report(self, raw: list) -> None:
        """Inspect an incoming HID++ report for diverted key events."""
        msg = _parse(raw)
        if msg is None:
            return
        _, feat, func, _sw, params = msg

        if feat != self._feat_idx:
            return

        if func != 0:
            return

        # Params: sequential CID pairs terminated by 0x0000
        cids_now: set = set()
        i = 0
        while i + 1 < len(params):
            c = (params[i] << 8) | params[i + 1]
            if c == 0:
                break
            cids_now.add(c)
            i += 2

        # Filter to only CIDs we diverted
        cids_now = cids_now & self._diverted_cids

        # Newly pressed
        newly_pressed = cids_now - self._held_cids
        for cid in newly_pressed:
            print(f"[KeyboardHid] Key DOWN {_format_cid(cid)}")
            if self._on_key_diverted:
                try:
                    self._on_key_diverted(cid, True)
                except Exception as e:
                    print(f"[KeyboardHid] key_diverted callback error: {e}")

        # Newly released
        newly_released = self._held_cids - cids_now
        for cid in newly_released:
            print(f"[KeyboardHid] Key UP {_format_cid(cid)}")
            if self._on_key_diverted:
                try:
                    self._on_key_diverted(cid, False)
                except Exception as e:
                    print(f"[KeyboardHid] key_diverted callback error: {e}")

        self._held_cids = cids_now

    # ── connect / main loop ───────────────────────────────────────

    def _try_connect(self) -> bool:
        """Open the vendor HID collection, discover features, divert keys."""
        infos = vendor_hid_infos()
        if not infos:
            return False

        print(f"[KeyboardHid] Backend preference: {_hidpp.get_backend_preference()}")
        print(f"[KeyboardHid] Candidate HID interfaces: {len(infos)}")
        for info in infos:
            pid = int(info.get("product_id", 0) or 0)
            up = int(info.get("usage_page", 0) or 0)
            usage = int(info.get("usage", 0) or 0)
            transport = info.get("transport")
            source = info.get("source", "unknown")
            product = info.get("product_string") or "?"
            print(f"[KeyboardHid] Candidate PID=0x{pid:04X} UP=0x{up:04X} "
                  f"usage=0x{usage:04X} transport={transport or '-'} "
                  f"source={source} product={product}")

        for info in infos:
            pid = int(info.get("product_id", 0) or 0)
            up = int(info.get("usage_page", 0) or 0)
            usage = int(info.get("usage", 0) or 0)
            product = info.get("product_string")
            source = info.get("source", "unknown")

            # Only attempt connection to known keyboard PIDs or Bolt receiver
            if pid not in KEYBOARD_CANDIDATE_PIDS:
                continue

            self._feat_idx = None
            self._backlight_idx = None
            self._fn_inv_idx = None
            self._battery_idx = None
            self._battery_feature_id = None
            self._diverted_cids = set()
            self._held_cids = set()

            open_attempts = []
            if _hidpp.get_backend_preference() in ("auto", "hidapi") and info.get("path"):
                open_attempts.append(("hidapi", info))
            if (
                sys.platform == "darwin"
                and _MAC_NATIVE_OK
                and _hidpp.get_backend_preference() in ("auto", "iokit")
            ):
                open_attempts.extend([
                    ("iokit-exact", info),
                    ("iokit-ble", {
                        "product_id": pid,
                        "usage_page": 0,
                        "usage": 0,
                        "transport": "Bluetooth Low Energy",
                    }),
                ])

            for transport_name, open_info in open_attempts:
                try:
                    if transport_name.startswith("iokit"):
                        d = _MacNativeHidDevice(
                            pid,
                            usage_page=open_info.get("usage_page", 0),
                            usage=open_info.get("usage", 0),
                            transport=open_info.get("transport"),
                        )
                        d.open()
                    else:
                        if not HIDAPI_OK:
                            continue
                        d = _hid.device()
                        d.open_path(open_info["path"])
                        d.set_nonblocking(False)
                    self._dev = d
                    print(f"[KeyboardHid] Opened PID=0x{pid:04X} "
                          f"via {transport_name}")
                    break
                except Exception as exc:
                    print(f"[KeyboardHid] Can't open PID=0x{pid:04X} "
                          f"UP=0x{int(open_info.get('usage_page', up) or 0):04X} "
                          f"usage=0x{int(open_info.get('usage', usage) or 0):04X} "
                          f"via {transport_name}: {exc}")
                    self._dev = None
            if self._dev is None:
                continue

            # Try Bluetooth direct (0xFF) first, then Bolt receiver slots
            is_bolt = (pid == BOLT_RECEIVER_PID)
            for idx in (0xFF, 1, 2, 3, 4, 5, 6):
                self._dev_idx = idx
                fi = self._find_feature(FEAT_REPROG_V4)
                if fi is None:
                    continue

                self._feat_idx = fi

                # On Bolt receiver, multiple devices share one HID interface.
                # Use BACKLIGHT2 as a keyboard discriminator (mice don't have it).
                # Also query device name for identification.
                bl_fi = self._find_feature(FEAT_BACKLIGHT2)
                dev_name = self._query_device_name()

                if is_bolt and not bl_fi:
                    # This device index is probably a mouse, skip it
                    print(f"[KeyboardHid] devIdx=0x{idx:02X} has REPROG_V4 "
                          f"but no BACKLIGHT2 (name={dev_name!r}) — "
                          f"skipping (likely a mouse)")
                    self._feat_idx = None
                    continue

                print(f"[KeyboardHid] Found REPROG_V4 @0x{fi:02X}  "
                      f"PID=0x{pid:04X} devIdx=0x{idx:02X} "
                      f"name={dev_name!r}")

                if bl_fi:
                    self._backlight_idx = bl_fi
                    print(f"[KeyboardHid] Found BACKLIGHT2 @0x{bl_fi:02X}")

                fn_fi = self._find_feature(FEAT_FN_INVERSION)
                if fn_fi:
                    self._fn_inv_idx = fn_fi
                    print(f"[KeyboardHid] Found FN_INVERSION @0x{fn_fi:02X}")

                batt_fi = self._find_feature(FEAT_UNIFIED_BATT)
                if batt_fi:
                    self._battery_idx = batt_fi
                    self._battery_feature_id = FEAT_UNIFIED_BATT
                    print(f"[KeyboardHid] Found UNIFIED_BATT @0x{batt_fi:02X}")
                else:
                    batt_fi = self._find_feature(FEAT_BATTERY_STATUS)
                    if batt_fi:
                        self._battery_idx = batt_fi
                        self._battery_feature_id = FEAT_BATTERY_STATUS
                        print(f"[KeyboardHid] Found BATTERY_STATUS "
                              f"@0x{batt_fi:02X}")

                # Use queried device name for build_connected_keyboard_info
                resolved_name = dev_name or product
                kb_spec = resolve_keyboard(
                    product_id=pid, product_name=resolved_name)

                if self._discover_and_divert_keys():
                    self._connected_keyboard = build_connected_keyboard_info(
                        product_id=pid,
                        product_name=resolved_name,
                        transport=(
                            open_info.get("transport") or transport_name
                        ),
                        source=source,
                    )
                    return True
                break  # right device but divert failed

            # Couldn't use this interface — close and try next
            try:
                self._dev.close()
            except Exception:
                pass
            self._dev = None

        return False

    def _main_loop(self) -> None:
        """Outer loop: connect -> listen -> reconnect on error/disconnect."""
        while self._running:
            if not self._try_connect():
                print("[KeyboardHid] No compatible keyboard; retrying in 5 s...")
                for _ in range(50):
                    if not self._running:
                        return
                    time.sleep(0.1)
                continue

            self._connected = True
            if self._on_connect:
                try:
                    self._on_connect()
                except Exception:
                    pass
            print("[KeyboardHid] Listening for key events...")
            try:
                while self._running:
                    # Apply any queued commands
                    if self._pending_backlight_read is not None:
                        self._apply_pending_backlight_read()
                    if self._pending_backlight_write is not None:
                        self._apply_pending_backlight_write()
                    if self._pending_fn_read is not None:
                        self._apply_pending_fn_read()
                    if self._pending_fn_write is not None:
                        self._apply_pending_fn_write()
                    if self._pending_battery is not None:
                        self._apply_pending_read_battery()
                    raw = self._rx(1000)
                    if raw:
                        self._on_report(raw)
            except Exception as e:
                print(f"[KeyboardHid] read error: {e}")

            # Cleanup before potential reconnect
            self._undivert_all()
            try:
                if self._dev:
                    self._dev.close()
            except Exception:
                pass
            self._dev = None
            self._feat_idx = None
            self._backlight_idx = None
            self._fn_inv_idx = None
            self._battery_idx = None
            self._battery_feature_id = None
            self._pending_battery = None
            self._held_cids = set()
            self._diverted_cids = set()
            self._connected_keyboard = None
            if self._connected:
                self._connected = False
                if self._on_disconnect:
                    try:
                        self._on_disconnect()
                    except Exception:
                        pass

            if self._running:
                time.sleep(2)
