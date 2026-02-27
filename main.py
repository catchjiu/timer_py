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
import json
import re
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

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

            from gpiozero import RotaryEncoder, Button

            a_pin, b_pin = (PIN_DT, PIN_CLK) if SWAP_ENCODER_PINS else (PIN_CLK, PIN_DT)
            self._encoder = RotaryEncoder(a=a_pin, b=b_pin, wrap=True, max_steps=100)
            self._encoder.when_rotated_clockwise = lambda: self._on_encoder(1)
            self._encoder.when_rotated_counter_clockwise = lambda: self._on_encoder(-1)

            self._button = Button(PIN_SW)
            self._button.when_pressed = self._on_button_pressed
            self._button.when_released = self._on_button_released

            # Use lgpio directly for buzzer (TonalBuzzer.stop() unreliable on Pi 5)
            for chip in [0, 4]:
                try:
                    self._lgpio_handle = lgpio.gpiochip_open(chip)
                    lgpio.gpio_claim_output(self._lgpio_handle, PIN_BUZZER, 0)
                    break
                except Exception:
                    self._lgpio_handle = None
            else:
                self._lgpio_handle = None
            self._buzzer = None  # Not using TonalBuzzer

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
        """Play a tone via lgpio PWM. Must be called from main thread."""
        if self._buzzer_stop_timer is not None:
            self._buzzer_stop_timer.stop()
            self._buzzer_stop_timer = None
        self._stop_buzzer()
        if hasattr(self, "_lgpio_handle") and self._lgpio_handle is not None:
            try:
                import lgpio
                lgpio.tx_pwm(self._lgpio_handle, PIN_BUZZER, frequency_hz, 50)  # 50% duty
                self._buzzer_stop_timer = QTimer(self)
                self._buzzer_stop_timer.setSingleShot(True)
                self._buzzer_stop_timer.timeout.connect(self._stop_buzzer)
                self._buzzer_stop_timer.start(duration_ms)
            except Exception:
                pass
        self.buzzerBeep.emit(frequency_hz, duration_ms)

    def play_two_buzzes(self, frequency_hz: int = 880, duration_ms: int = 400, gap_ms: int = 150):
        """Play two buzzes with gap - second starts only after first fully stops."""
        if self._buzzer_stop_timer is not None:
            self._buzzer_stop_timer.stop()
            self._buzzer_stop_timer = None
        self._stop_buzzer()
        if not (hasattr(self, "_lgpio_handle") and self._lgpio_handle is not None):
            return
        try:
            import lgpio
            lgpio.tx_pwm(self._lgpio_handle, PIN_BUZZER, frequency_hz, 50)
            self._buzzer_stop_timer = QTimer(self)
            self._buzzer_stop_timer.setSingleShot(True)
            self._buzzer_stop_timer.timeout.connect(
                lambda: self._on_first_buzz_done(frequency_hz, duration_ms, gap_ms)
            )
            self._buzzer_stop_timer.start(duration_ms)
        except Exception:
            pass

    def _on_first_buzz_done(self, frequency_hz: int, duration_ms: int, gap_ms: int):
        """Called when first buzz ends - stop, wait gap, play second."""
        self._buzzer_stop_timer = None
        self._stop_buzzer()
        QTimer.singleShot(gap_ms, lambda: self._play_second_buzz(frequency_hz, duration_ms))

    def _play_second_buzz(self, frequency_hz: int, duration_ms: int):
        """Play second buzz of the pair."""
        self._stop_buzzer()
        if hasattr(self, "_lgpio_handle") and self._lgpio_handle is not None:
            try:
                import lgpio
                lgpio.tx_pwm(self._lgpio_handle, PIN_BUZZER, frequency_hz, 50)
                self._buzzer_stop_timer = QTimer(self)
                self._buzzer_stop_timer.setSingleShot(True)
                self._buzzer_stop_timer.timeout.connect(self._stop_buzzer)
                self._buzzer_stop_timer.start(duration_ms)
            except Exception:
                pass

    @Slot()
    def _stop_buzzer(self):
        self._buzzer_stop_timer = None
        if hasattr(self, "_lgpio_handle") and self._lgpio_handle is not None:
            try:
                import lgpio
                lgpio.tx_pwm(self._lgpio_handle, PIN_BUZZER, 0, 0)  # Stop PWM
                lgpio.gpio_write(self._lgpio_handle, PIN_BUZZER, 0)  # Force pin low
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
        if hasattr(self, "_lgpio_handle") and self._lgpio_handle is not None:
            try:
                import lgpio
                lgpio.gpiochip_close(self._lgpio_handle)
            except Exception:
                pass
            self._lgpio_handle = None
        for dev in (self._encoder, self._button, self._buzzer):
            if dev is not None:
                try:
                    dev.close()
                except Exception:
                    pass
        self._encoder = self._button = self._buzzer = None


# ESP32 Weather Station (temp + humidity)
# Override with BJJ_ESP32_URL env var
ESP32_WEATHER_URL = os.environ.get("BJJ_ESP32_URL", "http://35.201.220.212:5000/")

# Kaohsiung, Taiwan - fallback for weather description only
KAOHSIUNG_LAT = 22.6273
KAOHSIUNG_LON = 120.3014
OPEN_METEO_URL = (
    f"https://api.open-meteo.com/v1/forecast"
    f"?latitude={KAOHSIUNG_LAT}&longitude={KAOHSIUNG_LON}"
    "&current=weather_code"
)

# WMO weather codes -> short description
WEATHER_DESC = {
    0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Foggy", 51: "Drizzle", 53: "Drizzle", 55: "Drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain",
    67: "Freezing rain", 71: "Snow", 73: "Snow", 75: "Snow",
    77: "Snow grains", 80: "Showers", 81: "Showers", 82: "Heavy showers",
    85: "Snow showers", 86: "Snow showers", 95: "Thunderstorm",
    96: "Thunderstorm", 99: "Thunderstorm",
}


class SensorProvider(QObject):
    """
    Provides Temperature, Humidity, Weather, and System Time.
    Temp/humidity from ESP32 at http://35.201.220.212:5000/
    Weather description from Open-Meteo (fallback).
    """

    tempChanged = Signal(float)
    humidityChanged = Signal(float)
    weatherDescriptionChanged = Signal(str)
    timeStringChanged = Signal(str)
    timeString12hChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._temp = 22.0
        self._humidity = 45.0
        self._weather_description = "—"
        self._time_string = "00:00"
        self._time_string_12h = "12:00 AM"
        self._location = "Kaohsiung"

    def _fetch_esp32(self) -> bool:
        """Fetch temp and humidity from ESP32 weather station. Returns True on success."""
        url_base = ESP32_WEATHER_URL.rstrip("/") or "http://35.201.220.212:5000"
        if not url_base.startswith("http"):
            url_base = "http://" + url_base
        for path in ["/", "/api", "/data", "/sensors"]:
            url = url_base.rstrip("/") + path
            try:
                req = Request(url, headers={"User-Agent": "BJJ-Timer/1.0"})
                with urlopen(req, timeout=8) as resp:
                    raw = resp.read().decode()
            except (URLError, OSError) as e:
                if os.environ.get("BJJ_DEBUG"):
                    print(f"[BJJ Timer] ESP32 fetch {url}: {e}", file=sys.stderr)
                continue
            # Try JSON first
            data = None
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                for m in re.finditer(r'\{[^{}]*(?:"temperature"|"temp"|"humidity"|"hum")[^{}]*\}', raw):
                    try:
                        data = json.loads(m.group(0))
                        break
                    except json.JSONDecodeError:
                        pass
            if data is not None:
                t = data.get("temperature") or data.get("temp") or data.get("Temperature") or data.get("Temp")
                h = data.get("humidity") or data.get("hum") or data.get("Humidity") or data.get("Hum")
                if t is not None:
                    self._temp = float(t)
                if h is not None:
                    self._humidity = float(h)
                if t is not None or h is not None:
                    return True
                continue
            # Scrape HTML: "Temperature" / "27.5°C", "Humidity" / "49.4%"
            t_match = re.search(r'[Tt]emperature[^0-9]*(\d+\.?\d*)', raw)
            h_match = re.search(r'[Hh]umidity[^0-9]*(\d+\.?\d*)', raw)
            if t_match:
                self._temp = float(t_match.group(1))
            if h_match:
                self._humidity = float(h_match.group(1))
            if t_match or h_match:
                return True
        return False

    def _fetch_weather(self) -> bool:
        """Fetch temp/humidity from ESP32, weather description from Open-Meteo."""
        esp_ok = self._fetch_esp32()
        # Weather description from Open-Meteo (optional)
        try:
            req = Request(OPEN_METEO_URL, headers={"User-Agent": "BJJ-Timer/1.0"})
            with urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            code = data.get("current", {}).get("weather_code", 0)
            self._weather_description = WEATHER_DESC.get(code, "—")
        except (URLError, json.JSONDecodeError, OSError):
            if not esp_ok:
                self._weather_description = "Local"
        return esp_ok

    def get_time_string(self) -> str:
        from datetime import datetime
        return datetime.now().strftime("%H:%M")

    def get_time_string_12h(self) -> str:
        from datetime import datetime
        dt = datetime.now()
        h, m = dt.hour, dt.minute
        ampm = "AM" if h < 12 else "PM"
        h12 = (h % 12) or 12
        return f"{h12}:{m:02d} {ampm}"

    # Q_PROPERTY for QML binding
    def _get_temp(self): return self._temp
    temp = Property(float, _get_temp, notify=tempChanged)

    def _get_humidity(self): return self._humidity
    humidity = Property(float, _get_humidity, notify=humidityChanged)

    def _get_weather_description(self): return self._weather_description
    weatherDescription = Property(str, _get_weather_description, notify=weatherDescriptionChanged)

    def _get_time_string(self): return self._time_string
    timeString = Property(str, _get_time_string, notify=timeStringChanged)

    def _get_time_string_12h(self): return self._time_string_12h
    timeString12h = Property(str, _get_time_string_12h, notify=timeString12hChanged)

    def _get_location(self): return self._location
    location = Property(str, _get_location)

    def refresh(self):
        """Full refresh: fetch weather and update time."""
        self._fetch_weather()
        self._time_string = self.get_time_string()
        self._time_string_12h = self.get_time_string_12h()
        self.tempChanged.emit(self._temp)
        self.humidityChanged.emit(self._humidity)
        self.weatherDescriptionChanged.emit(self._weather_description)
        self.timeStringChanged.emit(self._time_string)
        self.timeString12hChanged.emit(self._time_string_12h)

    def _refresh_clock_only(self):
        """Update only the clock (no API call)."""
        self._time_string = self.get_time_string()
        self._time_string_12h = self.get_time_string_12h()
        self.timeStringChanged.emit(self._time_string)
        self.timeString12hChanged.emit(self._time_string_12h)


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
        hw_bridge.play_two_buzzes(880, 400, 150)  # Two buzzes, second starts after first stops

    timer_logic.roundStarted.connect(on_round_started)
    timer_logic.roundEnded.connect(on_round_ended)

    # QML engine
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("timerLogic", timer_logic)
    engine.rootContext().setContextProperty("hardwareBridge", hw_bridge)
    engine.rootContext().setContextProperty("sensorProvider", sensor_provider)

    qml_name = "main_alt.qml" if "--alt" in sys.argv else "main.qml"
    qml_file = Path(__file__).parent / qml_name
    engine.load(QUrl.fromLocalFile(str(qml_file)))

    if not engine.rootObjects():
        return -1

    # Refresh sensors periodically: weather every 60s, clock every 10s
    from PySide6.QtCore import QTimer
    sensor_provider.refresh()  # Initial load
    weather_timer = QTimer()
    weather_timer.timeout.connect(sensor_provider.refresh)
    weather_timer.start(60000)  # Weather: every 60 seconds
    clock_timer = QTimer()
    clock_timer.timeout.connect(sensor_provider._refresh_clock_only)
    clock_timer.start(10000)  # Clock: every 10 seconds

    ret = app.exec()
    hw_bridge.cleanup()
    return ret


if __name__ == "__main__":
    sys.exit(main())
