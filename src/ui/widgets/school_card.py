from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...models.school import SchoolContact
from ..theme import theme_manager


class SchoolCardWidget(QWidget):
    """
    Moderní 'School Dossier' panel ve stylu Linear.
    Poskytuje okamžitý přehled o škole, kontaktní osobě, čísle a historii.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._current_phone: str = ""
        self._setup_ui()
        self._apply_theme()
        theme_manager.theme_changed.connect(self._apply_theme)

    def _setup_ui(self) -> None:
        self.setObjectName("schoolCardRoot")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # 1. Záhlaví dossieru (Název a Město)
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)

        self.lbl_school_name = QLabel("— Žádná škola nenačtena —")
        self.lbl_school_name.setObjectName("schoolName")
        self.lbl_school_name.setWordWrap(True)
        header_layout.addWidget(self.lbl_school_name)

        self.lbl_city = QLabel("Město: —")
        self.lbl_city.setObjectName("schoolCity")
        header_layout.addWidget(self.lbl_city)

        layout.addLayout(header_layout)

        # Jemná oddělovací linka
        self.sep = QFrame()
        self.sep.setFrameShape(QFrame.Shape.HLine)
        self.sep.setFrameShadow(QFrame.Shadow.Plain)
        layout.addWidget(self.sep)

        # 2. Kontaktní sekce (Telefon, Routing, Kopírování)
        contact_section = QVBoxLayout()
        contact_section.setSpacing(8)

        lbl_phone_section = QLabel("TELEFONNÍ ČÍSLO")
        lbl_phone_section.setObjectName("sectionKicker")
        contact_section.addWidget(lbl_phone_section)

        phone_row = QHBoxLayout()
        phone_row.setSpacing(10)

        self.lbl_phone = QLabel("—")
        self.lbl_phone.setObjectName("schoolPhone")
        phone_row.addWidget(self.lbl_phone)

        self.btn_copy_phone = QPushButton("Kopírovat")
        self.btn_copy_phone.setObjectName("btnCopyPhone")
        self.btn_copy_phone.setFixedHeight(28)
        self.btn_copy_phone.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_phone.setToolTip("Zkopírovat telefonní číslo do schránky")
        self.btn_copy_phone.clicked.connect(self._copy_phone)
        phone_row.addWidget(self.btn_copy_phone)

        self.lbl_routing_badge = QLabel("ČR • GSM")
        self.lbl_routing_badge.setObjectName("routingBadge")
        phone_row.addWidget(self.lbl_routing_badge)

        phone_row.addStretch()
        contact_section.addLayout(phone_row)
        layout.addLayout(contact_section)

        # 3. Mřížka podrobností (Kontaktní osoba & E-mail)
        details_grid = QGridLayout()
        details_grid.setHorizontalSpacing(24)
        details_grid.setVerticalSpacing(8)

        # Kontaktní osoba
        lbl_person_title = QLabel("KONTAKTNÍ OSOBA")
        lbl_person_title.setObjectName("sectionKicker")
        self.lbl_contact_person = QLabel("—")
        self.lbl_contact_person.setObjectName("detailValue")

        details_grid.addWidget(lbl_person_title, 0, 0)
        details_grid.addWidget(self.lbl_contact_person, 1, 0)

        # E-mail
        lbl_email_title = QLabel("E-MAIL")
        lbl_email_title.setObjectName("sectionKicker")
        self.lbl_email = QLabel("—")
        self.lbl_email.setObjectName("detailValue")

        details_grid.addWidget(lbl_email_title, 0, 1)
        details_grid.addWidget(self.lbl_email, 1, 1)

        layout.addLayout(details_grid)

        # 4. Historie a poznámky
        lbl_history_title = QLabel("HISTORIE A POZNÁMKY K TÉTO ŠKOLE")
        lbl_history_title.setObjectName("sectionKicker")
        layout.addWidget(lbl_history_title)

        self.txt_history = QTextEdit()
        self.txt_history.setObjectName("txtHistory")
        self.txt_history.setReadOnly(True)
        self.txt_history.setPlaceholderText("K této škole zatím nejsou žádné předchozí záznamy.")
        self.txt_history.setMinimumHeight(110)
        layout.addWidget(self.txt_history, stretch=1)

    def _copy_phone(self) -> None:
        if self._current_phone:
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(self._current_phone)
            original_text = "Kopírovat"
            self.btn_copy_phone.setText("Zkopírováno ✓")
            QTimer.singleShot(1500, lambda: self.btn_copy_phone.setText(original_text))

    def _apply_theme(self) -> None:
        t = theme_manager.tokens

        self.setStyleSheet(f"""
            QWidget#schoolCardRoot {{
                background-color: {t.bg_card};
                border: 1px solid {t.border_card};
                border-radius: 8px;
            }}
            QLabel#schoolName {{
                font-size: 20px;
                font-weight: 700;
                color: {t.text_primary};
                line-height: 1.25;
            }}
            QLabel#schoolCity {{
                font-size: 13px;
                font-weight: 500;
                color: {t.text_secondary};
            }}
            QFrame {{
                background-color: {t.border_subtle};
                max-height: 1px;
                border: none;
            }}
            QLabel#sectionKicker {{
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.6px;
                color: {t.text_muted};
            }}
            QLabel#schoolPhone {{
                font-size: 18px;
                font-weight: 700;
                font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                color: {t.text_primary};
                letter-spacing: 0.5px;
            }}
            QPushButton#btnCopyPhone {{
                font-size: 11px;
                font-weight: 600;
                background-color: {t.bg_card_secondary};
                color: {t.text_secondary};
                border: 1px solid {t.border_subtle};
                border-radius: 5px;
                padding: 3px 10px;
            }}
            QPushButton#btnCopyPhone:hover {{
                background-color: {t.bg_hover};
                color: {t.text_primary};
                border-color: {t.border_focus};
            }}
            QLabel#detailValue {{
                font-size: 14px;
                font-weight: 500;
                color: {t.text_primary};
            }}
            QTextEdit#txtHistory {{
                background-color: {t.bg_card_secondary};
                border: 1px solid {t.border_subtle};
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
                line-height: 1.5;
                color: {t.text_secondary};
            }}
        """)

        # Re-apply routing badge style if visible
        self._update_badge_style()

    def _update_badge_style(self, is_slovak: bool = False) -> None:
        t = theme_manager.tokens
        if is_slovak:
            self.lbl_routing_badge.setText("SK • VoIP (Odorik)")
            self.lbl_routing_badge.setStyleSheet(f"""
                QLabel#routingBadge {{
                    background-color: {t.accent_green_subtle};
                    color: {t.accent_green_text};
                    border: 1px solid {t.accent_green};
                    padding: 3px 9px;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 700;
                    letter-spacing: 0.3px;
                }}
            """)
        else:
            self.lbl_routing_badge.setText("ČR • GSM (Vodafone)")
            self.lbl_routing_badge.setStyleSheet(f"""
                QLabel#routingBadge {{
                    background-color: {t.accent_blue_subtle};
                    color: {t.accent_blue_text};
                    border: 1px solid {t.accent_blue};
                    padding: 3px 9px;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 700;
                    letter-spacing: 0.3px;
                }}
            """)

    def set_school(self, school: SchoolContact | None) -> None:
        """Naplní dossier daty o vybrané škole."""
        if not school:
            self._current_phone = ""
            self.lbl_school_name.setText("— Všechny školy zpracovány —")
            self.lbl_city.setText("Fronta kontaktů je prázdná")
            self.lbl_contact_person.setText("—")
            self.lbl_phone.setText("—")
            self.lbl_routing_badge.setVisible(False)
            self.btn_copy_phone.setVisible(False)
            self.lbl_email.setText("—")
            self.txt_history.setPlainText("")
            return

        self._current_phone = school.phone or school.clean_phone
        self.lbl_school_name.setText(school.name)
        self.lbl_city.setText(f"Město: {school.city}" if school.city else "Město: neuvedeno")
        self.lbl_contact_person.setText(school.contact_person or "Neuvedena")
        self.lbl_phone.setText(school.phone or "Neuveden")
        self.btn_copy_phone.setVisible(bool(school.phone))
        self.lbl_email.setText(school.email or "Neuveden")
        self.txt_history.setPlainText(school.previous_notes or "Zatím žádná zaznamenaná historie.")

        self.lbl_routing_badge.setVisible(True)
        self._update_badge_style(is_slovak=school.is_slovak)
