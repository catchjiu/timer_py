# BJJ Gym Timer

A professional, high-end lifestyle BJJ (Brazilian Jiu-Jitsu) gym timer built with Python 3 and PySide6 (Qt for Python) and a QML frontend.

## Features

- **DRILLING Mode**: Work period with "Switch!" alerts every 30 seconds (no full rest)
- **SPARRING Mode**: Adjustable work + rest + rounds
- **Rotary Encoder Navigation**: Scroll menu, add/subtract 30s when running
- **IR Remote (KY-022)**: Numbers for time entry, OK=select, Back=back, Up/Down=scroll
- **Chic UI**: Deep matte black (#121212), gold (#D4AF37), circular progress arc

## Hardware Configuration (Raspberry Pi)

| Component      | Physical Pins | BCM (GPIO) | Notes                    |
|----------------|---------------|------------|--------------------------|
| Rotary Encoder | CLK→11, DT→12, SW→13 | 17, 18, 27 | VCC→1 (3.3V), GND→6 |
| Passive Buzzer | 16 (signal)   | 23         | 2=5V, 14=GND, 16=signal   |
| IR Receiver (KY-022) | Data→7 | 4 | VCC→17 (3.3V), GND→9 |

Uses **gpiozero** (Pi 5 compatible via LGPIOFactory). No daemon required.

**If you see "No module named 'lgpio'"** on Pi 5:
```bash
pip install lgpio
```

**If rotary encoder doesn't work**, ensure your user has GPIO access:
```bash
sudo usermod -aG gpio $USER
# Log out and back in, or reboot
```

**If GPIO shows green but rotary still doesn't respond:**
1. Run with debug to see if encoder events are received: `BJJ_DEBUG=1 python main.py`
2. If you see "Encoder: +1" or "Encoder: -1" when turning, the wiring is fine—the issue is elsewhere.
3. If you see nothing when turning, try swapping CLK and DT wires, or set `SWAP_ENCODER_PINS = True` in `main.py`.
4. Verify wiring: CLK→physical 11 (BCM 17), DT→physical 12 (BCM 18), SW→physical 13 (BCM 27), VCC→pin 1 (3.3V), GND→pin 6.

### IR Receiver (KY-022) Setup

1. **Hardware**: Data→physical 7 (GPIO 4), VCC→physical 17 (3.3V), GND→physical 9.

2. **Enable gpio-ir overlay** – edit `/boot/firmware/config.txt` (or `/boot/config.txt` on older Pi OS):
   ```
   dtoverlay=gpio-ir,gpio_pin=4
   ```
   Reboot.

3. **Install evdev** (for Python):
   ```bash
   sudo apt install python3-evdev
   ```

4. **Enable IR protocol decoding** (required for key events):
   ```bash
   sudo apt install ir-keytable
   sudo ir-keytable -p all
   ```
   This enables protocol decoding. Without it, the kernel receives IR but won't emit key events.

5. **Permissions** – ensure your user can read input devices:
   ```bash
   sudo usermod -aG input $USER
   ```
   Log out and back in (or reboot).

6. **Debug** – if the remote doesn't work, run:
   ```bash
   python3 ir_debug.py
   ```
   Then test with `sudo ir-keytable -v -t -p all` and press remote buttons. You should see scancodes or key names.

**IR key mapping**: The app maps common remote keys:
   - **0–9**: Enter times (e.g. `5` `0` `0` = 5:00) or rounds
   - **OK / Enter**: Select, confirm, start
   - **Back / Exit / Esc**: Go back, reset
   - **Up / Down / Left / Right**: Scroll (same as rotary)

   If numbers or up/down don't work, run `python3 ir_debug.py --test` and press each button to see scancodes. Copy `ir_scancodes.example.json` to `ir_scancodes.json` and map your remote's scancodes (e.g. `"0x58": "up"`, `"0x44": 3`).

## Installation

```bash
# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r requirements.txt
```

## Running

```bash
python main.py
```

**Mock Mode**: When not running on Linux or when GPIO is unavailable, the app runs in mock mode. Use keyboard shortcuts:

- **↑ / ↓** or **+ / -**: Simulate rotary encoder (scroll / adjust time)
- **Space** or **Enter**: Short press (Start/Pause/Select)
- **Escape** or **Backspace**: Long press (Reset/Back to menu)
- **0–9** (number keys): Enter times or rounds in config (e.g. `5` `0` `0` = 5:00)

## Project Structure

```
timer-py/
├── main.py        # Hardware init, gpiozero + IR bridge, QML engine
├── TimerLogic.py  # BJJ state machine (modes, phases, timer logic)
├── IRReceiver.py  # IR receiver (evdev + lircd fallback)
├── main.qml       # Luxury UI layout, progress arc, transitions
├── requirements.txt
└── README.md
```

## Bridging Hardware to QML

The **HardwareBridge** class in `main.py` connects gpiozero callbacks to Qt signals:

1. **Rotary Encoder (CLK/DT)**: `when_rotated_clockwise` / `when_rotated_counter_clockwise` emit `encoderDelta(+1)` or `encoderDelta(-1)`.
2. **Encoder Switch (SW)**: `when_pressed` starts a QTimer; `when_released` emits `shortPress` or `longPress` based on duration.
3. **Signals → TimerLogic**: `encoderDelta` → `timerLogic.encoder_delta()`, `shortPress` → `short_press()`, `longPress` → `long_press()`.

The **TimerLogic** class exposes `Q_PROPERTY` values (`mode`, `state`, `displayTime`, `progress`, etc.) that QML binds to reactively. No polling—hardware events flow: **gpiozero callback → Qt Signal → Python slot → Q_PROPERTY update → QML re-render**.

## License

MIT
