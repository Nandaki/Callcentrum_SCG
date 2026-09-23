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
    """Segmentovaná dlaždice výsledku hovoru."""

    def __init__(self, key_shortcut: str, text: str, result_type: CallResultType, parent: QWidget | None = None):
        super().__init__(parent)
        self.key_shortcut = key_shortcut
        self.result_type = result_type
        self.title_text = text
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(38)
        self.setText(self.title_text)
        self.setToolTip(f"Klávesová zkratka: {self.key_shortcut}")


class ResultPanelWidget(QWidget):
    """
    Panel pro zápis výsledku hovoru.
    Čisté dlaždice bez rušivých závorek v popiscích, podpora klávesových zkratek 1-5 a Enter.
    """

    result_submitted = Signal(CallResult)
    send_sms_requested = Signal()
    send_email_requested = Signal()
    skip_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.tiles: List[ResultTileButton] = []
        self._setup_ui()
        self._apply_theme()
        theme_manager.theme_changed.connect(self._apply_theme)

    def _setup_ui(self) -> None:
        self.setObjectName("resultPanelRoot")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        # 1. Nadpis sekce
        lbl_section = QLabel("VÝSLEDEK HOVORU")
        lbl_section.setObjectName("sectionKicker")
        layout.addWidget(lbl_section)

        # 2. Segmentované dlaždice (čisté texty)
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)

        tiles_data: List[Tuple[str, str, CallResultType]] = [
            ("1", "Zaujali jsme", CallResultType.INTERESTED),
            ("2", "Nezájem", CallResultType.NOT_INTERESTED),
            ("3", "Asi ok", CallResultType.OK_MAYBE),
            ("4", "Nedovoláno", CallResultType.UNANSWERED),
            ("5", "Poslat mail", CallResultType.SEND_MAIL),
        ]

        tiles_layout = QVBoxLayout()
        tiles_layout.setSpacing(6)

        for idx, (key, text, res_type) in enumerate(tiles_data):
            btn = ResultTileButton(key, text, res_type, self)
            self.btn_group.addButton(btn, idx)
            self.tiles.append(btn)
            tiles_layout.addWidget(btn)

        self.btn_group.idClicked.connect(self._on_tile_clicked)
        layout.addLayout(tiles_layout)

        # 3. Tlačítka pro odeslání zpráv (SMS & E-mail)
        msg_layout = QVBoxLayout()
        msg_layout.setSpacing(6)

        msg_btn_row = QHBoxLayout()
        msg_btn_row.setSpacing(8)

        self.btn_send_sms = QPushButton("💬 Odeslat SMS")
        self.btn_send_sms.setObjectName("btnSendSms")
        self.btn_send_sms.setFixedHeight(38)
        self.btn_send_sms.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send_sms.setToolTip("Odeslat přednastavenou SMS přes telefon (klávesa S)")
        self.btn_send_sms.clicked.connect(self._on_send_sms_clicked)
        msg_btn_row.addWidget(self.btn_send_sms, stretch=1)

        self.btn_send_email = QPushButton("✉️ Odeslat e-mail")
        self.btn_send_email.setObjectName("btnSendEmail")
        self.btn_send_email.setFixedHeight(38)
        self.btn_send_email.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send_email.setToolTip("Odeslat podklady e-mailem škole (klávesa E nebo M)")
        self.btn_send_email.clicked.connect(self._on_send_email_clicked)
        msg_btn_row.addWidget(self.btn_send_email, stretch=1)

        msg_layout.addLayout(msg_btn_row)

        self.lbl_sms_status = QLabel("")
        self.lbl_sms_status.setObjectName("smsStatus")
        msg_layout.addWidget(self.lbl_sms_status)

        layout.addLayout(msg_layout)

        # 4. Poznámka operátora
        lbl_note_section = QLabel("POZNÁMKA K HOVORU")
        lbl_note_section.setObjectName("sectionKicker")
        layout.addWidget(lbl_note_section)

        self.txt_note = QTextEdit()
        self.txt_note.setObjectName("txtNote")
        self.txt_note.setPlaceholderText("Poznámka k hovoru (např. volat zítra po 10:00)...")
        self.txt_note.setMaximumHeight(65)
        layout.addWidget(self.txt_note)

        # 5. Tlačítka pro přeskočení a uložení výsledku
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.btn_skip = QPushButton("Přeskočit")
        self.btn_skip.setObjectName("btnSkip")
        self.btn_skip.setFixedHeight(44)
        self.btn_skip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_skip.setToolTip("Přeskočit tuto školu bez zápisu do tabulky")
        self.btn_skip.clicked.connect(self.skip_requested.emit)
        action_row.addWidget(self.btn_skip, stretch=1)

        self.btn_submit = QPushButton("Uložit výsledek")
        self.btn_submit.setObjectName("btnSubmit")
        self.btn_submit.setFixedHeight(44)
        self.btn_submit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_submit.setToolTip("Uložit výsledek do tabulky a načíst další kontakt (klávesa Enter)")
        self.btn_submit.clicked.connect(self._on_submit_clicked)
        action_row.addWidget(self.btn_submit, stretch=2)

        layout.addLayout(action_row)

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
                letter-spacing: 0.5px;
                color: {t.text_muted};
            }}
            QPushButton[checkable="true"] {{
                text-align: left;
                padding-left: 14px;
                font-size: 13px;
                font-weight: 600;
                background-color: {t.bg_card_secondary};
                color: {t.text_primary};
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
            QPushButton#btnSendSms, QPushButton#btnSendEmail {{
                background-color: {t.bg_card_secondary};
                color: {t.text_primary};
                font-size: 13px;
                font-weight: 600;
                border: 1px solid {t.border_subtle};
                border-radius: 6px;
            }}
            QPushButton#btnSendSms:hover, QPushButton#btnSendEmail:hover {{
                background-color: {t.bg_hover};
                border-color: {t.border_focus};
            }}
            QPushButton#btnSendSms:disabled, QPushButton#btnSendEmail:disabled {{
                background-color: {t.bg_card_secondary};
                color: {t.text_muted};
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
            QPushButton#btnSkip {{
                background-color: {t.bg_card_secondary};
                color: {t.text_secondary};
                font-size: 13px;
                font-weight: 600;
                border: 1px solid {t.border_subtle};
                border-radius: 6px;
            }}
            QPushButton#btnSkip:hover {{
                background-color: {t.bg_hover};
                color: {t.text_primary};
                border-color: {t.border_focus};
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
        """Vybere výchozí stav pro timeout (Nedovoláno)."""
        self.select_outcome_by_key("4")
        t = theme_manager.tokens
        self.lbl_sms_status.setText("Odesílám automatickou SMS...")
        self.lbl_sms_status.setStyleSheet(f"color: {t.accent_amber}; font-size: 12px; font-weight: 600;")

    def _on_tile_clicked(self, btn_id: int) -> None:
        btn = self.btn_group.button(btn_id)
        if btn and isinstance(btn, ResultTileButton) and btn.result_type == CallResultType.SEND_MAIL:
            t = theme_manager.tokens
            self.lbl_sms_status.setText("💡 Zvoleno 'Poslat mail' — připravte e-mail tlačítkem 'Odeslat e-mail' nebo klávesou M.")
            self.lbl_sms_status.setStyleSheet(f"color: {t.accent_blue}; font-size: 12px; font-weight: 600;")

    def _on_send_sms_clicked(self) -> None:
        t = theme_manager.tokens
        self.btn_send_sms.setEnabled(False)
        self.lbl_sms_status.setText("Odesílám SMS přes ADB...")
        self.lbl_sms_status.setStyleSheet(f"color: {t.accent_amber}; font-size: 12px; font-weight: 600;")
        self.send_sms_requested.emit()

    def _on_send_email_clicked(self) -> None:
        self.send_email_requested.emit()

    def set_sms_result(self, ok: bool, msg: str) -> None:
        t = theme_manager.tokens
        self.btn_send_sms.setEnabled(True)
        if ok:
            self.btn_send_sms.setText("SMS odeslána ✓")
            self.lbl_sms_status.setText(msg)
            self.lbl_sms_status.setStyleSheet(f"color: {t.accent_green_text}; font-size: 12px; font-weight: 600;")
        else:
            self.btn_send_sms.setText("Zkusit poslat SMS znovu")
            self.lbl_sms_status.setText(f"Chyba: {msg}")
            self.lbl_sms_status.setStyleSheet(f"color: {t.accent_red}; font-size: 12px; font-weight: 600;")

    def set_email_result(self, ok: bool, msg: str) -> None:
        t = theme_manager.tokens
        if ok:
            self.btn_send_email.setText("E-mail odeslán ✓")
            self.lbl_sms_status.setText(msg)
            self.lbl_sms_status.setStyleSheet(f"color: {t.accent_green_text}; font-size: 12px; font-weight: 600;")
        else:
            self.lbl_sms_status.setText(f"Chyba e-mailu: {msg}")
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
        self.btn_send_sms.setText("💬 Odeslat SMS")
        self.btn_send_sms.setEnabled(True)
        self.btn_send_email.setText("✉️ Odeslat e-mail")
        self.btn_send_email.setEnabled(True)
