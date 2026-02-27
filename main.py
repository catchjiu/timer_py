"""
BJJ Gym Timer - Main Entry & Hardware Bridge
Senior Embedded Software Architecture

Hardware: gpiozero (Pi 5 compatible; uses LGPIOFactory)
- Rotary Encoder: CLK→phys 11 (BCM 17), DT→phys 12 (BCM 18), SW→phys 13 (BCM 27)
- Passive Buzzer: BCM 23 (physical 16); 2=5V, 14=GND
"""

import sys
import os
import platform
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QUrl, QObject, Signal, Slot, Property, QTimer, Qt, QMetaObject
from PySide6.QtGui import QGuiApplication

from TimerLogic import TimerLogic

# GPIO Pin Definitions (BCM numbering)
# Physical pins 11, 12, 13 = BCM 17, 18, 27
PIN_CLK = 17   # Physical pin 11
PIN_DT = 18    # Physical pin 12
PIN_SW = 27    # Physical pin 13
PIN_BUZZER = 23  # Physical pin 16 (PWM); 2=5V, 14=GND

# Set True if rotary doesn't respond (swap CLK/DT)
SWAP_ENCODER_PINS = False

# Long press threshold (ms)
LONG_PRESS_MS = 800


class HardwareBridge(QObject):
    """
    Bridges gpiozero hardware events to QML/TimerLogic.
    Uses gpiozero (Pi 5 compatible) instead of pigpio.
    """

    encoderDelta = Signal(int)
    buzzerBeep = Signal(int, int)  # frequency_hz, duration_ms

    shortPress = Signal()
    longPress = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._encoder = None
        self._button = None
        self._buzzer = None
        self._long_press_timer = None
        self._buzzer_stop_timer = None
        self._use_mock = platform.system() != "Linux" or not self._init_gpiozero()

    def _init_gpiozero(self) -> bool:
        """Initialize gpiozero (Pi 5 compatible). Returns True if successful."""
        try:
            # Pi 5 kernel 6.6.45+ fix: gpiochip changed from 4 to 0
            import gpiozero.pins.lgpio
            import lgpio

            def _patched_lgpio_init(self, chip=None):
                gpiozero.pins.lgpio.LGPIOFactory.__bases__[0].__init__(self)
                for c in [0, 4]:  # Try 0 first (newer Pi 5), then 4
                    try:
                        self._handle = lgpio.gpiochip_open(c)
                        self._chip = c
                        self.pin_class = gpiozero.pins.lgpio.LGPIOPin
                        return
                    except Exception:
                        continue
                raise RuntimeError("Cannot open gpiochip 0 or 4 - check GPIO permissions (usermod -aG gpio $USER)")

            gpiozero.pins.lgpio.LGPIOFactory.__init__ = _patched_lgpio_init

            from gpiozero import RotaryEncoder, Button, TonalBuzzer

            a_pin, b_pin = (PIN_DT, PIN_CLK) if SWAP_ENCODER_PINS else (PIN_CLK, PIN_DT)
            self._encoder = RotaryEncoder(a=a_pin, b=b_pin, wrap=True, max_steps=100)
            self._encoder.when_rotated_clockwise = lambda: self._on_encoder(1)
            self._encoder.when_rotated_counter_clockwise = lambda: self._on_encoder(-1)

            self._button = Button(PIN_SW)
            self._button.when_pressed = self._on_button_pressed
            self._button.when_released = self._on_button_released

            self._buzzer = TonalBuzzer(PIN_BUZZER)

            self._sw_press_time = None
            self._long_press_fired = False
            self._long_press_timer = None
            return True
        except Exception as e:
            print(f"[BJJ Timer] GPIO init failed: {e}", file=sys.stderr)
            print("[BJJ Timer] Running in MOCK mode - use keyboard: ↑↓ scroll, SPACE select, ESC back", file=sys.stderr)
            return False

    def _on_encoder(self, delta: int):
        """Encoder callback - runs in gpiozero thread, emit to main thread."""
        if os.environ.get("BJJ_DEBUG"):
            print(f"[BJJ Timer] Encoder: {delta:+d}", file=sys.stderr)
        self.encoderDelta.emit(delta)

    def _on_button_pressed(self):
        """Called from gpiozero thread - queue to main thread."""
        QMetaObject.invokeMethod(
            self, "_start_long_press_timer",
            Qt.ConnectionType.QueuedConnection
        )

    @Slot()
    def _start_long_press_timer(self):
        """Runs on main thread - create QTimer here."""
        self._sw_press_time = time.monotonic()
        self._long_press_fired = False
        if self._long_press_timer is not None:
            self._long_press_timer.stop()
        self._long_press_timer = QTimer(self)
        self._long_press_timer.setSingleShot(True)
        self._long_press_timer.timeout.connect(self._on_long_press)
        self._long_press_timer.start(LONG_PRESS_MS)

    def _on_long_press(self):
        self._long_press_fired = True
        self._long_press_timer = None
        self.longPress.emit()

    def _on_button_released(self):
        """Called from gpiozero thread - queue to main thread."""
        QMetaObject.invokeMethod(
            self, "_handle_button_released",
            Qt.ConnectionType.QueuedConnection
        )

    @Slot()
    def _handle_button_released(self):
        """Runs on main thread."""
        if self._long_press_timer is not None:
            self._long_press_timer.stop()
            self._long_press_timer = None
        if not self._long_press_fired and self._sw_press_time is not None:
            self.shortPress.emit()
        self._sw_press_time = None

    def play_tone(self, frequency_hz: int, duration_ms: int):
        """Play a tone via PWM. Must be called from main thread."""
        if self._buzzer is not None:
            if self._buzzer_stop_timer is not None:
                self._buzzer_stop_timer.stop()
                self._buzzer_stop_timer = None
            try:
                from gpiozero.tones import Tone
                self._buzzer.play(Tone(frequency_hz))
                self._buzzer_stop_timer = QTimer(self)
                self._buzzer_stop_timer.setSingleShot(True)
                self._buzzer_stop_timer.timeout.connect(self._stop_buzzer)
                self._buzzer_stop_timer.start(duration_ms)
            except Exception:
                pass
        self.buzzerBeep.emit(frequency_hz, duration_ms)

    @Slot()
    def _stop_buzzer(self):
        self._buzzer_stop_timer = None
        if self._buzzer is not None:
            try:
                self._buzzer.stop()
            except Exception:
                pass

    @Slot(int)
    def simulate_encoder_delta(self, delta: int):
        """Simulate rotary turn (for mock/dev mode)."""
        self.encoderDelta.emit(delta)

    @Slot()
    def simulate_short_press(self):
        """Simulate short press (for mock/dev mode)."""
        self.shortPress.emit()

    @Slot()
    def simulate_long_press(self):
        """Simulate long press (for mock/dev mode)."""
        self.longPress.emit()

    @Slot(result=bool)
    def is_mock(self) -> bool:
        return self._use_mock

    @Slot(result=bool)
    def is_hardware(self) -> bool:
        return not self._use_mock

    def cleanup(self):
        """Release GPIO resources."""
        if self._buzzer_stop_timer is not None:
            self._buzzer_stop_timer.stop()
            self._buzzer_stop_timer = None
        self._stop_buzzer()
        for dev in (self._encoder, self._button, self._buzzer):
            if dev is not None:
                try:
                    dev.close()
                except Exception:
                    pass
        self._encoder = self._button = self._buzzer = None


class SensorProvider(QObject):
    """
    Provides Temperature, Humidity, and System Time.
    Uses system calls on Linux, dummy data otherwise.
    """

    tempChanged = Signal(float)
    humidityChanged = Signal(float)
    timeStringChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._temp = 22.0
        self._humidity = 45.0
        self._time_string = "00:00"
        self._use_dummy = True
        self._init_sensors()

    def _init_sensors(self):
        """Try to initialize real sensors (e.g. DHT22 via sysfs or i2c)."""
        # Placeholder: check for /sys/class/thermal or similar
        if platform.system() == "Linux" and os.path.exists("/sys/class/thermal/thermal_zone0/temp"):
            self._use_dummy = False

    def get_temp(self) -> float:
        if self._use_dummy:
            return 22.5
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return float(f.read().strip()) / 1000.0
        except Exception:
            return 22.0

    def get_humidity(self) -> float:
        if self._use_dummy:
            return 48.0
        # DHT22 would require a library; use dummy for now
        return 48.0

    def get_time_string(self) -> str:
        from datetime import datetime
        return datetime.now().strftime("%H:%M")

    # Q_PROPERTY for QML binding
    def _get_temp(self): return self._temp
    temp = Property(float, _get_temp, notify=tempChanged)

    def _get_humidity(self): return self._humidity
    humidity = Property(float, _get_humidity, notify=humidityChanged)

    def _get_time_string(self): return self._time_string
    timeString = Property(str, _get_time_string, notify=timeStringChanged)

    def refresh(self):
        self._temp = self.get_temp()
        self._humidity = self.get_humidity()
        self._time_string = self.get_time_string()
        self.tempChanged.emit(self._temp)
        self.humidityChanged.emit(self._humidity)
        self.timeStringChanged.emit(self._time_string)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("BJJ Gym Timer")
    app.setOrganizationName("BJJ Timer")

    # Timer logic (state machine)
    timer_logic = TimerLogic()

    # Hardware bridge
    hw_bridge = HardwareBridge()

    # Sensor provider
    sensor_provider = SensorProvider()

    # Connect hardware to logic (QueuedConnection for cross-thread encoder callbacks)
    hw_bridge.encoderDelta.connect(timer_logic.encoder_delta, Qt.ConnectionType.QueuedConnection)
    hw_bridge.shortPress.connect(timer_logic.short_press)
    hw_bridge.longPress.connect(timer_logic.long_press)

    # Buzzer: single buzz on round start, two longer buzzes on round end
    def on_round_started():
        hw_bridge.play_tone(880, 100)

    def on_round_ended():
        hw_bridge.play_tone(880, 400)
        QTimer.singleShot(500, lambda: hw_bridge.play_tone(880, 400))

    timer_logic.roundStarted.connect(on_round_started)
    timer_logic.roundEnded.connect(on_round_ended)

    # QML engine
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("timerLogic", timer_logic)
    engine.rootContext().setContextProperty("hardwareBridge", hw_bridge)
    engine.rootContext().setContextProperty("sensorProvider", sensor_provider)

    qml_file = Path(__file__).parent / "main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_file)))

    if not engine.rootObjects():
        return -1

    # Refresh sensors periodically
    from PySide6.QtCore import QTimer
    sensor_timer = QTimer()
    sensor_timer.timeout.connect(sensor_provider.refresh)
    sensor_timer.start(10000)  # Every 10 seconds
    sensor_provider.refresh()

    ret = app.exec()
    hw_bridge.cleanup()
    return ret


if __name__ == "__main__":
    sys.exit(main())
