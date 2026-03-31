"""
bolt_mux.py — Bolt receiver multiplexer for shared HID++ access.

The Logitech Bolt USB receiver (PID 0xC548) hosts multiple devices at
different device indices (1-6). On macOS IOKit, only one process/thread
can hold the HID device handle at a time. This module provides a shared
connection that routes HID++ traffic to per-device-index channels.

Usage:
    mux = BoltMultiplexer()
    if mux.open():
        mux.start()
        mouse_channel = mux.get_channel(1)    # device index 1
        keyboard_channel = mux.get_channel(2)  # device index 2
        # Each channel has write()/read()/close() like a regular HID device
"""

from __future__ import annotations

import queue
import sys
import threading
import time

from core.hidpp import (
    BOLT_RECEIVER_PID,
    HIDAPI_OK,
    LONG_ID,
    LONG_LEN,
    MAC_NATIVE_OK,
    MY_SW,
    parse_report,
    vendor_hid_infos,
)

import core.hidpp as _hidpp

if MAC_NATIVE_OK:
    _MacNativeHidDevice = _hidpp.MacNativeHidDevice


class BoltChannel:
    """A logical HID++ channel for one device index on a shared Bolt receiver.

    Implements the same write/read/close interface as a raw HID device,
    so listeners (HidGestureListener, KeyboardHidListener) can use it
    as a drop-in replacement for self._dev.
    """

    def __init__(self, mux: BoltMultiplexer, dev_idx: int):
        self._mux = mux
        self._dev_idx = dev_idx
        self._queue: queue.Queue = queue.Queue()
        self._closed = False

    def write(self, buf: list[int]) -> int:
        """Write an HID++ report, forcing our device index."""
        if self._closed:
            raise OSError("BoltChannel closed")
        return self._mux._write(buf)

    def read(self, size: int, timeout_ms: int = 0) -> bytes | list | None:
        """Read from this channel's per-device-index queue."""
        if self._closed:
            return None
        try:
            if timeout_ms and timeout_ms > 0:
                return self._queue.get(timeout=timeout_ms / 1000.0)
            else:
                return self._queue.get_nowait()
        except queue.Empty:
            return b""

    def close(self) -> None:
        """Mark this channel as closed. Does NOT close the underlying device."""
        self._closed = True
        # Drain queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def set_nonblocking(self, _enabled) -> None:
        pass  # No-op — reads use queue with timeout

    def _deliver(self, data) -> None:
        """Called by the multiplexer's reader thread to deliver a report."""
        if not self._closed:
            try:
                self._queue.put_nowait(data)
            except queue.Full:
                pass


class BoltMultiplexer:
    """Shared connection to a Logitech Bolt USB receiver.

    Opens the Bolt receiver once, reads HID++ reports in a background
    thread, and routes them to per-device-index BoltChannel queues.
    """

    def __init__(self):
        self._dev = None
        self._channels: dict[int, BoltChannel] = {}
        self._reader_thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.Lock()

    def open(self) -> bool:
        """Open the Bolt receiver HID interface. Returns True on success."""
        infos = vendor_hid_infos()
        bolt_infos = [
            i for i in infos
            if int(i.get("product_id", 0) or 0) == BOLT_RECEIVER_PID
        ]
        if not bolt_infos:
            print("[BoltMux] No Bolt receiver found")
            return False

        backend_pref = _hidpp.get_backend_preference()

        for info in bolt_infos:
            pid = int(info.get("product_id", 0) or 0)
            up = int(info.get("usage_page", 0) or 0)
            usage = int(info.get("usage", 0) or 0)
            transport = info.get("transport")

            open_attempts = []
            if backend_pref in ("auto", "hidapi") and info.get("path"):
                open_attempts.append(("hidapi", info))
            if (
                sys.platform == "darwin"
                and MAC_NATIVE_OK
                and backend_pref in ("auto", "iokit")
            ):
                open_attempts.extend([
                    ("iokit-exact", info),
                ])

            for method, open_info in open_attempts:
                try:
                    if method.startswith("iokit"):
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
                        import hid as _hid
                        d = _hid.device()
                        d.open_path(open_info["path"])
                        d.set_nonblocking(False)
                    self._dev = d
                    print(f"[BoltMux] Opened Bolt receiver via {method} "
                          f"(UP=0x{up:04X} usage=0x{usage:04X})")
                    return True
                except Exception as exc:
                    print(f"[BoltMux] Can't open Bolt via {method}: {exc}")

        print("[BoltMux] Failed to open Bolt receiver")
        return False

    def start(self) -> None:
        """Start the reader thread that routes reports to channels."""
        if self._dev is None:
            return
        self._running = True
        self._reader_thread = threading.Thread(
            target=self._read_loop, daemon=True, name="BoltMuxReader")
        self._reader_thread.start()
        print("[BoltMux] Reader thread started")

    def stop(self) -> None:
        """Stop the reader thread and close the device."""
        self._running = False
        if self._reader_thread:
            self._reader_thread.join(timeout=3)
            self._reader_thread = None
        if self._dev:
            try:
                self._dev.close()
            except Exception:
                pass
            self._dev = None
        # Close all channels
        for ch in self._channels.values():
            ch.close()
        self._channels.clear()

    def get_channel(self, dev_idx: int) -> BoltChannel:
        """Get or create a channel for a specific device index."""
        with self._lock:
            if dev_idx not in self._channels:
                self._channels[dev_idx] = BoltChannel(self, dev_idx)
            return self._channels[dev_idx]

    def _write(self, buf: list[int]) -> int:
        """Write a raw HID++ report to the Bolt receiver."""
        if self._dev is None:
            raise OSError("BoltMultiplexer not open")
        return self._dev.write(buf)

    def _read_loop(self) -> None:
        """Read HID++ reports and route to per-device-index channels."""
        while self._running:
            try:
                dev = self._dev
                if dev is None:
                    break
                data = dev.read(64, 500)
                if not data:
                    continue
                parsed = parse_report(data)
                if parsed is None:
                    # Broadcast to all channels (unknown format)
                    for ch in list(self._channels.values()):
                        ch._deliver(data)
                    continue
                dev_idx = parsed[0]
                ch = self._channels.get(dev_idx)
                if ch:
                    ch._deliver(data)
            except Exception as exc:
                if self._running:
                    print(f"[BoltMux] Read error: {exc}")
                break

        # Signal disconnect to all channels
        print("[BoltMux] Reader thread exiting")

    @property
    def is_open(self) -> bool:
        return self._dev is not None

    def scan_device_indices(self) -> list[int]:
        """Probe device indices 1-6 to see which respond to IRoot queries.
        Returns list of responding indices."""
        if self._dev is None:
            return []

        found = []
        for idx in range(1, 7):
            # Send IRoot query (feature 0x0000, function 0, asking for REPROG_V4)
            buf = [0] * LONG_LEN
            buf[0] = LONG_ID
            buf[1] = idx
            buf[2] = 0x00  # IRoot feature index
            buf[3] = ((0 & 0x0F) << 4) | (MY_SW & 0x0F)
            buf[4] = 0x00  # feature_id high (0x0000 = IRoot self-query)
            buf[5] = 0x01  # feature_id low  (0x0001 = FEATURE_SET)
            buf[6] = 0x00
            try:
                self._dev.write(buf)
            except Exception:
                continue
            # Read with short timeout
            deadline = time.time() + 0.5
            while time.time() < deadline:
                try:
                    data = self._dev.read(64, 200)
                except Exception:
                    break
                if not data:
                    break
                parsed = parse_report(data)
                if parsed:
                    r_dev, r_feat, r_func, r_sw, r_params = parsed
                    if r_dev == idx and r_sw == MY_SW:
                        found.append(idx)
                        print(f"[BoltMux] Device found at index {idx}")
                        break
                    if r_dev == idx and r_feat == 0xFF:
                        # Error response — device exists but feature not found
                        found.append(idx)
                        print(f"[BoltMux] Device found at index {idx} (error response)")
                        break
        return found
