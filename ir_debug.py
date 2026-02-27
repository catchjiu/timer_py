#!/usr/bin/env python3
"""
IR Receiver Debug Script - Run on Raspberry Pi to troubleshoot IR remote.
Usage: python3 ir_debug.py          # List devices
       python3 ir_debug.py --test  # Live test: press keys (Ctrl+C to exit)
"""

import sys

def main():
    if "--test" in sys.argv:
        return _run_test()

    print("=== IR Receiver Debug ===\n")

    # 1. List all input devices
    print("1. Input devices:")
    try:
        import evdev
        for path in evdev.list_devices():
            dev = evdev.InputDevice(path)
            caps = dev.capabilities()
            has_key = evdev.ecodes.EV_KEY in caps
            print(f"   {path}: {dev.name!r} (has EV_KEY: {has_key})")
    except Exception as e:
        print(f"   Error: {e}")
        return 1

    # 2. Check which device we'd pick
    print("\n2. IRReceiver device selection:")
    try:
        from IRReceiver import _try_evdev
        dev, ok = _try_evdev()
        if ok:
            print(f"   Found: {dev.path} - {dev.name}")
        else:
            print("   No matching device found (looking for gpio/ir/infrared/rc in name)")
    except Exception as e:
        print(f"   Error: {e}")

    # 3. Test
    print("\n3. Live test (press remote buttons):")
    print("   python3 ir_debug.py --test")

    # 4. Permissions
    print("\n4. Ensure your user can read input devices:")
    print("   sudo usermod -aG input $USER")
    print("   (then log out and back in)")

    return 0


def _run_test():
    """Live test: read IR events and show scancode -> action mapping."""
    try:
        from IRReceiver import _try_evdev, _load_scancode_map, IR_DIGIT, IR_SELECT, IR_BACK, IR_UP, IR_DOWN
        import evdev
    except Exception as e:
        print(f"Error: {e}")
        return 1

    dev, ok = _try_evdev()
    if not ok:
        print("No IR device found.")
        return 1

    print(f"Testing {dev.path} - {dev.name}")
    print("Press remote buttons (Ctrl+C to exit)")
    print("To customize: copy ir_scancodes.example.json to ir_scancodes.json and edit.\n")

    action_names = {IR_DIGIT: "digit", IR_SELECT: "SELECT", IR_BACK: "BACK", IR_UP: "UP", IR_DOWN: "DOWN"}

    try:
        for event in dev.read_loop():
            if event.type == evdev.ecodes.EV_KEY and event.value == 1:
                try:
                    code_str = evdev.ecodes.KEY[event.code]
                    print(f"  EV_KEY: {code_str}")
                except (KeyError, TypeError):
                    pass
            elif event.type == evdev.ecodes.EV_MSC and event.code == evdev.ecodes.MSC_SCAN:
                scancode = event.value
                mapped = _load_scancode_map().get(scancode)
                if mapped:
                    action, payload = mapped
                    name = action_names.get(action, action)
                    if payload is not None:
                        print(f"  scancode 0x{scancode:02x} -> {name}({payload})")
                    else:
                        print(f"  scancode 0x{scancode:02x} -> {name}")
                else:
                    print(f"  scancode 0x{scancode:02x} -> (not mapped)")
    except KeyboardInterrupt:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
