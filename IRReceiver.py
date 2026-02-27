"""
BJJ Gym Timer - IR Receiver (KY-022)
Reads from evdev (gpio-ir overlay) or lircd socket.
Pin: GPIO 4 (physical 7) - Data; VCC→3.3V (pin 17); GND→pin 9
"""

import platform
import threading
import time

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
            return
        self._last_key_time = now
        try:
            self._callback(action, payload)
        except Exception:
            pass

    def _run_evdev(self, dev):
        import evdev
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
                        self._emit(action, payload)
        except (OSError, IOError):
            pass
        finally:
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
