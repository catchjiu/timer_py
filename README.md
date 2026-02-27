# BJJ Gym Timer

A professional, high-end lifestyle BJJ (Brazilian Jiu-Jitsu) gym timer built with Python 3 and PySide6 (Qt for Python) and a QML frontend.

## Features

- **DRILLING Mode**: Work period with "Switch!" alerts every 30 seconds (no full rest)
- **SPARRING Mode**: Adjustable work + rest + rounds
- **Rotary Encoder Navigation**: Scroll menu, add/subtract 30s when running
- **Chic UI**: Deep matte black (#121212), gold (#D4AF37), circular progress arc

## Hardware Configuration (Raspberry Pi)

| Component      | Physical Pins | BCM (GPIO) | Notes                    |
|----------------|---------------|------------|--------------------------|
| Rotary Encoder | CLK→11, DT→12, SW→13 | 17, 18, 27 | VCC→1 (3.3V), GND→6 |
| Passive Buzzer | 16 (signal)   | 23         | 2=5V, 14=GND, 16=signal   |

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

**Mock Mode**: When not running on Linux or when pigpio is unavailable, the app runs in mock mode. Use keyboard shortcuts:

- **↑ / ↓** or **+ / -**: Simulate rotary encoder (scroll / adjust time)
- **Space**: Short press (Start/Pause/Select)
- **Escape**: Long press (Reset/Back to menu)

## Project Structure

```
timer-py/
├── main.py        # Hardware init, pigpio callbacks, QML engine bridge
├── TimerLogic.py  # BJJ state machine (modes, phases, timer logic)
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
