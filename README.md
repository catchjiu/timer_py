# BJJ Gym Timer

A professional, high-end lifestyle BJJ (Brazilian Jiu-Jitsu) gym timer built with Python 3 and PySide6 (Qt for Python) and a QML frontend.

## Features

- **DRILLING Mode**: Work period with "Switch!" alerts every 30 seconds (no full rest)
- **SPARRING Mode**: Adjustable work + rest + rounds
- **Rotary Encoder Navigation**: Scroll menu, add/subtract 30s when running
- **Chic UI**: Deep matte black (#121212), gold (#D4AF37), circular progress arc

## Hardware Configuration (Raspberry Pi)

| Component      | GPIO Pins (BCM) | Notes                    |
|----------------|-----------------|--------------------------|
| Rotary Encoder | CLK(11), DT(12), SW(13) | VCC→3.3V, GND→GND |
| Passive Buzzer | 16 (PWM)        | Pins 2, 14 also PWM-capable |

Uses **gpiozero** (Pi 5 compatible via LGPIOFactory). No daemon required.

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
