from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QGroupBox,
    QLabel,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...models.school import CallResult, CallResultType
from ..theme import (
    SCG_BLUE,
    SCG_DARK_BLUE,
    SCG_GREEN,
    SCG_RED,
    TEXT_ON_DARK_BLUE,
)


class ResultPanelWidget(QWidget):
    """Panel pro rychlé zaznamenání výsledku hovoru a uložení poznámky."""

    result_submitted = Signal(CallResult)
    send_sms_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        group = QGroupBox("Výsledek hovoru")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(group)

        layout = QVBoxLayout(group)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # Skupina radio buttonů pro výsledek
        self.btn_group = QButtonGroup(self)

        self.radio_interested = QRadioButton("🌟  Dovoláno – Má zájem (zaslat podklady)")
        self.radio_interested.setStyleSheet("font-size: 13px; font-weight: 700; color: #0f4a34;")

        self.radio_not_interested = QRadioButton("❌  Dovoláno – Nemá zájem")
        self.radio_not_interested.setStyleSheet("font-size: 13px; font-weight: 600; color: #991b1b;")

        self.radio_unanswered = QRadioButton("📵  Nezastiženi (vypršel limit / poslána SMS)")
        self.radio_unanswered.setStyleSheet("font-size: 13px; font-weight: 600; color: #92400e;")

        self.radio_call_later = QRadioButton("⏳  Zavolat později / Domluveno na jindy")
        self.radio_call_later.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {SCG_DARK_BLUE};")

        self.radio_wrong_number = QRadioButton("🚫  Špatné číslo / Neexistuje")
        self.radio_wrong_number.setStyleSheet("font-size: 13px; font-weight: 500; color: #475569;")

        radios = [
            (self.radio_interested, CallResultType.INTERESTED),
            (self.radio_not_interested, CallResultType.NOT_INTERESTED),
            (self.radio_unanswered, CallResultType.UNANSWERED),
            (self.radio_call_later, CallResultType.CALL_LATER),
            (self.radio_wrong_number, CallResultType.WRONG_NUMBER),
        ]

        grid_radios = QVBoxLayout()
        grid_radios.setSpacing(7)
        for i, (rb, res_type) in enumerate(radios):
            self.btn_group.addButton(rb, i)
            rb.setProperty("result_type", res_type)
            grid_radios.addWidget(rb)

        layout.addLayout(grid_radios)

        # Skutečné TLAČÍTKO pro odeslání SMS (žádné zaškrtávací políčko!)
        sms_box = QVBoxLayout()
        sms_box.setSpacing(4)

        self.btn_send_sms = QPushButton("💬  Odeslat SMS škole přes ADB")
        self.btn_send_sms.setFixedHeight(44)
        self.btn_send_sms.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send_sms.setStyleSheet(f"""
            QPushButton {{
                background-color: #ffffff;
                color: {SCG_DARK_BLUE};
                font-size: 13px;
                font-weight: 800;
                border: 1.5px solid {SCG_BLUE};
                border-radius: 8px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                background-color: #edf5fd;
                border-color: {SCG_DARK_BLUE};
            }}
            QPushButton:disabled {{
                background-color: #f1f5f9;
                color: #94a3b8;
                border-color: #cbd5e1;
            }}
        """)
        self.btn_send_sms.clicked.connect(self._on_send_sms_clicked)
        sms_box.addWidget(self.btn_send_sms)

        self.lbl_sms_status = QLabel("")
        self.lbl_sms_status.setStyleSheet("font-size: 12px; font-weight: 700; color: #059669; padding-left: 4px;")
        sms_box.addWidget(self.lbl_sms_status)

        layout.addLayout(sms_box)

        # Poznámka operátora
        lbl_note = QLabel("Poznámka k hovoru:")
        lbl_note.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {SCG_DARK_BLUE}; margin-top: 4px;")
        layout.addWidget(lbl_note)

        self.txt_note = QTextEdit()
        self.txt_note.setPlaceholderText("Např. Paní ředitelka je na poradě, volat zítra po 10:00...")
        self.txt_note.setMaximumHeight(70)
        self.txt_note.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px;
                font-size: 13px;
                color: #0f172a;
            }
            QTextEdit:focus {
                border: 1.5px solid #5d9be6;
            }
        """)
        layout.addWidget(self.txt_note)

        # Akční tlačítko pro uložení a přechod na další školu (SCG Tmavě modrá #34337e)
        self.btn_submit = QPushButton("💾  Uložit výsledek a načíst další školu ➡️")
        self.btn_submit.setFixedHeight(48)
        self.btn_submit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_submit.setStyleSheet(f"""
            QPushButton {{
                background-color: {SCG_DARK_BLUE};
                color: {TEXT_ON_DARK_BLUE};
                font-size: 15px;
                font-weight: 800;
                border-radius: 8px;
                border: none;
                letter-spacing: 0.3px;
            }}
            QPushButton:hover {{
                background-color: #2b2a68;
            }}
            QPushButton:pressed {{
                background-color: #1e1d4d;
            }}
        """)
        self.btn_submit.clicked.connect(self._on_submit_clicked)
        layout.addWidget(self.btn_submit)

    def _on_send_sms_clicked(self) -> None:
        self.btn_send_sms.setEnabled(False)
        self.lbl_sms_status.setText("⏳ Odesílám SMS přes ADB...")
        self.lbl_sms_status.setStyleSheet("font-size: 12px; font-weight: 700; color: #b45309; padding-left: 4px;")
        self.send_sms_requested.emit()

    def set_sms_result(self, ok: bool, msg: str) -> None:
        self.btn_send_sms.setEnabled(True)
        if ok:
            self.btn_send_sms.setText("✅  SMS byla odeslána")
            self.lbl_sms_status.setText(f"✅ {msg}")
            self.lbl_sms_status.setStyleSheet("font-size: 12px; font-weight: 700; color: #059669; padding-left: 4px;")
        else:
            self.btn_send_sms.setText("💬  Zkusit odeslat SMS znovu")
            self.lbl_sms_status.setText(f"❌ {msg}")
            self.lbl_sms_status.setStyleSheet("font-size: 12px; font-weight: 700; color: #dc2626; padding-left: 4px;")

    def select_timeout_default(self) -> None:
        """Vybere výchozí stav pro timeout (Nezastiženi)."""
        self.radio_unanswered.setChecked(True)
        self.lbl_sms_status.setText("⏳ Odesílám automatickou SMS...")
        self.lbl_sms_status.setStyleSheet("font-size: 12px; font-weight: 700; color: #b45309; padding-left: 4px;")

    def _on_submit_clicked(self) -> None:
        selected_btn = self.btn_group.checkedButton()
        if not selected_btn:
            result_type = CallResultType.CUSTOM
        else:
            result_type = selected_btn.property("result_type")

        result = CallResult(
            result_type=result_type,
            note=self.txt_note.toPlainText().strip(),
            send_email=False,
        )
        self.result_submitted.emit(result)

    def reset(self) -> None:
        """Vyčistí panel pro další hovor."""
        checked = self.btn_group.checkedButton()
        if checked:
            self.btn_group.setExclusive(False)
            checked.setChecked(False)
            self.btn_group.setExclusive(True)

        self.txt_note.clear()
        self.lbl_sms_status.setText("")
        self.btn_send_sms.setText("💬  Odeslat SMS škole přes ADB")
        self.btn_send_sms.setEnabled(True)

