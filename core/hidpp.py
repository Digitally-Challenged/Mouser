"""
hidpp.py — Shared HID++ 2.0 protocol layer.

Provides constants, report parsing, platform HID transport wrappers,
and device enumeration used by both the mouse gesture listener
(hid_gesture.py) and keyboard listener (keyboard_hid.py).

Extracted from hid_gesture.py to share the protocol layer across
mouse and keyboard modules without duplication.
"""

import sys
import queue
import time

# ── hidapi import ────────────────────────────────────────────────

try:
    import hid as _hid
    HIDAPI_OK = True
    # On macOS, allow non-exclusive HID access so the mouse keeps working
    if sys.platform == "darwin" and hasattr(_hid, "hid_darwin_set_open_exclusive"):
        _hid.hid_darwin_set_open_exclusive(0)
except ImportError:
    HIDAPI_OK = False

# ── macOS native HID (IOKit) setup ───────────────────────────────

_MAC_NATIVE_OK = False
if sys.platform == "darwin":
    try:
        import ctypes
        from ctypes import POINTER, byref, c_char_p, c_int, c_long, c_uint8, c_void_p, create_string_buffer

        _cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        _iokit = ctypes.CDLL("/System/Library/Frameworks/IOKit.framework/IOKit")

        _cf.CFNumberCreate.argtypes = [c_void_p, c_int, c_void_p]
        _cf.CFNumberCreate.restype = c_void_p
        _cf.CFNumberGetValue.argtypes = [c_void_p, c_int, c_void_p]
        _cf.CFNumberGetValue.restype = c_int
        _cf.CFStringCreateWithCString.argtypes = [c_void_p, c_char_p, c_int]
        _cf.CFStringCreateWithCString.restype = c_void_p
        _cf.CFStringGetCString.argtypes = [c_void_p, c_void_p, c_long, c_int]
        _cf.CFStringGetCString.restype = c_int
        _cf.CFDictionaryCreate.argtypes = [
            c_void_p, POINTER(c_void_p), POINTER(c_void_p), c_long, c_void_p, c_void_p,
        ]
        _cf.CFDictionaryCreate.restype = c_void_p
        _cf.CFSetGetCount.argtypes = [c_void_p]
        _cf.CFSetGetCount.restype = c_long
        _cf.CFSetGetValues.argtypes = [c_void_p, POINTER(c_void_p)]
        _cf.CFRelease.argtypes = [c_void_p]
        _cf.CFRetain.argtypes = [c_void_p]
        _cf.CFRetain.restype = c_void_p
        _cf.CFRunLoopGetCurrent.argtypes = []
        _cf.CFRunLoopGetCurrent.restype = c_void_p
        _cf.CFRunLoopRunInMode.argtypes = [c_void_p, ctypes.c_double, ctypes.c_bool]
        _cf.CFRunLoopRunInMode.restype = c_int

        _iokit.IOHIDManagerCreate.argtypes = [c_void_p, c_int]
        _iokit.IOHIDManagerCreate.restype = c_void_p
        _iokit.IOHIDManagerSetDeviceMatching.argtypes = [c_void_p, c_void_p]
        _iokit.IOHIDManagerOpen.argtypes = [c_void_p, c_int]
        _iokit.IOHIDManagerOpen.restype = c_int
        _iokit.IOHIDManagerCopyDevices.argtypes = [c_void_p]
        _iokit.IOHIDManagerCopyDevices.restype = c_void_p

        _iokit.IOHIDDeviceOpen.argtypes = [c_void_p, c_int]
        _iokit.IOHIDDeviceOpen.restype = c_int
        _iokit.IOHIDDeviceClose.argtypes = [c_void_p, c_int]
        _iokit.IOHIDDeviceClose.restype = c_int
        _iokit.IOHIDDeviceGetProperty.argtypes = [c_void_p, c_void_p]
        _iokit.IOHIDDeviceGetProperty.restype = c_void_p
        _iokit.IOHIDDeviceScheduleWithRunLoop.argtypes = [c_void_p, c_void_p, c_void_p]
        _iokit.IOHIDDeviceUnscheduleFromRunLoop.argtypes = [c_void_p, c_void_p, c_void_p]
        _iokit.IOHIDDeviceSetReport.argtypes = [c_void_p, c_int, c_long, POINTER(c_uint8), c_long]
        _iokit.IOHIDDeviceSetReport.restype = c_int
        _IOHID_REPORT_CALLBACK = ctypes.CFUNCTYPE(
            None,
            c_void_p,
            c_int,
            c_void_p,
            c_int,
            ctypes.c_uint32,
            POINTER(c_uint8),
            c_long,
        )
        _iokit.IOHIDDeviceRegisterInputReportCallback.argtypes = [
            c_void_p,
            POINTER(c_uint8),
            c_long,
            _IOHID_REPORT_CALLBACK,
            c_void_p,
        ]
        _iokit.IOHIDDeviceGetReport.argtypes = [c_void_p, c_int, c_long, POINTER(c_uint8), POINTER(c_long)]
        _iokit.IOHIDDeviceGetReport.restype = c_int

        _K_CF_NUMBER_SINT32 = 3
        _K_CF_STRING_ENCODING_UTF8 = 0x08000100
        _K_IOHID_REPORT_TYPE_INPUT = 0
        _K_IOHID_REPORT_TYPE_OUTPUT = 1
        _K_CF_RUN_LOOP_DEFAULT_MODE = c_void_p.in_dll(_cf, "kCFRunLoopDefaultMode")

        _MAC_NATIVE_OK = True
    except Exception as exc:
        print(f"[HidPP] macOS native HID unavailable: {exc}")


# ── Backend preference ───────────────────────────────────────────

def _default_backend_preference(platform_name=None):
    platform_name = sys.platform if platform_name is None else platform_name
    if platform_name == "darwin":
        return "iokit"
    return "auto"


_BACKEND_PREFERENCE = _default_backend_preference()


def set_backend_preference(preference):
    normalized = (preference or "auto").strip().lower()
    if normalized not in {"auto", "hidapi", "iokit"}:
        raise ValueError("hid backend must be one of: auto, hidapi, iokit")
    if normalized == "hidapi" and not HIDAPI_OK:
        raise ValueError("hidapi backend requested but hidapi is not available")
    if normalized == "iokit":
        if sys.platform != "darwin":
            raise ValueError("iokit backend is only available on macOS")
        if not _MAC_NATIVE_OK:
            raise ValueError("iokit backend requested but native macOS HID is unavailable")

    global _BACKEND_PREFERENCE
    _BACKEND_PREFERENCE = normalized
    print(f"[HidPP] Backend preference set to {normalized}")


def get_backend_preference():
    return _BACKEND_PREFERENCE


# ── macOS native HID device wrapper ──────────────────────────────

if _MAC_NATIVE_OK:
    class MacNativeHidDevice:
        """Minimal IOHIDDevice wrapper for Logitech BLE HID++ on macOS."""

        def __init__(self, product_id, usage_page=0, usage=0, transport=None):
            self._product_id = int(product_id)
            self._usage_page = int(usage_page or 0)
            self._usage = int(usage or 0)
            self._transport = transport or None
            self._manager = None
            self._matching = None
            self._device = None
            self._matching_refs = []
            self._run_loop = None
            self._input_buffer = None
            self._report_callback = None
            self._report_queue = queue.Queue()

        @staticmethod
        def _cfstring(text):
            return _cf.CFStringCreateWithCString(
                None, text.encode("utf-8"), _K_CF_STRING_ENCODING_UTF8
            )

        @staticmethod
        def _cfnumber(value):
            num = c_int(int(value))
            return _cf.CFNumberCreate(None, _K_CF_NUMBER_SINT32, byref(num))

        @staticmethod
        def _cfnumber_to_int(ref):
            if not ref:
                return 0
            value = c_int()
            ok = _cf.CFNumberGetValue(ref, _K_CF_NUMBER_SINT32, byref(value))
            return int(value.value) if ok else 0

        @staticmethod
        def _cfstring_to_str(ref):
            if not ref:
                return None
            buf = create_string_buffer(256)
            ok = _cf.CFStringGetCString(ref, buf, len(buf), _K_CF_STRING_ENCODING_UTF8)
            return buf.value.decode("utf-8", errors="replace") if ok else None

        @classmethod
        def _get_property(cls, device_ref, name):
            key = cls._cfstring(name)
            try:
                return _iokit.IOHIDDeviceGetProperty(device_ref, key)
            finally:
                _cf.CFRelease(key)

        @classmethod
        def enumerate_infos(cls):
            infos = []
            manager = None
            matching = None
            matching_refs = []
            try:
                keys = [cls._cfstring("VendorID")]
                values = [cls._cfnumber(LOGI_VID)]
                key_array = (c_void_p * len(keys))(*keys)
                value_array = (c_void_p * len(values))(*values)
                matching = _cf.CFDictionaryCreate(
                    None, key_array, value_array, len(keys), None, None
                )
                matching_refs = keys + values

                manager = _iokit.IOHIDManagerCreate(None, 0)
                if not manager:
                    raise OSError("IOHIDManagerCreate failed")
                _iokit.IOHIDManagerSetDeviceMatching(manager, matching)
                res = _iokit.IOHIDManagerOpen(manager, 0)
                if res != 0:
                    raise OSError(f"IOHIDManagerOpen failed: 0x{res:08X}")

                devices = _iokit.IOHIDManagerCopyDevices(manager)
                if not devices:
                    return infos
                try:
                    count = _cf.CFSetGetCount(devices)
                    if count <= 0:
                        return infos
                    values_buf = (c_void_p * count)()
                    _cf.CFSetGetValues(devices, values_buf)
                    seen = set()
                    for device_ref in values_buf:
                        pid = cls._cfnumber_to_int(cls._get_property(device_ref, "ProductID"))
                        up = cls._cfnumber_to_int(cls._get_property(device_ref, "PrimaryUsagePage"))
                        usage = cls._cfnumber_to_int(cls._get_property(device_ref, "PrimaryUsage"))
                        transport = cls._cfstring_to_str(cls._get_property(device_ref, "Transport"))
                        product = cls._cfstring_to_str(cls._get_property(device_ref, "Product"))
                        if not pid:
                            continue
                        key = (pid, up, usage, transport or "", product or "")
                        if key in seen:
                            continue
                        seen.add(key)
                        infos.append({
                            "product_id": pid,
                            "usage_page": up,
                            "usage": usage,
                            "transport": transport,
                            "product_string": product,
                            "source": "iokit-enumerate",
                        })
                finally:
                    _cf.CFRelease(devices)
            except Exception as exc:
                print(f"[HidPP] native enumerate error: {exc}")
            finally:
                if matching:
                    _cf.CFRelease(matching)
                if manager:
                    _cf.CFRelease(manager)
                for item in matching_refs:
                    _cf.CFRelease(item)
            return infos

        def open(self):
            keys = [
                self._cfstring("VendorID"),
                self._cfstring("ProductID"),
            ]
            values = [
                self._cfnumber(LOGI_VID),
                self._cfnumber(self._product_id),
            ]
            if self._usage_page > 0:
                keys.append(self._cfstring("PrimaryUsagePage"))
                values.append(self._cfnumber(self._usage_page))
            if self._usage > 0:
                keys.append(self._cfstring("PrimaryUsage"))
                values.append(self._cfnumber(self._usage))
            if self._transport:
                keys.append(self._cfstring("Transport"))
                values.append(self._cfstring(self._transport))
            key_array = (c_void_p * len(keys))(*keys)
            value_array = (c_void_p * len(values))(*values)
            self._matching = _cf.CFDictionaryCreate(
                None, key_array, value_array, len(keys), None, None
            )
            self._matching_refs = keys + values

            self._manager = _iokit.IOHIDManagerCreate(None, 0)
            if not self._manager:
                raise OSError("IOHIDManagerCreate failed")
            _iokit.IOHIDManagerSetDeviceMatching(self._manager, self._matching)
            res = _iokit.IOHIDManagerOpen(self._manager, 0)
            if res != 0:
                raise OSError(f"IOHIDManagerOpen failed: 0x{res:08X}")

            devices = _iokit.IOHIDManagerCopyDevices(self._manager)
            if not devices:
                raise OSError(self._describe_match_failure())
            try:
                count = _cf.CFSetGetCount(devices)
                if count <= 0:
                    raise OSError(self._describe_match_failure())
                values_buf = (c_void_p * count)()
                _cf.CFSetGetValues(devices, values_buf)
                self._device = _cf.CFRetain(values_buf[0])
            finally:
                _cf.CFRelease(devices)

            res = _iokit.IOHIDDeviceOpen(self._device, 0)
            if res != 0:
                raise OSError(f"IOHIDDeviceOpen failed: 0x{res:08X}")
            self._run_loop = _cf.CFRunLoopGetCurrent()
            self._input_buffer = (c_uint8 * 64)()
            self._report_callback = _IOHID_REPORT_CALLBACK(self._on_input_report)
            _iokit.IOHIDDeviceScheduleWithRunLoop(
                self._device,
                self._run_loop,
                _K_CF_RUN_LOOP_DEFAULT_MODE,
            )
            _iokit.IOHIDDeviceRegisterInputReportCallback(
                self._device,
                self._input_buffer,
                len(self._input_buffer),
                self._report_callback,
                None,
            )

        def _describe_match_failure(self):
            parts = [f"PID 0x{self._product_id:04X}"]
            if self._usage_page > 0:
                parts.append(f"UP 0x{self._usage_page:04X}")
            if self._usage > 0:
                parts.append(f"usage 0x{self._usage:04X}")
            if self._transport:
                parts.append(f'transport "{self._transport}"')
            return "No IOHIDDevice for " + " ".join(parts)

        def close(self):
            if self._device and self._run_loop:
                try:
                    _iokit.IOHIDDeviceUnscheduleFromRunLoop(
                        self._device,
                        self._run_loop,
                        _K_CF_RUN_LOOP_DEFAULT_MODE,
                    )
                except Exception:
                    pass
            if self._device:
                try:
                    _iokit.IOHIDDeviceClose(self._device, 0)
                except Exception:
                    pass
            if self._device:
                _cf.CFRelease(self._device)
                self._device = None
            if self._matching:
                _cf.CFRelease(self._matching)
                self._matching = None
            if self._manager:
                _cf.CFRelease(self._manager)
                self._manager = None
            for item in self._matching_refs:
                _cf.CFRelease(item)
            self._matching_refs = []
            self._run_loop = None
            self._input_buffer = None
            self._report_callback = None
            self._report_queue = queue.Queue()

        def set_nonblocking(self, _enabled):
            return None

        def write(self, buf):
            arr = (c_uint8 * len(buf))(*buf)
            res = _iokit.IOHIDDeviceSetReport(
                self._device,
                _K_IOHID_REPORT_TYPE_OUTPUT,
                int(buf[0]),
                arr,
                len(buf),
            )
            if res != 0:
                raise OSError(f"IOHIDDeviceSetReport failed: 0x{res:08X}")
            return len(buf)

        def _on_input_report(self, _context, result, _sender, _report_type,
                             _report_id, report, report_length):
            if result != 0 or report_length <= 0:
                return
            try:
                self._report_queue.put_nowait(
                    ctypes.string_at(report, int(report_length))
                )
            except Exception:
                pass

        def read(self, _size, timeout_ms=0):
            try:
                return self._report_queue.get_nowait()
            except queue.Empty:
                pass

            deadline = None
            if timeout_ms and timeout_ms > 0:
                deadline = time.monotonic() + timeout_ms / 1000.0

            while True:
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return b""
                    slice_seconds = min(remaining, 0.05)
                else:
                    slice_seconds = 0.05

                _cf.CFRunLoopRunInMode(
                    _K_CF_RUN_LOOP_DEFAULT_MODE,
                    slice_seconds,
                    True,
                )
                try:
                    return self._report_queue.get_nowait()
                except queue.Empty:
                    if deadline is not None:
                        continue
                    return b""

# ── Constants ─────────────────────────────────────────────────────

LOGI_VID       = 0x046D

SHORT_ID       = 0x10        # HID++ short report (7 bytes total)
LONG_ID        = 0x11        # HID++ long  report (20 bytes total)
SHORT_LEN      = 7
LONG_LEN       = 20

BT_DEV_IDX     = 0xFF        # device-index for direct Bluetooth
FEAT_IROOT     = 0x0000
FEAT_REPROG_V4 = 0x1B04      # Reprogrammable Controls V4
FEAT_ADJ_DPI   = 0x2201      # Adjustable DPI
FEAT_UNIFIED_BATT   = 0x1004      # Unified Battery (preferred)
FEAT_BATTERY_STATUS = 0x1000      # Battery Status (fallback)

# Keyboard feature constants
FEAT_BACKLIGHT2    = 0x1982   # Keyboard backlight control
FEAT_FN_INVERSION  = 0x40A3   # Fn key inversion toggle
FEAT_DISABLE_KEYS  = 0x4521   # Disable specific keys

MY_SW          = 0x0A        # arbitrary software-id used in our requests

HIDPP_ERROR_NAMES = {
    0x01: "UNKNOWN",
    0x02: "INVALID_ARGUMENT",
    0x03: "OUT_OF_RANGE",
    0x04: "HARDWARE_ERROR",
    0x05: "LOGITECH_ERROR",
    0x06: "INVALID_FEATURE_INDEX",
    0x07: "INVALID_FUNCTION",
    0x08: "BUSY",
    0x09: "UNSUPPORTED",
}

KEY_FLAG_BITS = (
    (0x0001, "mse"),
    (0x0002, "fn"),
    (0x0004, "nonstandard"),
    (0x0008, "fn_sensitive"),
    (0x0010, "reprogrammable"),
    (0x0020, "divertable"),
    (0x0040, "persist_divertable"),
    (0x0080, "virtual"),
    (0x0100, "raw_xy"),
    (0x0200, "force_raw_xy"),
    (0x0400, "analytics"),
    (0x0800, "raw_wheel"),
)

MAPPING_FLAG_BITS = (
    (0x0001, "diverted"),
    (0x0004, "persist_diverted"),
    (0x0010, "raw_xy_diverted"),
    (0x0040, "force_raw_xy_diverted"),
    (0x0100, "analytics_reporting"),
    (0x0400, "raw_wheel"),
)

KNOWN_CID_NAMES = {
    # Mouse CIDs
    0x00C3: "Mouse Gesture Button",
    0x00C4: "Smart Shift",
    0x00D7: "Virtual Gesture Button",
    0x01A0: "Actions Ring (Haptic)",
    # Keyboard CIDs
    0x00C7: "Fn Key",
    0x00C8: "Lock Key",
    0x00C9: "Brightness Down",
    0x00CA: "Brightness Up",
    0x00CB: "Host Switch 1",
    0x00CC: "Host Switch 2",
    0x00CD: "Host Switch 3",
    0x00D0: "Mic Mute",
    0x00D1: "Emoji Key",
    0x00D2: "Snipping Tool",
    0x00D3: "Dictation",
    0x00D5: "Do Not Disturb",
    0x00E0: "Smart Actions (F9)",
    0x00E1: "Smart Actions (F10)",
    0x00E2: "Smart Actions (F11)",
    0x00E3: "Smart Actions (F12)",
    0x0108: "Voice Assistant",
    0x0141: "Globe/Language Key",
}


# ── Helpers ───────────────────────────────────────────────────────

def parse_report(raw):
    """Parse a read buffer -> (dev_idx, feat_idx, func, sw, params) or None.

    On Windows the hidapi C backend strips the report-ID byte, so the
    first byte is device-index.  On other platforms / future versions
    the report-ID may be included.  We detect which layout we have by
    checking whether byte 0 looks like a valid HID++ report-ID.
    """
    if not raw or len(raw) < 4:
        return None
    off = 1 if raw[0] in (SHORT_ID, LONG_ID) else 0
    if off + 3 > len(raw):
        return None
    dev    = raw[off]
    feat   = raw[off + 1]
    fsw    = raw[off + 2]
    func   = (fsw >> 4) & 0x0F
    sw     = fsw & 0x0F
    params = raw[off + 3:]
    return dev, feat, func, sw, params


def hex_bytes(data):
    if not data:
        return "-"
    return " ".join(f"{int(b) & 0xFF:02X}" for b in data)


def format_flags(value, bit_names):
    names = [name for bit, name in bit_names if value & bit]
    return ",".join(names) if names else "none"


def format_cid(cid):
    name = KNOWN_CID_NAMES.get(cid)
    return f"0x{cid:04X} ({name})" if name else f"0x{cid:04X}"


# ── Device enumeration ───────────────────────────────────────────

def vendor_hid_infos():
    """Return candidate Logitech HID interfaces from hidapi and macOS IOKit."""
    out = []
    seen = set()

    def add_info(info):
        pid = int(info.get("product_id", 0) or 0)
        up = int(info.get("usage_page", 0) or 0)
        usage = int(info.get("usage", 0) or 0)
        transport = info.get("transport") or ""
        path = info.get("path") or b""
        if isinstance(path, str):
            path = path.encode("utf-8", errors="replace")
        key = (pid, up, usage, transport, bytes(path))
        if key in seen:
            return
        seen.add(key)
        out.append(info)

    if HIDAPI_OK and _BACKEND_PREFERENCE in ("auto", "hidapi"):
        try:
            for info in _hid.enumerate(LOGI_VID, 0):
                if info.get("usage_page", 0) >= 0xFF00:
                    add_info(dict(info, source="hidapi-enumerate"))
        except Exception as exc:
            print(f"[HidPP] hidapi enumerate error: {exc}")

    if (
        sys.platform == "darwin"
        and _MAC_NATIVE_OK
        and _BACKEND_PREFERENCE in ("auto", "iokit")
    ):
        for info in MacNativeHidDevice.enumerate_infos():
            add_info(info)

    return out
