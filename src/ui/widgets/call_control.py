from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...models.school import CallState
from ..theme import (
    SCG_BLUE,
    SCG_DARK_BLUE,
    SCG_GREEN,
    SCG_RED,
    TEXT_ON_BLUE,
    TEXT_ON_DARK_BLUE,
    TEXT_ON_GREEN,
    TEXT_ON_RED,
)


class CallControlWidget(QWidget):
    """Panel pro řízení hovoru, 30s odpočet a tlačítka Volat / Spojeno / Zavěsit."""

    call_requested = Signal()
    connected_requested = Signal()
    hangup_requested = Signal()
    timeout_reached = Signal()

    def __init__(self, timeout_seconds: int = 30, parent: QWidget | None = None):
        super().__init__(parent)
        self.timeout_seconds = timeout_seconds
        self.remaining_seconds = timeout_seconds
        self.state = CallState.IDLE

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_timer_tick)

        self._setup_ui()
        self._update_state_ui()

    def _setup_ui(self) -> None:
        group = QGroupBox("Řízení hovoru")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(group)

        layout = QVBoxLayout(group)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # Stavový pruh
        status_box = QHBoxLayout()
        lbl_prefix = QLabel("Stav:")
        lbl_prefix.setStyleSheet(f"font-size: 14px; color: {SCG_DARK_BLUE}; font-weight: bold;")
        self.lbl_status = QLabel("Připraveno")
        self.lbl_status.setStyleSheet("font-size: 15px; font-weight: 800; color: #0d5f43;")
        status_box.addWidget(lbl_prefix)
        status_box.addWidget(self.lbl_status)
        status_box.addStretch()

        # Digitální časovač
        self.lbl_timer = QLabel(f"{self.timeout_seconds} s")
        self.lbl_timer.setStyleSheet(
            f"font-size: 26px; font-weight: 900; color: {SCG_DARK_BLUE}; "
            f"background-color: #edf5fd; padding: 4px 18px; border-radius: 8px; border: 2px solid {SCG_BLUE};"
        )
        self.lbl_timer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_box.addWidget(self.lbl_timer)

        layout.addLayout(status_box)

        # Progress bar odpočtu
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, self.timeout_seconds)
        self.progress_bar.setValue(self.timeout_seconds)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #e2e8f0;
                border-radius: 6px;
            }}
            QProgressBar::chunk {{
                background-color: {SCG_BLUE};
                border-radius: 6px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        # Tlačítka akcí (s použitím SCG barev a vysokého kontrastu)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        # 1. Volat (Zelená SCG #5dd0a6)
        self.btn_call = QPushButton("📞  VOLAT")
        self.btn_call.setFixedHeight(52)
        self.btn_call.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_call.setStyleSheet(f"""
            QPushButton {{
                background-color: {SCG_GREEN};
                color: {TEXT_ON_GREEN};
                font-size: 16px;
                font-weight: 900;
                border-radius: 8px;
                border: none;
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{
                background-color: #4bc498;
            }}
            QPushButton:disabled {{
                background-color: #e2e8f0;
                color: #94a3b8;
            }}
        """)
        self.btn_call.clicked.connect(self._on_call_clicked)
        btn_layout.addWidget(self.btn_call, stretch=2)

        # 2. Spojeno (Modrá SCG #5d9be6)
        self.btn_connected = QPushButton("✅  SPOJENO")
        self.btn_connected.setFixedHeight(52)
        self.btn_connected.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_connected.setStyleSheet(f"""
            QPushButton {{
                background-color: {SCG_BLUE};
                color: {TEXT_ON_BLUE};
                font-size: 16px;
                font-weight: 900;
                border-radius: 8px;
                border: none;
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{
                background-color: #4a8cd9;
            }}
            QPushButton:disabled {{
                background-color: #e2e8f0;
                color: #94a3b8;
            }}
        """)
        self.btn_connected.clicked.connect(self._on_connected_clicked)
        btn_layout.addWidget(self.btn_connected, stretch=2)

        # 3. Zavěsit (Červená SCG #ff7f7f)
        self.btn_hangup = QPushButton("🛑  ZAVĚSIT")
        self.btn_hangup.setFixedHeight(52)
        self.btn_hangup.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_hangup.setStyleSheet(f"""
            QPushButton {{
                background-color: {SCG_RED};
                color: {TEXT_ON_RED};
                font-size: 16px;
                font-weight: 900;
                border-radius: 8px;
                border: none;
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{
                background-color: #f76868;
            }}
            QPushButton:disabled {{
                background-color: #e2e8f0;
                color: #94a3b8;
            }}
        """)
        self.btn_hangup.clicked.connect(self._on_hangup_clicked)
        btn_layout.addWidget(self.btn_hangup, stretch=2)

        layout.addLayout(btn_layout)

    def _on_call_clicked(self) -> None:
        # Přepneme do stavu DIALING ale BEZ spuštění timeru.
        # Timer se spustí až po potvrzení, že hovor byl skutečně zahájen (start_dialing).
        self.state = CallState.DIALING
        self._update_state_ui()
        self.lbl_status.setText("Vytáčím...")
        self.lbl_status.setStyleSheet("font-size: 15px; font-weight: 800; color: #b45309;")
        # Zakážeme VOLAT hned, aby se nedalo kliknout dvakrát
        self.btn_call.setEnabled(False)
        self.btn_connected.setEnabled(False)
        self.btn_hangup.setEnabled(False)
        self.call_requested.emit()

    def start_dialing(self) -> None:
        """Zavolá se z MainWindow PO úspěšném zahájení hovoru – spustí 30s odpočet."""
        self.state = CallState.DIALING
        self.remaining_seconds = self.timeout_seconds
        self._update_timer_display()
        self._timer.start()
        self._update_state_ui()

    def dial_failed(self, error_msg: str) -> None:
        """Zavolá se z MainWindow pokud hovor SELHAL – vrátí se do IDLE a zobrazí chybu."""
        self._timer.stop()
        self.state = CallState.IDLE
        self.lbl_status.setText(f"❌ {error_msg}")
        self.lbl_status.setStyleSheet("font-size: 14px; font-weight: 800; color: #dc2626;")
        self.btn_call.setEnabled(True)
        self.btn_connected.setEnabled(False)
        self.btn_hangup.setEnabled(False)

    def _on_connected_clicked(self) -> None:
        self.set_state(CallState.CONNECTED)
        self.connected_requested.emit()

    def _on_hangup_clicked(self) -> None:
        self.set_state(CallState.COMPLETED)
        self.hangup_requested.emit()

    def _on_timer_tick(self) -> None:
        if self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            self._update_timer_display()

        if self.remaining_seconds == 0:
            self._timer.stop()
            self.lbl_status.setText("Čas vypršel (30s timeout)")
            self.lbl_status.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {TEXT_ON_RED};")
            self.set_state(CallState.COMPLETED)
            self.timeout_reached.emit()

    def _update_timer_display(self) -> None:
        self.lbl_timer.setText(f"{self.remaining_seconds} s")
        self.progress_bar.setValue(self.remaining_seconds)

        if self.remaining_seconds <= 5:
            color = SCG_RED
            text_color = TEXT_ON_RED
            bg = "#fff1f1"
        elif self.remaining_seconds <= 12:
            color = "#f59e0b"
            text_color = "#92400e"
            bg = "#fffbeb"
        else:
            color = SCG_BLUE
            text_color = SCG_DARK_BLUE
            bg = "#edf5fd"

        self.lbl_timer.setStyleSheet(
            f"font-size: 26px; font-weight: 900; color: {text_color}; "
            f"background-color: {bg}; padding: 4px 18px; border-radius: 8px; border: 2px solid {color};"
        )
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #e2e8f0;
                border-radius: 6px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 6px;
            }}
        """)

    def set_state(self, state: CallState) -> None:
        self.state = state
        if state == CallState.DIALING:
            self.remaining_seconds = self.timeout_seconds
            self._update_timer_display()
            self._timer.start()
        elif state in (CallState.CONNECTED, CallState.COMPLETED, CallState.IDLE):
            self._timer.stop()

        self._update_state_ui()

    def _update_state_ui(self) -> None:
        if self.state == CallState.IDLE:
            self.lbl_status.setText("Připraveno k hovoru")
            self.lbl_status.setStyleSheet("font-size: 15px; font-weight: 800; color: #0d5f43;")
            self.btn_call.setEnabled(True)
            self.btn_connected.setEnabled(False)
            self.btn_hangup.setEnabled(False)
            self.remaining_seconds = self.timeout_seconds
            self._update_timer_display()

        elif self.state == CallState.DIALING:
            self.lbl_status.setText("Vyzvánění (čeká se na zvednutí)...")
            self.lbl_status.setStyleSheet(f"font-size: 15px; font-weight: 800; color: #b45309;")
            self.btn_call.setEnabled(False)
            self.btn_connected.setEnabled(True)
            self.btn_hangup.setEnabled(True)

        elif self.state == CallState.CONNECTED:
            self.lbl_status.setText("Hovor probíhá (spojeno)")
            self.lbl_status.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {SCG_DARK_BLUE};")
            self.btn_call.setEnabled(False)
            self.btn_connected.setEnabled(False)
            self.btn_hangup.setEnabled(True)

        elif self.state == CallState.COMPLETED:
            if self.remaining_seconds > 0:
                self.lbl_status.setText("Hovor ukončen")
                self.lbl_status.setStyleSheet("font-size: 15px; font-weight: 800; color: #475569;")
            self.btn_call.setEnabled(True)
            self.btn_connected.setEnabled(False)
            self.btn_hangup.setEnabled(False)

    def reset(self) -> None:
        """Resetuje panel do výchozího stavu."""
        self._timer.stop()
        self.set_state(CallState.IDLE)

