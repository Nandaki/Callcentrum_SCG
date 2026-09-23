from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...models.school import CallState
from ..theme import theme_manager


class CallControlWidget(QWidget):
    """
    Panel pro řízení hovoru.
    Digitální odpočet, stavová indikace a přehledná akční tlačítka.
    """

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
        self._apply_theme()
        self._update_state_ui()
        theme_manager.theme_changed.connect(self._apply_theme)

    def _setup_ui(self) -> None:
        self.setObjectName("callControlRoot")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        # 1. Horní řádek: Stavová tečka & Digitální časovač
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        # Stavová sekce s živou tečkou
        status_box = QHBoxLayout()
        status_box.setSpacing(8)

        self.lbl_status_dot = QLabel("●")
        self.lbl_status_dot.setObjectName("statusDot")
        status_box.addWidget(self.lbl_status_dot)

        self.lbl_status_text = QLabel("Připraveno k hovoru")
        self.lbl_status_text.setObjectName("statusText")
        status_box.addWidget(self.lbl_status_text)
        status_box.addStretch()

        top_row.addLayout(status_box)

        # Digitální časovač
        self.lbl_timer = QLabel("00:30")
        self.lbl_timer.setObjectName("timerText")
        self.lbl_timer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(self.lbl_timer)

        layout.addLayout(top_row)

        # 2. Tenký progress bar odpočtu (4px)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("callProgressBar")
        self.progress_bar.setRange(0, self.timeout_seconds)
        self.progress_bar.setValue(self.timeout_seconds)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        layout.addWidget(self.progress_bar)

        # 3. Akční tlačítka (Čisté popisky bez hranatých závorek)
        self.btn_layout = QHBoxLayout()
        self.btn_layout.setSpacing(10)

        # Tlačítko 1: Volat
        self.btn_call = QPushButton("Volat")
        self.btn_call.setObjectName("btnCall")
        self.btn_call.setFixedHeight(46)
        self.btn_call.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_call.setToolTip("Zahájit hovor (klávesa Mezerník)")
        self.btn_call.clicked.connect(self._on_call_clicked)
        self.btn_layout.addWidget(self.btn_call, stretch=2)

        # Tlačítko 2: Spojeno
        self.btn_connected = QPushButton("Spojeno")
        self.btn_connected.setObjectName("btnConnected")
        self.btn_connected.setFixedHeight(46)
        self.btn_connected.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_connected.setToolTip("Označit jako spojeno (klávesa Mezerník)")
        self.btn_connected.clicked.connect(self._on_connected_clicked)
        self.btn_layout.addWidget(self.btn_connected, stretch=2)

        # Tlačítko 3: Zavěsit
        self.btn_hangup = QPushButton("Zavěsit")
        self.btn_hangup.setObjectName("btnHangup")
        self.btn_hangup.setFixedHeight(46)
        self.btn_hangup.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_hangup.setToolTip("Zavěsit / ukončit hovor (klávesa Esc)")
        self.btn_hangup.clicked.connect(self._on_hangup_clicked)
        self.btn_layout.addWidget(self.btn_hangup, stretch=2)

        layout.addLayout(self.btn_layout)

    def _apply_theme(self) -> None:
        t = theme_manager.tokens

        self.setStyleSheet(f"""
            QWidget#callControlRoot {{
                background-color: {t.bg_card};
                border: 1px solid {t.border_card};
                border-radius: 8px;
            }}
            QLabel#statusText {{
                font-size: 14px;
                font-weight: 600;
                color: {t.text_primary};
            }}
            QLabel#timerText {{
                font-size: 20px;
                font-weight: 700;
                color: {t.text_primary};
                background-color: {t.bg_card_secondary};
                border: 1px solid {t.border_subtle};
                border-radius: 6px;
                padding: 4px 14px;
            }}
            QProgressBar#callProgressBar {{
                background-color: {t.bg_card_secondary};
                border-radius: 2px;
                border: none;
            }}
            QProgressBar#callProgressBar::chunk {{
                background-color: {t.accent_blue};
                border-radius: 2px;
            }}
            QPushButton#btnCall {{
                background-color: {t.accent_green};
                color: #064e3b;
                font-size: 15px;
                font-weight: 700;
                border-radius: 6px;
                border: none;
            }}
            QPushButton#btnCall:hover {{
                background-color: {'#75e6bc' if t.is_dark else '#047857'};
            }}
            QPushButton#btnCall:disabled {{
                background-color: {t.bg_card_secondary};
                color: {t.text_muted};
                border: 1px solid {t.border_subtle};
            }}
            QPushButton#btnConnected {{
                background-color: {t.accent_blue};
                color: #ffffff;
                font-size: 15px;
                font-weight: 700;
                border-radius: 6px;
                border: none;
            }}
            QPushButton#btnConnected:hover {{
                background-color: {'#75acf0' if t.is_dark else '#1d4ed8'};
            }}
            QPushButton#btnConnected:disabled {{
                background-color: {t.bg_card_secondary};
                color: {t.text_muted};
                border: 1px solid {t.border_subtle};
            }}
            QPushButton#btnHangup {{
                background-color: {t.bg_card_secondary};
                color: {t.accent_red};
                font-size: 15px;
                font-weight: 700;
                border-radius: 6px;
                border: 1px solid {t.border_subtle};
            }}
            QPushButton#btnHangup:hover {{
                background-color: {t.accent_red};
                color: #ffffff;
                border: none;
            }}
            QPushButton#btnHangup:disabled {{
                background-color: {t.bg_card_secondary};
                color: {t.text_muted};
                border: 1px solid {t.border_subtle};
            }}
        """)

        self._update_timer_display()
        self._update_state_ui()

    def _on_call_clicked(self) -> None:
        self.state = CallState.DIALING
        self._update_state_ui()
        self.lbl_status_text.setText("Vytáčím hovor...")
        self.btn_call.setEnabled(False)
        self.btn_connected.setEnabled(False)
        self.btn_hangup.setEnabled(False)
        self.call_requested.emit()

    def start_dialing(self) -> None:
        """Spustí odpočet po potvrzení zahájení vytáčení."""
        self.state = CallState.DIALING
        self.remaining_seconds = self.timeout_seconds
        self._update_timer_display()
        self._timer.start()
        self._update_state_ui()

    def dial_failed(self, error_msg: str) -> None:
        """Vrátí do IDLE po chybě vytáčení."""
        self._timer.stop()
        self.state = CallState.IDLE
        self.lbl_status_text.setText(f"Chyba: {error_msg}")
        t = theme_manager.tokens
        self.lbl_status_dot.setStyleSheet(f"color: {t.accent_red}; font-size: 14px;")
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
            self.lbl_status_text.setText("Limit vypršel (30 s)")
            self.set_state(CallState.COMPLETED)
            self.timeout_reached.emit()

    def _update_timer_display(self) -> None:
        mins = self.remaining_seconds // 60
        secs = self.remaining_seconds % 60
        self.lbl_timer.setText(f"{mins:02d}:{secs:02d}")
        self.progress_bar.setValue(self.remaining_seconds)

        t = theme_manager.tokens
        if self.remaining_seconds <= 5:
            bar_color = t.accent_red
            timer_text_color = t.accent_red
        elif self.remaining_seconds <= 12:
            bar_color = t.accent_amber
            timer_text_color = t.accent_amber
        else:
            bar_color = t.accent_blue
            timer_text_color = t.text_primary

        self.progress_bar.setStyleSheet(f"""
            QProgressBar#callProgressBar {{
                background-color: {t.bg_card_secondary};
                border-radius: 2px;
                border: none;
            }}
            QProgressBar#callProgressBar::chunk {{
                background-color: {bar_color};
                border-radius: 2px;
            }}
        """)
        self.lbl_timer.setStyleSheet(f"""
            QLabel#timerText {{
                font-size: 20px;
                font-weight: 700;
                color: {timer_text_color};
                background-color: {t.bg_card_secondary};
                border: 1px solid {t.border_subtle};
                border-radius: 6px;
                padding: 4px 14px;
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
        t = theme_manager.tokens

        if self.state == CallState.IDLE:
            self.lbl_status_dot.setStyleSheet(f"color: {t.accent_green}; font-size: 14px;")
            self.lbl_status_text.setText("Připraveno k hovoru")
            self.btn_call.setEnabled(True)
            self.btn_connected.setEnabled(False)
            self.btn_hangup.setEnabled(False)
            self.remaining_seconds = self.timeout_seconds
            self._update_timer_display()

        elif self.state == CallState.DIALING:
            self.lbl_status_dot.setStyleSheet(f"color: {t.accent_amber}; font-size: 14px;")
            self.lbl_status_text.setText("Vyzvánění (čeká na zvednutí)...")
            self.btn_call.setEnabled(False)
            self.btn_connected.setEnabled(True)
            self.btn_hangup.setEnabled(True)

        elif self.state == CallState.CONNECTED:
            self.lbl_status_dot.setStyleSheet(f"color: {t.accent_blue}; font-size: 14px;")
            self.lbl_status_text.setText("Hovor probíhá (spojeno)")
            self.btn_call.setEnabled(False)
            self.btn_connected.setEnabled(False)
            self.btn_hangup.setEnabled(True)

        elif self.state == CallState.COMPLETED:
            self.lbl_status_dot.setStyleSheet(f"color: {t.text_muted}; font-size: 14px;")
            if self.remaining_seconds > 0:
                self.lbl_status_text.setText("Hovor ukončen")
            self.btn_call.setEnabled(True)
            self.btn_connected.setEnabled(False)
            self.btn_hangup.setEnabled(False)

    def reset(self) -> None:
        """Resetuje panel do výchozího stavu."""
        self._timer.stop()
        self.set_state(CallState.IDLE)
