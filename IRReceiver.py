"""
BJJ Gym Timer - IR Receiver (KY-022)
Reads from evdev (gpio-ir overlay) or lircd socket.
Pin: GPIO 4 (physical 7) - Data; VCC→3.3V (pin 17); GND→pin 9

Custom mapping: create ir_scancodes.json next to main.py, e.g.:
  {"0x44": 3, "0x40": 4, "0x43": 5, "0x58": "up", "0x59": "down", "0x1C": "select"}
  Numbers 0-9, or "select", "back", "up", "down"
"""

import json
import os
import platform
import sys
import threading
import time
from pathlib import Path

# Key actions we emit
IR_DIGIT = "digit"      # payload: 0-9
IR_SELECT = "select"   # OK / Enter
IR_BACK = "back"       # Back / Exit
IR_UP = "up"           # encoder +1
IR_DOWN = "down"       # encoder -1


def _try_evdev():
    """Try to open IR device via evdev (gpio-ir overlay). Returns (device, True) or (None, False)."""
    if platform.system() != "Linux":
        return None, False
    try:
        import evdev
        devices = [evdev.InputDevice(p) for p in evdev.list_devices()]
        for dev in devices:
            name = dev.name.lower()
            path = dev.path.lower()
            # gpio-ir creates "gpio_ir_recv"; also match rc-core devices
            if any(x in name or x in path for x in ("gpio", "ir", "infrared", "rc-rc", "rc_rc", "gpio_ir")):
                # Prefer devices that have EV_KEY (key events)
                if evdev.ecodes.EV_KEY in dev.capabilities():
                    return dev, True
        # Fallback: try any device with gpio/ir in name even without EV_KEY
        for dev in devices:
            name = dev.name.lower()
            path = dev.path.lower()
            if any(x in name or x in path for x in ("gpio", "ir", "infrared", "rc-rc", "gpio_ir")):
                return dev, True
        return None, False
    except Exception:
        return None, False


def _try_lircd():
    """Try to connect to lircd socket. Returns (socket, True) or (None, False)."""
    if platform.system() != "Linux":
        return None, False
    import socket
    for path in ("/var/run/lirc/lircd", "/run/lirc/lircd"):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(0.5)
            s.connect(path)
            s.settimeout(None)
            return s, True
        except (FileNotFoundError, OSError, socket.error):
            continue
    return None, False


# Maps evdev key codes to our actions. (code, action, payload)
_EVDEV_MAP = {
    "KEY_0": (IR_DIGIT, 0), "KEY_1": (IR_DIGIT, 1), "KEY_2": (IR_DIGIT, 2),
    "KEY_3": (IR_DIGIT, 3), "KEY_4": (IR_DIGIT, 4), "KEY_5": (IR_DIGIT, 5),
    "KEY_6": (IR_DIGIT, 6), "KEY_7": (IR_DIGIT, 7), "KEY_8": (IR_DIGIT, 8),
    "KEY_9": (IR_DIGIT, 9),
    "KEY_KP0": (IR_DIGIT, 0), "KEY_KP1": (IR_DIGIT, 1), "KEY_KP2": (IR_DIGIT, 2),
    "KEY_KP3": (IR_DIGIT, 3), "KEY_KP4": (IR_DIGIT, 4), "KEY_KP5": (IR_DIGIT, 5),
    "KEY_KP6": (IR_DIGIT, 6), "KEY_KP7": (IR_DIGIT, 7), "KEY_KP8": (IR_DIGIT, 8),
    "KEY_KP9": (IR_DIGIT, 9),
    "KEY_OK": (IR_SELECT, None), "KEY_ENTER": (IR_SELECT, None),
    "KEY_SELECT": (IR_SELECT, None), "KEY_KPENTER": (IR_SELECT, None),
    "KEY_BACK": (IR_BACK, None), "KEY_BACKSPACE": (IR_BACK, None),
    "KEY_ESC": (IR_BACK, None), "KEY_EXIT": (IR_BACK, None),
    "KEY_UP": (IR_UP, None),
    "KEY_DOWN": (IR_DOWN, None),
    "KEY_LEFT": (IR_DOWN, None), "KEY_RIGHT": (IR_UP, None),
}

# NEC scancode -> (action, payload) - for remotes that only emit EV_MSC (no keymap loaded)
# Multiple common remote layouts; run ir_debug.py --test to see your remote's scancodes
_SCANCODE_MAP = {
    # Numbers - Layout A (44-key: 0x45=0..0x16=9)
    0x45: (IR_DIGIT, 0), 0x46: (IR_DIGIT, 1), 0x47: (IR_DIGIT, 2),
    0x44: (IR_DIGIT, 3), 0x40: (IR_DIGIT, 4), 0x43: (IR_DIGIT, 5),
    0x07: (IR_DIGIT, 6), 0x15: (IR_DIGIT, 7), 0x09: (IR_DIGIT, 8),
    0x16: (IR_DIGIT, 9),
    # Numbers - Layout B (standard NEC)
    0x0C: (IR_DIGIT, 1), 0x18: (IR_DIGIT, 2), 0x5E: (IR_DIGIT, 3),
    0x08: (IR_DIGIT, 4), 0x1C: (IR_DIGIT, 5), 0x5A: (IR_DIGIT, 6),
    0x42: (IR_DIGIT, 7), 0x52: (IR_DIGIT, 8), 0x4A: (IR_DIGIT, 9),
    # OK / Select (0x1C/0x15 can be Enter on some remotes - add after digits so SELECT wins)
    0x0D: (IR_SELECT, None),
    # Back / Exit
    0x0B: (IR_BACK, None), 0x0E: (IR_BACK, None), 0x0F: (IR_BACK, None),
    # Up/Down/Left/Right - use codes that don't conflict with numbers
    0x58: (IR_UP, None), 0x59: (IR_DOWN, None),
    0x5B: (IR_UP, None), 0x5C: (IR_DOWN, None),
    0x5D: (IR_UP, None), 0x60: (IR_DOWN, None),
    # Some 44-key remotes use these for nav (add SELECT/back variants)
    0x1C: (IR_SELECT, None), 0x15: (IR_SELECT, None),
}


def _load_scancode_map():
    """Load default map, then overlay custom ir_scancodes.json if present."""
    result = dict(_SCANCODE_MAP)
    for base in [Path(__file__).parent, Path.cwd()]:
        cfg = base / "ir_scancodes.json"
        if cfg.exists():
            try:
                with open(cfg, "r") as f:
                    custom = json.load(f)
                for k, v in custom.items():
                    if isinstance(k, str) and k.startswith("0x"):
                        sc = int(k, 16)
                    else:
                        sc = int(k)
                    if isinstance(v, int) and 0 <= v <= 9:
                        result[sc] = (IR_DIGIT, v)
                    elif isinstance(v, str):
                        v = v.lower()
                        if v == "select":
                            result[sc] = (IR_SELECT, None)
                        elif v == "back":
                            result[sc] = (IR_BACK, None)
                        elif v in ("up", "right"):
                            result[sc] = (IR_UP, None)
                        elif v in ("down", "left"):
                            result[sc] = (IR_DOWN, None)
            except Exception as e:
                if os.environ.get("BJJ_DEBUG"):
                    print(f"[BJJ Timer] ir_scancodes.json error: {e}", file=sys.stderr)
            break
    return result


# Maps lirc key names (from lircd) to our actions
_LIRC_MAP = {
    "KEY_0": (IR_DIGIT, 0), "KEY_1": (IR_DIGIT, 1), "KEY_2": (IR_DIGIT, 2),
    "KEY_3": (IR_DIGIT, 3), "KEY_4": (IR_DIGIT, 4), "KEY_5": (IR_DIGIT, 5),
    "KEY_6": (IR_DIGIT, 6), "KEY_7": (IR_DIGIT, 7), "KEY_8": (IR_DIGIT, 8),
    "KEY_9": (IR_DIGIT, 9),
    "KEY_OK": (IR_SELECT, None), "KEY_ENTER": (IR_SELECT, None),
    "KEY_SELECT": (IR_SELECT, None), "KEY_KPENTER": (IR_SELECT, None),
    "KEY_BACK": (IR_BACK, None), "KEY_BACKSPACE": (IR_BACK, None),
    "KEY_ESC": (IR_BACK, None), "KEY_EXIT": (IR_BACK, None),
    "KEY_UP": (IR_UP, None), "KEY_DOWN": (IR_DOWN, None),
    "KEY_LEFT": (IR_DOWN, None), "KEY_RIGHT": (IR_UP, None),
}


def _evdev_key_to_action(code_str: str):
    """Convert evdev key code string to (action, payload) or None."""
    return _EVDEV_MAP.get(code_str)


def _lirc_key_to_action(key_name: str):
    """Convert lirc key name to (action, payload) or None."""
    return _LIRC_MAP.get(key_name.upper())


class IRReceiver:
    """
    Background thread that reads IR input and invokes callback(action, payload).
    Uses evdev (gpio-ir) or lircd socket. Cooldown prevents repeat spam.
    """

    def __init__(self, callback, cooldown_ms: int = 150):
        self._callback = callback
        self._cooldown = cooldown_ms / 1000.0
        self._last_key_time = 0.0
        self._thread = None
        self._stop = threading.Event()
        self._source = None  # "evdev" | "lirc" | None

    def start(self) -> bool:
        """Start IR receiver. Returns True if a source was found."""
        if platform.system() != "Linux":
            return False
        dev, ok = _try_evdev()
        if ok:
            self._source = "evdev"
            self._thread = threading.Thread(target=self._run_evdev, args=(dev,), daemon=True)
            self._thread.start()
            return True
        sock, ok = _try_lircd()
        if ok:
            self._source = "lirc"
            self._thread = threading.Thread(target=self._run_lirc, args=(sock,), daemon=True)
            self._thread.start()
            return True
        return False

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        self._thread = None
        self._source = None

    def _emit(self, action: str, payload):
        now = time.monotonic()
        if now - self._last_key_time < self._cooldown:
            return  # Dropped by cooldown
        self._last_key_time = now
        try:
            self._callback(action, payload)
        except Exception:
            pass

    def _run_evdev(self, dev):
        import evdev
        try:
            dev.grab()  # Exclusive access - prevents other apps (e.g. desktop) from consuming IR
            if os.environ.get("BJJ_DEBUG"):
                print("[BJJ Timer] IR device grabbed", file=sys.stderr)
        except (OSError, IOError) as e:
            if os.environ.get("BJJ_DEBUG"):
                print(f"[BJJ Timer] IR device grab failed: {e}", file=sys.stderr)
        try:
            for event in dev.read_loop():
                if self._stop.is_set():
                    break
                if event.type == evdev.ecodes.EV_KEY and event.value == 1:
                    try:
                        code_str = evdev.ecodes.KEY[event.code]
                    except (KeyError, TypeError):
                        continue
                    mapped = _evdev_key_to_action(code_str)
                    if mapped:
                        action, payload = mapped
                        if os.environ.get("BJJ_DEBUG"):
                            print(f"[BJJ Timer] IR EV_KEY {code_str} -> {action}({payload})", file=sys.stderr)
                        self._emit(action, payload)
                elif event.type == evdev.ecodes.EV_MSC and event.code == evdev.ecodes.MSC_SCAN:
                    # No keymap loaded - kernel only sends scancodes; map them ourselves
                    raw = event.value
                    if os.environ.get("BJJ_DEBUG"):
                        print(f"[BJJ Timer] IR raw 0x{raw:x}", file=sys.stderr)
                    scancode_map = _load_scancode_map()
                    mapped = scancode_map.get(raw)
                    if not mapped and raw > 0xFF:
                        mapped = scancode_map.get(raw & 0xFF)  # Try lower 8 bits
                    if os.environ.get("BJJ_DEBUG"):
                        if mapped:
                            action, payload = mapped
                            print(f"[BJJ Timer] IR 0x{raw:x} -> {action}({payload})", file=sys.stderr)
                        else:
                            print(f"[BJJ Timer] IR scancode 0x{raw:x} (dec {raw}) not mapped", file=sys.stderr)
                    if mapped:
                        action, payload = mapped
                        self._emit(action, payload)
        except (OSError, IOError):
            pass
        finally:
            try:
                dev.ungrab()
            except Exception:
                pass
            try:
                dev.close()
            except Exception:
                pass

    def _run_lirc(self, sock):
        try:
            f = sock.makefile(mode="r", encoding="utf-8", errors="replace")
            while not self._stop.is_set():
                try:
                    line = f.readline()
                    if not line:
                        break
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        key_name = parts[1]
                        mapped = _lirc_key_to_action(key_name)
                        if mapped:
                            action, payload = mapped
                            self._emit(action, payload)
                except (OSError, IOError, UnicodeDecodeError):
                    break
        finally:
            try:
                sock.close()
            except Exception:
                pass
