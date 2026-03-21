# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Mouser is an open-source Logitech Options+ alternative for remapping Logitech HID++ mice (MX Master family primarily). Python 3.10+ with PySide6 (Qt Quick/QML) UI. Supports Windows 10/11 and macOS 12+.

**Logitech Options+ must NOT be running** — it conflicts with HID++ access and will cause Mouser to malfunction. macOS requires Accessibility permission in System Settings.

## Commands

```bash
# Run from source
python main_qml.py
python main_qml.py --hid-backend=iokit  # macOS: force IOKit transport
python main_qml.py --hid-backend=hidapi # macOS: force hidapi transport

# Tests
python -m unittest discover -s tests -p "test_*.py"

# Run a single test file
python -m unittest tests.test_config

# Compile check (what CI runs)
python -m py_compile main_qml.py core/*.py ui/*.py

# QML lint (requires PySide6 installed)
python -c "
from pathlib import Path; import subprocess, PySide6
qmllint = Path(PySide6.__file__).resolve().parent / 'qmllint'
subprocess.run([str(qmllint)] + sorted(str(p) for p in Path('ui/qml').glob('*.qml')), check=True)
"

# Build portable Windows exe (requires pyinstaller)
build.bat              # incremental
build.bat --clean      # full rebuild
```

## Architecture

```
main_qml.py → Entry point: QML engine, system tray, single-instance guard
core/       → Backend (all platform-specific code lives here)
ui/         → QML frontend + Python↔QML bridge
tests/      → unittest-based tests
images/     → Mouse diagram, app icons, SVG icons
```

### Data Flow

```
Logitech mouse ──HID++──▶ mouse_hook ──event──▶ engine ──action──▶ key_simulator
                              ▲                     │
                         block/pass          reads config.json
                                                    ▲
QML UI ◀──properties/signals──▶ ui/backend ─────────┘
                                    ▲
                               app_detector (polls foreground window every 300ms)
```

### Threading Model

This is a multi-threaded application. Understanding thread ownership is critical:

| Thread | Owner | Notes |
|---|---|---|
| Qt main thread | `main_qml.py`, QML engine, `Backend` | All Qt property/signal work must happen here |
| Hook thread | `mouse_hook.py` | Windows: `SetWindowsHookExW` message loop. macOS: `CGEventTap` run loop |
| HID++ reader | `hid_gesture.py` | Blocking HID read loop; detects disconnects and enters reconnect polling |
| App detector | `app_detector.py` | `QTimer`-based polling every 300ms on the main thread |

**Cross-thread communication**: Hook/HID++ threads cannot touch Qt objects directly. `Backend` defines internal signals (`_profileSwitchRequest`, `_connectionChangeRequest`, `_dpiReadRequest`, etc.) connected with `Qt.QueuedConnection`. Engine callbacks fire these from background threads; the connected slots execute on the Qt main thread.

### Core Modules

- **engine.py** — Orchestrator. Wires hook→simulator→config. On app change, performs lightweight profile switch (re-wires callbacks without tearing down hook thread or HID++ connection). Forwards device identity to backend.
- **mouse_hook.py** — Low-level mouse interception. Windows: `SetWindowsHookExW` (WH_MOUSE_LL) on dedicated thread + Raw Input. macOS: `CGEventTap` via Quartz. Intercepts back/forward/middle/scroll/gestures/action-ring and decides block vs pass-through. `MouseEvent` defines all event type constants including `ACTION_RING_DOWN`/`ACTION_RING_UP`. Handles `WM_DEVICECHANGE` for auto-reconnection.
- **hid_gesture.py** — HID++ 2.0 gesture detection. Opens Logitech HID device, discovers `REPROG_CONTROLS_V4` (feature `0x1B04`), ranks gesture CID candidates from device registry, diverts the best candidate. Also diverts the Actions Ring (`ACTION_RING_CID = 0x01A0`) when present, firing `on_action_ring_down`/`on_action_ring_up` callbacks. Detects disconnection and enters reconnect loop (2–5s retry). macOS defaults to `iokit` transport.
- **key_simulator.py** — 22 built-in actions. Windows: `SendInput` API. macOS: `CGEvent` + `NSEvent` (media keys). Actions registered in the `ACTIONS` dict with `id`, `label`, and `category`.
- **config.py** — JSON config (schema v4). Manages profiles, button mappings (including `action_ring`), app associations, DPI, scroll/gesture settings. Auto-migrates schema versions (check `_migrate()` when changing config shape). Config path: `%APPDATA%\Mouser\` (Windows) or `~/Library/Application Support/Mouser/` (macOS).
- **app_detector.py** — Foreground window polling. Windows: `GetForegroundWindow` → process name (handles UWP `ApplicationFrameHost.exe` → child). macOS: `NSWorkspace.frontmostApplication`.
- **logi_devices.py** — Device catalog. `LogiDeviceSpec` (frozen dataclass) maps product IDs/aliases to display name, DPI range, gesture CIDs, layout key, and `supported_buttons`. Includes MX Master 4 (PID `0xB042`) with `action_ring` in its button layout. `build_connected_device_info()` resolves a live device against the registry; unknown devices get a generic fallback. `clamp_dpi()` enforces per-device DPI bounds.
- **device_layouts.py** — Layout registry mapping layout keys to image assets, hotspot coordinates, and layout metadata for QML rendering. `MX_MASTER_4_LAYOUT` extends `MX_MASTER_LAYOUT` with an `action_ring` hotspot (6 hotspots total). `get_device_layout(key)` returns a deep copy; unknown keys fall back to `generic_mouse`. `get_manual_layout_choices()` returns only `manual_selectable` layouts.
- **app_catalog.py** — Registry of known apps (name, exe, icon path) for per-app profile creation UI.

### UI Layer

- **ui/backend.py** — QObject bridge. Exposes `Property`/`Signal`/`Slot` for QML two-way binding. Properties follow the pattern: private `_field`, getter method, setter with `notify=signal`. Cross-thread safe via internal `Qt.QueuedConnection` signals.
- **ui/qml/Main.qml** — App shell with sidebar navigation (Mouse & Profiles, Point & Scroll). Uses Material theme.
- **ui/qml/MousePage.qml** — Device diagram with clickable `HotspotDot` overlays + profile manager with `ActionChip` selectors. Largest QML file (~2200 lines).
- **ui/qml/ScrollPage.qml** — DPI slider (200–8000 with quick presets) + scroll inversion toggles.
- **ui/qml/Theme.js** — `palette(isDark)` function returning dark/light color objects. All QML components use this for theming.

### QML Conventions

- Material theme is set via env vars (`QT_QUICK_CONTROLS_STYLE=Material`, `QT_QUICK_CONTROLS_MATERIAL_ACCENT=#00d4aa`) **before any Qt imports** in `main_qml.py`.
- Colors come from `Theme.js` `palette()`, not hardcoded. Accent: `#00d4aa` (dark) / `#0ea5a4` (light).
- `HotspotDot.qml`, `ActionChip.qml`, and `AppIcon.qml` are reusable components used by `MousePage.qml`.

### Platform Differences

| Concern | Windows | macOS |
|---|---|---|
| Mouse hook | `SetWindowsHookExW` + Raw Input | `CGEventTap` (Quartz) |
| Key simulation | `SendInput` API | `CGEvent` + `NSEvent` (media keys) |
| App detection | `GetForegroundWindow` | `NSWorkspace.frontmostApplication` |
| Config path | `%APPDATA%\Mouser\` | `~/Library/Application Support/Mouser/` |
| Modifier key | Ctrl | Cmd |
| HID transport | `hidapi` (auto) | `iokit` (default), `hidapi`/`auto` as fallback |
| Permissions | None required | Accessibility permission in System Settings |

## Dependencies

Defined in `requirements.txt`:
- `hidapi` — HID++ communication with Logitech mice
- `PySide6` — Qt Quick/QML UI framework
- `Pillow` — Image processing for icon generation
- `pyobjc-framework-Quartz` / `pyobjc-framework-Cocoa` — macOS only

## CI

GitHub Actions (`.github/workflows/ci.yml`): Python 3.12 on ubuntu-latest. Runs `py_compile`, `unittest discover`, and `qmllint` on every push/PR.

## Packaging

PyInstaller via `Mouser.spec`. Aggressive Qt module trimming (excludes WebEngine, 3D, Charts, Multimedia) with post-build cleanup. Must include `QtSvg` plugin for icon rendering. Output: `dist/Mouser/Mouser.exe`. UPX is disabled (decompression at startup is too slow).

## Testing Notes

Tests use `unittest` with `unittest.mock.patch` to stub platform-specific APIs (ctypes, HID, Qt). Tests run headless on CI (ubuntu-latest) even though the app targets Windows/macOS — platform-specific code paths are mocked. Test files mirror module names: `test_config.py`, `test_hid_gesture.py`, `test_logi_devices.py`, `test_device_layouts.py`, `test_backend.py`.
