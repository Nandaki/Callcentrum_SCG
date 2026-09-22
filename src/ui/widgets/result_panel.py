from __future__ import annotations

from typing import List, Tuple
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...models.school import CallResult, CallResultType
from ..theme import theme_manager


class ResultTileButton(QPushButton):
    """Segmentovaná dlaždice výsledku hovoru s kbd zkratkou."""

    def __init__(self, key_shortcut: str, text: str, result_type: CallResultType, parent: QWidget | None = None):
        super().__init__(parent)
        self.key_shortcut = key_shortcut
        self.result_type = result_type
        self.title_text = text
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(38)
        self._update_text()

    def _update_text(self) -> None:
        self.setText(f"[{self.key_shortcut}]  {self.title_text}")


class ResultPanelWidget(QWidget):
    """
    Moderní panel pro zápis výsledku hovoru ve stylu Linear.
    Využívá segmentované dlaždice s klávesovými zkratkami [1] až [5].
    """

    result_submitted = Signal(CallResult)
    send_sms_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.tiles: List[ResultTileButton] = []
        self._setup_ui()
        self._apply_theme()
        theme_manager.theme_changed.connect(self._apply_theme)

    def _setup_ui(self) -> None:
        self.setObjectName("resultPanelRoot")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        # 1. Kicker nadpis: Výsledek hovoru
        lbl_section = QLabel("VÝSLEDEK HOVORU")
        lbl_section.setObjectName("sectionKicker")
        layout.addWidget(lbl_section)

        # 2. Segmentované dlaždice (QButtonGroup)
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)

        tiles_data: List[Tuple[str, str, CallResultType]] = [
            ("1", "Má zájem (zaslat podklady)", CallResultType.INTERESTED),
            ("2", "Nemá zájem", CallResultType.NOT_INTERESTED),
            ("3", "Nezastiženi (vypršel limit / SMS)", CallResultType.UNANSWERED),
            ("4", "Zavolat později / jiný termín", CallResultType.CALL_LATER),
            ("5", "Špatné číslo / Neexistuje", CallResultType.WRONG_NUMBER),
        ]

        tiles_layout = QVBoxLayout()
        tiles_layout.setSpacing(6)

        for idx, (key, text, res_type) in enumerate(tiles_data):
            btn = ResultTileButton(key, text, res_type, self)
            self.btn_group.addButton(btn, idx)
            self.tiles.append(btn)
            tiles_layout.addWidget(btn)

        layout.addLayout(tiles_layout)

        # 3. Tlačítko pro odeslání SMS přes ADB
        sms_layout = QVBoxLayout()
        sms_layout.setSpacing(4)

        self.btn_send_sms = QPushButton("Odeslat SMS škole přes ADB  [S]")
        self.btn_send_sms.setObjectName("btnSendSms")
        self.btn_send_sms.setFixedHeight(38)
        self.btn_send_sms.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send_sms.clicked.connect(self._on_send_sms_clicked)
        sms_layout.addWidget(self.btn_send_sms)

        self.lbl_sms_status = QLabel("")
        self.lbl_sms_status.setObjectName("smsStatus")
        sms_layout.addWidget(self.lbl_sms_status)

        layout.addLayout(sms_layout)

        # 4. Poznámka operátora
        lbl_note_section = QLabel("POZNÁMKA K HOVORU")
        lbl_note_section.setObjectName("sectionKicker")
        layout.addWidget(lbl_note_section)

        self.txt_note = QTextEdit()
        self.txt_note.setObjectName("txtNote")
        self.txt_note.setPlaceholderText("Např. Paní zástupkyně je na poradě, zavolat zítra po 10:00...")
        self.txt_note.setMaximumHeight(65)
        layout.addWidget(self.txt_note)

        # 5. Hlavní akční tlačítko pro uložení výsledku
        self.btn_submit = QPushButton("Uložit výsledek a načíst další školu  [Enter]")
        self.btn_submit.setObjectName("btnSubmit")
        self.btn_submit.setFixedHeight(44)
        self.btn_submit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_submit.clicked.connect(self._on_submit_clicked)
        layout.addWidget(self.btn_submit)

    def _apply_theme(self) -> None:
        t = theme_manager.tokens

        self.setStyleSheet(f"""
            QWidget#resultPanelRoot {{
                background-color: {t.bg_card};
                border: 1px solid {t.border_card};
                border-radius: 8px;
            }}
            QLabel#sectionKicker {{
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.6px;
                color: {t.text_muted};
            }}
            QPushButton[checkable="true"] {{
                text-align: left;
                padding-left: 12px;
                font-size: 13px;
                font-weight: 600;
                background-color: {t.bg_card_secondary};
                color: {t.text_secondary};
                border: 1px solid {t.border_subtle};
                border-radius: 6px;
            }}
            QPushButton[checkable="true"]:hover {{
                background-color: {t.bg_hover};
                color: {t.text_primary};
                border-color: {t.border_focus};
            }}
            QPushButton[checkable="true"]:checked {{
                background-color: {t.accent_blue_subtle};
                color: {t.accent_blue_text};
                border: 1.5px solid {t.accent_blue};
                font-weight: 700;
            }}
            QPushButton#btnSendSms {{
                background-color: {t.bg_card_secondary};
                color: {t.text_primary};
                font-size: 13px;
                font-weight: 600;
                border: 1px solid {t.border_subtle};
                border-radius: 6px;
            }}
            QPushButton#btnSendSms:hover {{
                background-color: {t.bg_hover};
                border-color: {t.border_focus};
            }}
            QPushButton#btnSendSms:disabled {{
                background-color: {t.bg_card_secondary};
                color: {t.text_dimmed};
                border-color: {t.border_subtle};
            }}
            QLabel#smsStatus {{
                font-size: 12px;
                font-weight: 600;
                color: {t.accent_green_text};
                padding-left: 2px;
            }}
            QTextEdit#txtNote {{
                background-color: {t.bg_input};
                border: 1px solid {t.border_subtle};
                border-radius: 6px;
                padding: 8px 10px;
                font-size: 13px;
                color: {t.text_primary};
            }}
            QTextEdit#txtNote:focus {{
                border: 1.5px solid {t.border_focus};
            }}
            QPushButton#btnSubmit {{
                background-color: {t.btn_primary_bg};
                color: {t.btn_primary_text};
                font-size: 14px;
                font-weight: 700;
                border-radius: 6px;
                border: none;
            }}
            QPushButton#btnSubmit:hover {{
                background-color: {t.btn_primary_hover};
            }}
        """)

    def select_outcome_by_key(self, key_char: str) -> None:
        """Vybere dlaždici podle čísla '1' až '5'."""
        for tile in self.tiles:
            if tile.key_shortcut == key_char:
                tile.setChecked(True)
                break

    def select_timeout_default(self) -> None:
        """Vybere výchozí stav pro timeout (Nezastiženi)."""
        self.select_outcome_by_key("3")
        t = theme_manager.tokens
        self.lbl_sms_status.setText("Odesílám automatickou SMS...")
        self.lbl_sms_status.setStyleSheet(f"color: {t.accent_amber}; font-size: 12px; font-weight: 600;")

    def _on_send_sms_clicked(self) -> None:
        t = theme_manager.tokens
        self.btn_send_sms.setEnabled(False)
        self.lbl_sms_status.setText("Odesílám SMS přes ADB...")
        self.lbl_sms_status.setStyleSheet(f"color: {t.accent_amber}; font-size: 12px; font-weight: 600;")
        self.send_sms_requested.emit()

    def set_sms_result(self, ok: bool, msg: str) -> None:
        t = theme_manager.tokens
        self.btn_send_sms.setEnabled(True)
        if ok:
            self.btn_send_sms.setText("SMS odeslána ✓  [S]")
            self.lbl_sms_status.setText(msg)
            self.lbl_sms_status.setStyleSheet(f"color: {t.accent_green}; font-size: 12px; font-weight: 600;")
        else:
            self.btn_send_sms.setText("Zkusit poslat SMS znovu  [S]")
            self.lbl_sms_status.setText(f"Chyba: {msg}")
            self.lbl_sms_status.setStyleSheet(f"color: {t.accent_red}; font-size: 12px; font-weight: 600;")

    def _on_submit_clicked(self) -> None:
        checked_btn = self.btn_group.checkedButton()
        if checked_btn and isinstance(checked_btn, ResultTileButton):
            result_type = checked_btn.result_type
        else:
            result_type = CallResultType.CUSTOM

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
        self.btn_send_sms.setText("Odeslat SMS škole přes ADB  [S]")
        self.btn_send_sms.setEnabled(True)
