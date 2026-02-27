"""
BJJ Gym Timer - State Machine Logic
Senior Embedded Software Architecture
"""

from enum import Enum
from PySide6.QtCore import QObject, Signal, Property, QTimer, Slot


class TimerMode(Enum):
    """Timer operating modes."""
    MAIN_MENU = "main_menu"
    CONFIG_DRILLING = "config_drilling"
    CONFIG_SPARRING = "config_sparring"
    DRILLING = "drilling"
    SPARRING = "sparring"


class TimerState(Enum):
    """Internal state for the timer."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    WORK = "work"
    REST = "rest"
    SWITCH = "switch"


class TimerLogic(QObject):
    """
    BJJ Timer State Machine.
    Exposes Q_PROPERTY values for QML binding.
    """

    # Signals for QML
    modeChanged = Signal()
    stateChanged = Signal()
    displayTimeChanged = Signal()
    progressChanged = Signal()
    roundChanged = Signal()
    totalRoundsChanged = Signal()
    menuIndexChanged = Signal()
    switchAlertChanged = Signal()
    configStepChanged = Signal()
    roundStarted = Signal()
    roundEnded = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # Mode & State
        self._mode = TimerMode.MAIN_MENU
        self._state = TimerState.IDLE

        # DRILLING: work, switch(=rest), rounds
        # One round = P1 work + switch + P2 work (no rest between rounds)
        self._drill_work_sec = 120  # 2 min default
        self._drill_rest_sec = 10   # 10 sec switch/rest
        self._drill_rounds = 3
        self._drill_half = 1        # 1=P1 work, 2=P2 work

        # SPARRING: work, rest, rounds
        self._spar_work_sec = 300   # 5 min
        self._spar_rest_sec = 60   # 1 min
        self._spar_rounds = 5
        self._current_round = 1

        # Runtime
        self._display_sec = 0
        self._total_sec = 0
        self._progress = 0.0
        self._menu_index = 0
        self._switch_alert = False

        # Menu items for MAIN_MENU
        self._menu_items = ["DRILLING", "SPARRING"]
        self._state_before_pause = TimerState.WORK

        # Config flow: 0=work, 1=rest/switch, 2=rounds, 3=ready
        self._config_step = 0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # --- Q_PROPERTY: mode ---
    def _get_mode(self):
        return self._mode.value

    def _set_mode(self, value):
        if isinstance(value, str):
            try:
                self._mode = TimerMode(value)
            except ValueError:
                return
        else:
            self._mode = value
        self.modeChanged.emit()

    mode = Property(str, _get_mode, _set_mode, notify=modeChanged)

    # --- Q_PROPERTY: state ---
    def _get_state(self):
        return self._state.value

    def _set_state(self, value):
        if isinstance(value, str):
            try:
                self._state = TimerState(value)
            except ValueError:
                return
        else:
            self._state = value
        self.stateChanged.emit()

    state = Property(str, _get_state, _set_state, notify=stateChanged)

    # --- Q_PROPERTY: displayTime (formatted MM:SS) ---
    def _get_display_time(self):
        m = self._display_sec // 60
        s = self._display_sec % 60
        return f"{m:02d}:{s:02d}"

    displayTime = Property(str, lambda self: self._get_display_time(), notify=displayTimeChanged)

    # --- Q_PROPERTY: progress (0.0 - 1.0) ---
    def _get_progress(self):
        return self._progress

    progress = Property(float, _get_progress, notify=progressChanged)

    # --- Q_PROPERTY: currentRound ---
    def _get_current_round(self):
        return self._current_round

    currentRound = Property(int, _get_current_round, notify=roundChanged)

    # --- Q_PROPERTY: totalRounds ---
    def _get_total_rounds(self):
        if self._mode == TimerMode.DRILLING:
            return self._drill_rounds
        return self._spar_rounds

    totalRounds = Property(int, _get_total_rounds, notify=totalRoundsChanged)

    # --- Q_PROPERTY: menuIndex ---
    def _get_menu_index(self):
        return self._menu_index

    def _set_menu_index(self, value):
        self._menu_index = max(0, min(value, len(self._menu_items) - 1))
        self.menuIndexChanged.emit()

    menuIndex = Property(int, _get_menu_index, _set_menu_index, notify=menuIndexChanged)

    # --- Q_PROPERTY: switchAlert ---
    def _get_switch_alert(self):
        return self._switch_alert

    switchAlert = Property(bool, _get_switch_alert, notify=switchAlertChanged)

    # --- Q_PROPERTY: menuItem (current selection) ---
    def _get_menu_item(self):
        if 0 <= self._menu_index < len(self._menu_items):
            return self._menu_items[self._menu_index]
        return ""

    menuItem = Property(str, _get_menu_item, notify=menuIndexChanged)

    # --- Q_PROPERTY: configStep ---
    def _get_config_step(self):
        return self._config_step

    configStep = Property(int, _get_config_step, notify=configStepChanged)

    # --- Q_PROPERTY: config labels/values for UI ---
    def _get_config_work_sec(self):
        return self._drill_work_sec if self._mode == TimerMode.CONFIG_DRILLING else self._spar_work_sec

    def _get_config_rest_switch_sec(self):
        return self._drill_rest_sec if self._mode == TimerMode.CONFIG_DRILLING else self._spar_rest_sec

    def _get_drill_half(self):
        return self._drill_half

    drillHalf = Property(int, _get_drill_half, notify=roundChanged)

    def _get_config_rounds(self):
        return self._drill_rounds if self._mode == TimerMode.CONFIG_DRILLING else self._spar_rounds

    configWorkSec = Property(int, _get_config_work_sec, notify=configStepChanged)
    configRestSwitchSec = Property(int, _get_config_rest_switch_sec, notify=configStepChanged)
    configRounds = Property(int, _get_config_rounds, notify=configStepChanged)

    def _emit_config_changed(self):
        self.configStepChanged.emit()

    # --- Q_PROPERTY: phaseLabel (for UI) ---
    def _get_phase_label(self):
        if self._state == TimerState.WORK:
            if self._mode == TimerMode.DRILLING:
                return "P1" if self._drill_half == 1 else "P2"
            return "WORK"
        if self._state == TimerState.REST:
            return "SWITCH" if self._mode == TimerMode.DRILLING else "REST"
        if self._state == TimerState.SWITCH:
            return "SWITCH!"
        return ""

    phaseLabel = Property(str, _get_phase_label, notify=stateChanged)

    # --- Rotary encoder delta (from hardware) ---
    def encoder_delta(self, delta: int):
        """Called when rotary encoder is turned. delta: +1 CW, -1 CCW."""
        if self._mode == TimerMode.MAIN_MENU:
            self._set_menu_index(self._menu_index + delta)
        elif self._mode in (TimerMode.CONFIG_DRILLING, TimerMode.CONFIG_SPARRING):
            self._config_adjust(delta)
        elif self._state in (TimerState.RUNNING, TimerState.WORK, TimerState.REST, TimerState.SWITCH):
            # Add/subtract 30 seconds from active timer
            adj = 30 * delta
            self._display_sec = max(0, min(self._display_sec + adj, 59 * 60))
            self._total_sec = max(0, min(self._total_sec + adj, 59 * 60))
            self._update_progress()
            self.displayTimeChanged.emit()

    def _config_adjust(self, delta: int):
        """Adjust config value based on current step."""
        if self._config_step == 0:  # Work time
            adj = 30 * delta
            if self._mode == TimerMode.CONFIG_DRILLING:
                self._drill_work_sec = max(30, min(self._drill_work_sec + adj, 60 * 60))
            else:
                self._spar_work_sec = max(30, min(self._spar_work_sec + adj, 60 * 60))
        elif self._config_step == 1:  # Rest time
            adj = 15 * delta
            if self._mode == TimerMode.CONFIG_DRILLING:
                self._drill_rest_sec = max(0, min(self._drill_rest_sec + adj, 600))
            else:
                self._spar_rest_sec = max(0, min(self._spar_rest_sec + adj, 600))
        else:  # Rounds
            adj = delta
            if self._mode == TimerMode.CONFIG_DRILLING:
                self._drill_rounds = max(1, min(self._drill_rounds + adj, 20))
            else:
                self._spar_rounds = max(1, min(self._spar_rounds + adj, 20))
        self._emit_config_changed()

    # --- Short press: Start / Pause ---
    def short_press(self):
        if self._mode == TimerMode.MAIN_MENU:
            # Enter config for selected mode
            if self._menu_index == 0:
                self._set_mode(TimerMode.CONFIG_DRILLING)
                self._config_step = 0
                self.configStepChanged.emit()
            else:
                self._set_mode(TimerMode.CONFIG_SPARRING)
                self._config_step = 0
                self.configStepChanged.emit()
        elif self._mode in (TimerMode.CONFIG_DRILLING, TimerMode.CONFIG_SPARRING):
            if self._config_step < 3:
                self._config_step += 1
                self.configStepChanged.emit()
            else:
                # Start timer
                if self._mode == TimerMode.CONFIG_DRILLING:
                    self._enter_drilling()
                else:
                    self._enter_sparring()
        elif self._state in (TimerState.RUNNING, TimerState.WORK, TimerState.REST, TimerState.SWITCH):
            self._timer.stop()
            self._state_before_pause = self._state
            self._state = TimerState.PAUSED
            self.stateChanged.emit()
        elif self._state == TimerState.PAUSED:
            self._timer.start(1000)
            self._state = self._state_before_pause
            self.stateChanged.emit()

    # --- Long press: Reset / Back to menu ---
    def long_press(self):
        self._timer.stop()
        self._switch_alert = False
        self.switchAlertChanged.emit()
        if self._mode in (TimerMode.CONFIG_DRILLING, TimerMode.CONFIG_SPARRING):
            self._set_mode(TimerMode.MAIN_MENU)
            self._config_step = 0
            self.configStepChanged.emit()
        else:
            self._set_mode(TimerMode.MAIN_MENU)
        self._set_state(TimerState.IDLE)
        self._display_sec = 0
        self._total_sec = 0
        self._progress = 0.0
        self._current_round = 1
        self.displayTimeChanged.emit()
        self.progressChanged.emit()
        self.roundChanged.emit()

    def _enter_drilling(self):
        self._set_mode(TimerMode.DRILLING)
        self._current_round = 1
        self._drill_half = 1  # P1 work
        self._display_sec = self._drill_work_sec
        self._total_sec = self._drill_work_sec
        self._set_state(TimerState.WORK)
        self._update_progress()
        self._timer.start(1000)
        self.roundStarted.emit()
        self.displayTimeChanged.emit()
        self.progressChanged.emit()
        self.roundChanged.emit()

    def _enter_sparring(self):
        self._set_mode(TimerMode.SPARRING)
        self._display_sec = self._spar_work_sec
        self._total_sec = self._spar_work_sec
        self._current_round = 1
        self._set_state(TimerState.WORK)
        self._update_progress()
        self._timer.start(1000)
        self.roundStarted.emit()
        self.displayTimeChanged.emit()
        self.progressChanged.emit()
        self.roundChanged.emit()

    def _update_progress(self):
        if self._total_sec > 0:
            self._progress = 1.0 - (self._display_sec / self._total_sec)
        else:
            self._progress = 0.0
        self.progressChanged.emit()

    def _tick(self):
        self._display_sec -= 1

        if self._mode == TimerMode.DRILLING:
            self._tick_drilling()
        elif self._mode == TimerMode.SPARRING:
            self._tick_sparring()

        self.displayTimeChanged.emit()
        self._update_progress()

    def _tick_drilling(self):
        self._switch_alert = False
        self.switchAlertChanged.emit()

        if self._display_sec <= 0:
            if self._state == TimerState.WORK:
                self.roundEnded.emit()
                if self._drill_half == 1:
                    # P1 work done → switch/rest
                    if self._drill_rest_sec > 0:
                        self._display_sec = self._drill_rest_sec
                        self._total_sec = self._drill_rest_sec
                        self._set_state(TimerState.REST)
                    else:
                        self._drill_half = 2
                        self._display_sec = self._drill_work_sec
                        self._total_sec = self._drill_work_sec
                        self._set_state(TimerState.WORK)
                        self.roundStarted.emit()
                else:
                    # P2 work done → next round or done
                    if self._current_round >= self._drill_rounds:
                        self._timer.stop()
                        self._display_sec = 0
                        self._set_state(TimerState.IDLE)
                    else:
                        self._current_round += 1
                        self.roundChanged.emit()
                        self._drill_half = 1
                        self._display_sec = self._drill_work_sec
                        self._total_sec = self._drill_work_sec
                        self._set_state(TimerState.WORK)
                        QTimer.singleShot(1000, self._emit_round_started)  # Delay so double buzz finishes
            elif self._state == TimerState.REST:
                # Switch/rest done → P2 work
                self._drill_half = 2
                self._display_sec = self._drill_work_sec
                self._total_sec = self._drill_work_sec
                self._set_state(TimerState.WORK)
                self.roundStarted.emit()
            self.displayTimeChanged.emit()

    def _tick_sparring(self):
        if self._display_sec <= 0:
            if self._state == TimerState.WORK:
                self.roundEnded.emit()
                if self._current_round >= self._spar_rounds:
                    self._timer.stop()
                    self._display_sec = 0
                    self._set_state(TimerState.IDLE)
                elif self._spar_rest_sec > 0:
                    self._display_sec = self._spar_rest_sec
                    self._total_sec = self._spar_rest_sec
                    self._set_state(TimerState.REST)
                else:
                    self._current_round += 1
                    self.roundChanged.emit()
                    self._display_sec = self._spar_work_sec
                    self._total_sec = self._spar_work_sec
                    self._set_state(TimerState.WORK)
                    QTimer.singleShot(1000, self._emit_round_started)  # Delay so double buzz finishes
            elif self._state == TimerState.REST:
                self._current_round += 1
                self.roundChanged.emit()
                self._display_sec = self._spar_work_sec
                self._total_sec = self._spar_work_sec
                self._set_state(TimerState.WORK)
                self.roundStarted.emit()
            self.displayTimeChanged.emit()

    def _set_state(self, value):
        self._state = value
        self.stateChanged.emit()

    @Slot()
    def _emit_round_started(self):
        self.roundStarted.emit()
