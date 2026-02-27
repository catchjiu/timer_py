#!/usr/bin/env python3
"""
IR Receiver Debug Script - Run on Raspberry Pi to troubleshoot IR remote.
Usage: python3 ir_debug.py
"""

import sys

def main():
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

    # 3. Test with ir-keytable
    print("\n3. Run this to enable IR protocols and test (press remote buttons):")
    print("   sudo ir-keytable -v -t -p all")
    print("\n   If you see scancodes when pressing buttons, hardware works.")
    print("   If no key names appear, you may need a keymap. Try:")
    print("   sudo ir-keytable -c -w /lib/udev/rc_keymaps/rc6_mce   # or another map")

    # 4. Permissions
    print("\n4. Ensure your user can read input devices:")
    print("   sudo usermod -aG input $USER")
    print("   (then log out and back in)")

    return 0

if __name__ == "__main__":
    sys.exit(main())
