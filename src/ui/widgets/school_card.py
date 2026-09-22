from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...models.school import SchoolContact
from ..theme import (
    SCG_BLUE,
    SCG_DARK_BLUE,
    SCG_GREEN,
    TEXT_ON_GREEN,
)


class SchoolCardWidget(QWidget):
    """Zobrazuje přehledně všechny informace o vybrané škole a kontaktu."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Název školy
        self.lbl_school_name = QLabel("— Žádná škola nenačtena —")
        self.lbl_school_name.setStyleSheet(
            f"font-size: 22px; font-weight: 800; color: {SCG_DARK_BLUE}; line-height: 1.2;"
        )
        self.lbl_school_name.setWordWrap(True)
        layout.addWidget(self.lbl_school_name)

        # Město
        self.lbl_city = QLabel("Město: —")
        self.lbl_city.setStyleSheet("font-size: 14px; font-weight: 500; color: #475569;")
        layout.addWidget(self.lbl_city)

        # Oddělovací čára
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setStyleSheet(f"border-color: #e2e8f0;")
        layout.addWidget(sep)

        # Mřížka s kontaktními údaji
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)

        lbl_person_title = QLabel("Kontaktní osoba:")
        lbl_person_title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {SCG_DARK_BLUE};")
        self.lbl_contact_person = QLabel("—")
        self.lbl_contact_person.setStyleSheet("font-size: 15px; font-weight: 600; color: #0f172a;")

        lbl_phone_title = QLabel("Telefon:")
        lbl_phone_title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {SCG_DARK_BLUE};")
        self.lbl_phone = QLabel("—")
        self.lbl_phone.setStyleSheet(
            f"font-size: 20px; font-weight: 900; color: {SCG_DARK_BLUE}; letter-spacing: 0.5px;"
        )

        self.lbl_routing_badge = QLabel("ČR – Vodafone GSM")
        self.lbl_routing_badge.setStyleSheet(
            f"background-color: #edf5fd; color: {SCG_DARK_BLUE}; border: 1px solid {SCG_BLUE}; "
            f"padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: bold;"
        )

        lbl_email_title = QLabel("E-mail:")
        lbl_email_title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {SCG_DARK_BLUE};")
        self.lbl_email = QLabel("—")
        self.lbl_email.setStyleSheet("font-size: 15px; font-weight: 600; color: #0f172a;")

        grid.addWidget(lbl_person_title, 0, 0)
        grid.addWidget(self.lbl_contact_person, 0, 1)

        grid.addWidget(lbl_phone_title, 1, 0)
        phone_box = QHBoxLayout()
        phone_box.addWidget(self.lbl_phone)
        phone_box.addWidget(self.lbl_routing_badge)
        phone_box.addStretch()
        grid.addLayout(phone_box, 1, 1)

        grid.addWidget(lbl_email_title, 2, 0)
        grid.addWidget(self.lbl_email, 2, 1)

        layout.addLayout(grid)

        # Předchozí historie / poznámky
        lbl_history_title = QLabel("Předchozí historie a poznámky k této škole:")
        lbl_history_title.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {SCG_DARK_BLUE}; margin-top: 8px;"
        )
        layout.addWidget(lbl_history_title)

        self.txt_history = QTextEdit()
        self.txt_history.setReadOnly(True)
        self.txt_history.setPlaceholderText("Žádné předchozí záznamy.")
        self.txt_history.setMinimumHeight(90)
        self.txt_history.setStyleSheet("""
            QTextEdit {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 10px;
                font-size: 13px;
                color: #1e293b;
                line-height: 1.4;
            }
        """)
        layout.addWidget(self.txt_history)

    def set_school(self, school: SchoolContact | None) -> None:
        """Naplní widget daty o škole."""
        if not school:
            self.lbl_school_name.setText("— Žádná další škola ve frontě —")
            self.lbl_city.setText("")
            self.lbl_contact_person.setText("—")
            self.lbl_phone.setText("—")
            self.lbl_routing_badge.setVisible(False)
            self.lbl_email.setText("—")
            self.txt_history.setPlainText("")
            return

        self.lbl_school_name.setText(school.name)
        self.lbl_city.setText(f"Město: {school.city}")
        self.lbl_contact_person.setText(school.contact_person or "Neuvedeno")
        self.lbl_phone.setText(school.phone)
        self.lbl_email.setText(school.email or "Neuveden")
        self.txt_history.setPlainText(school.previous_notes or "Zatím žádná historie k této škole.")

        # Routing badge
        self.lbl_routing_badge.setVisible(True)
        if school.is_slovak:
            self.lbl_routing_badge.setText("🇸🇰 SK -> Odorik VoIP (Zoiper)")
            self.lbl_routing_badge.setStyleSheet(
                f"background-color: #eefbf6; color: {TEXT_ON_GREEN}; border: 1.5px solid {SCG_GREEN}; "
                f"padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: bold;"
            )
        else:
            self.lbl_routing_badge.setText("🇨🇿 ČR -> Vodafone GSM (SIM)")
            self.lbl_routing_badge.setStyleSheet(
                f"background-color: #edf5fd; color: {SCG_DARK_BLUE}; border: 1.5px solid {SCG_BLUE}; "
                f"padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: bold;"
            )
