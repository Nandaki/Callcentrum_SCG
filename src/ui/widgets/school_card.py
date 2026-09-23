from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
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
    Panel s informacemi o škole a kontaktu.
    Vysoký kontrast, čistá typografie, plná čitelnost v dark i light módu.
    Obsahuje i spodní přehled předchozí a další školy s výsledkem a možností přeskočení.
    """

    prev_requested = Signal()
    next_requested = Signal()
    skip_requested = Signal()
    edit_email_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._current_phone: str = ""
        self._setup_ui()
        self._apply_theme()
        theme_manager.theme_changed.connect(self._apply_theme)

    def _setup_ui(self) -> None:
        self.setObjectName("schoolCardRoot")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        # 1. Záhlaví (Název a Město)
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

        # Oddělovací linka s explicitním ID (nesmí ovlivnit QLabel!)
        self.sep = QFrame()
        self.sep.setObjectName("schoolCardSep")
        self.sep.setFrameShape(QFrame.Shape.HLine)
        self.sep.setFixedHeight(1)
        layout.addWidget(self.sep)

        # 2. Kontaktní sekce (Telefon, Routing, Kopírování)
        contact_section = QVBoxLayout()
        contact_section.setSpacing(8)

        lbl_phone_section = QLabel("TELEFONNÍ ČÍSLO")
        lbl_phone_section.setObjectName("sectionKicker")
        contact_section.addWidget(lbl_phone_section)

        phone_row = QHBoxLayout()
        phone_row.setSpacing(12)

        self.lbl_phone = QLabel("—")
        self.lbl_phone.setObjectName("schoolPhone")
        phone_row.addWidget(self.lbl_phone)

        self.btn_copy_phone = QPushButton("Kopírovat")
        self.btn_copy_phone.setObjectName("btnCopyPhone")
        self.btn_copy_phone.setFixedHeight(30)
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
        email_header_box = QHBoxLayout()
        email_header_box.setSpacing(6)
        lbl_email_title = QLabel("E-MAIL")
        lbl_email_title.setObjectName("sectionKicker")
        email_header_box.addWidget(lbl_email_title)

        self.btn_edit_email = QPushButton("✏️ Napsat adresu")
        self.btn_edit_email.setObjectName("btnEditEmail")
        self.btn_edit_email.setFixedHeight(22)
        self.btn_edit_email.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_edit_email.setToolTip("Zadat nebo upravit e-mailovou adresu školy")
        self.btn_edit_email.clicked.connect(self.edit_email_requested.emit)
        email_header_box.addWidget(self.btn_edit_email)
        email_header_box.addStretch()

        self.lbl_email = QLabel("—")
        self.lbl_email.setObjectName("detailValue")

        details_grid.addLayout(email_header_box, 0, 1)
        details_grid.addWidget(self.lbl_email, 1, 1)

        # Organizátor (sloupec Volá)
        lbl_org_title = QLabel("ORGANIZÁTOR")
        lbl_org_title.setObjectName("sectionKicker")
        self.lbl_organizer = QLabel("—")
        self.lbl_organizer.setObjectName("detailValue")

        details_grid.addWidget(lbl_org_title, 0, 2)
        details_grid.addWidget(self.lbl_organizer, 1, 2)

        layout.addLayout(details_grid)

        # 4. Historie a poznámky
        lbl_history_title = QLabel("HISTORIE A POZNÁMKY K TÉTO ŠKOLE")
        lbl_history_title.setObjectName("sectionKicker")
        layout.addWidget(lbl_history_title)

        self.txt_history = QTextEdit()
        self.txt_history.setObjectName("txtHistory")
        self.txt_history.setReadOnly(True)
        self.txt_history.setPlaceholderText("K této škole zatím nejsou žádné předchozí záznamy.")
        self.txt_history.setMinimumHeight(65)
        self.txt_history.setMaximumHeight(100)
        layout.addWidget(self.txt_history)

        # 5. Navigace pod poznámkami: Předchozí a další škola s výsledkem
        self.nav_card = QFrame()
        self.nav_card.setObjectName("navCard")
        nav_layout = QVBoxLayout(self.nav_card)
        nav_layout.setContentsMargins(12, 10, 12, 10)
        nav_layout.setSpacing(8)

        # Horní lišta navigace: Titulek a tlačítko Přeskočit
        nav_header = QHBoxLayout()
        lbl_nav_title = QLabel("PŘEHLED FRONTY & HISTORIE")
        lbl_nav_title.setObjectName("sectionKicker")
        nav_header.addWidget(lbl_nav_title)
        nav_header.addStretch()

        self.btn_skip_card = QPushButton("Přeskočit tuto školu")
        self.btn_skip_card.setObjectName("btnNavSkip")
        self.btn_skip_card.setFixedHeight(26)
        self.btn_skip_card.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_skip_card.setToolTip("Přeskočit aktuální školu a pokračovat na další (bez zápisu do tabulky)")
        self.btn_skip_card.clicked.connect(self.skip_requested.emit)
        nav_header.addWidget(self.btn_skip_card)
        nav_layout.addLayout(nav_header)

        # Dva sloupce: Předchozí škola vs. Další škola
        cols_layout = QHBoxLayout()
        cols_layout.setSpacing(10)

        # --- Box předchozí školy ---
        self.box_prev = QFrame()
        self.box_prev.setObjectName("navSchoolBox")
        box_prev_l = QVBoxLayout(self.box_prev)
        box_prev_l.setContentsMargins(12, 8, 12, 8)
        box_prev_l.setSpacing(4)

        box_prev_top = QHBoxLayout()
        lbl_prev_sub = QLabel("PŘEDCHOZÍ ŠKOLA")
        lbl_prev_sub.setObjectName("navKicker")
        box_prev_top.addWidget(lbl_prev_sub)
        box_prev_top.addStretch()

        self.btn_prev_school = QPushButton("◀ Zpět")
        self.btn_prev_school.setObjectName("btnNavAction")
        self.btn_prev_school.setFixedHeight(22)
        self.btn_prev_school.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev_school.setToolTip("Přejít zpět na předchozí školu")
        self.btn_prev_school.clicked.connect(self.prev_requested.emit)
        box_prev_top.addWidget(self.btn_prev_school)
        box_prev_l.addLayout(box_prev_top)

        self.lbl_prev_name = QLabel("— Na začátku fronty —")
        self.lbl_prev_name.setObjectName("navSchoolName")
        box_prev_l.addWidget(self.lbl_prev_name)

        prev_res_box = QHBoxLayout()
        prev_res_box.setSpacing(6)
        lbl_p_res = QLabel("Výsledek:")
        lbl_p_res.setObjectName("navResultLabel")
        prev_res_box.addWidget(lbl_p_res)

        self.lbl_prev_result = QLabel("—")
        self.lbl_prev_result.setObjectName("navResultBadge")
        prev_res_box.addWidget(self.lbl_prev_result)
        prev_res_box.addStretch()
        box_prev_l.addLayout(prev_res_box)

        cols_layout.addWidget(self.box_prev, stretch=1)

        # --- Box další školy ---
        self.box_next = QFrame()
        self.box_next.setObjectName("navSchoolBox")
        box_next_l = QVBoxLayout(self.box_next)
        box_next_l.setContentsMargins(12, 8, 12, 8)
        box_next_l.setSpacing(4)

        box_next_top = QHBoxLayout()
        lbl_next_sub = QLabel("DALŠÍ V POŘADÍ")
        lbl_next_sub.setObjectName("navKicker")
        box_next_top.addWidget(lbl_next_sub)
        box_next_top.addStretch()

        self.btn_next_school = QPushButton("Přejít ▶")
        self.btn_next_school.setObjectName("btnNavAction")
        self.btn_next_school.setFixedHeight(22)
        self.btn_next_school.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next_school.setToolTip("Přejít na následující školu")
        self.btn_next_school.clicked.connect(self.next_requested.emit)
        box_next_top.addWidget(self.btn_next_school)
        box_next_l.addLayout(box_next_top)

        self.lbl_next_name = QLabel("— Žádná další škola —")
        self.lbl_next_name.setObjectName("navSchoolName")
        box_next_l.addWidget(self.lbl_next_name)

        self.lbl_next_info = QLabel("—")
        self.lbl_next_info.setObjectName("navSchoolInfo")
        box_next_l.addWidget(self.lbl_next_info)

        cols_layout.addWidget(self.box_next, stretch=1)

        nav_layout.addLayout(cols_layout)
        layout.addWidget(self.nav_card)

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
            }}
            QLabel#schoolCity {{
                font-size: 13px;
                font-weight: 500;
                color: {t.text_secondary};
            }}
            QFrame#schoolCardSep {{
                background-color: {t.border_subtle};
                border: none;
            }}
            QLabel#sectionKicker {{
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
                color: {t.text_muted};
            }}
            QLabel#schoolPhone {{
                font-size: 20px;
                font-weight: 700;
                color: {t.text_primary};
            }}
            QPushButton#btnCopyPhone {{
                font-size: 12px;
                font-weight: 600;
                background-color: {t.bg_card_secondary};
                color: {t.text_primary};
                border: 1px solid {t.border_subtle};
                border-radius: 5px;
                padding: 4px 12px;
            }}
            QPushButton#btnCopyPhone:hover {{
                background-color: {t.bg_hover};
                color: {t.text_primary};
                border-color: {t.border_focus};
            }}
            QPushButton#btnEditEmail {{
                font-size: 11px;
                font-weight: 600;
                color: {t.accent_blue};
                background-color: {t.bg_card_secondary};
                border: 1px solid {t.border_subtle};
                border-radius: 4px;
                padding: 1px 7px;
            }}
            QPushButton#btnEditEmail:hover {{
                border-color: {t.accent_blue};
                background-color: {t.accent_blue_subtle};
            }}
            QLabel#detailValue {{
                font-size: 14px;
                font-weight: 600;
                color: {t.text_primary};
            }}
            QTextEdit#txtHistory {{
                background-color: {t.bg_card_secondary};
                border: 1px solid {t.border_subtle};
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
                color: {t.text_primary};
            }}
            QFrame#navCard {{
                background-color: {t.bg_card_secondary};
                border: 1px solid {t.border_subtle};
                border-radius: 8px;
            }}
            QFrame#navSchoolBox {{
                background-color: {t.bg_card};
                border: 1px solid {t.border_subtle};
                border-radius: 6px;
            }}
            QLabel#navKicker {{
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.5px;
                color: {t.text_muted};
            }}
            QLabel#navSchoolName {{
                font-size: 12px;
                font-weight: 700;
                color: {t.text_primary};
            }}
            QLabel#navSchoolInfo {{
                font-size: 11px;
                font-weight: 500;
                color: {t.text_secondary};
            }}
            QLabel#navResultLabel {{
                font-size: 11px;
                font-weight: 600;
                color: {t.text_muted};
            }}
            QLabel#navResultBadge {{
                font-size: 11px;
                font-weight: 700;
                padding: 2px 7px;
                border-radius: 4px;
                background-color: {t.bg_card_secondary};
                color: {t.text_secondary};
                border: 1px solid {t.border_subtle};
            }}
            QPushButton#btnNavAction {{
                background-color: {t.bg_card_secondary};
                color: {t.text_primary};
                font-size: 11px;
                font-weight: 600;
                border: 1px solid {t.border_subtle};
                border-radius: 4px;
                padding: 2px 8px;
            }}
            QPushButton#btnNavAction:hover {{
                background-color: {t.bg_hover};
                border-color: {t.border_focus};
            }}
            QPushButton#btnNavAction:disabled {{
                color: {t.text_dimmed};
                border-color: transparent;
                background-color: transparent;
            }}
            QPushButton#btnNavSkip {{
                background-color: {t.bg_card};
                color: {t.text_secondary};
                font-size: 11px;
                font-weight: 600;
                border: 1px solid {t.border_subtle};
                border-radius: 4px;
                padding: 3px 10px;
            }}
            QPushButton#btnNavSkip:hover {{
                background-color: {t.bg_hover};
                color: {t.text_primary};
                border-color: {t.border_focus};
            }}
        """)

        self._update_badge_style()

    def _update_badge_style(self, is_slovak: bool = False) -> None:
        t = theme_manager.tokens
        if is_slovak:
            self.lbl_routing_badge.setText("SK • VoIP")
            self.lbl_routing_badge.setStyleSheet(f"""
                QLabel#routingBadge {{
                    background-color: {t.accent_green_subtle};
                    color: {t.accent_green_text};
                    border: 1px solid {t.accent_green};
                    padding: 3px 9px;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 700;
                }}
            """)
        else:
            self.lbl_routing_badge.setText("ČR • GSM")
            self.lbl_routing_badge.setStyleSheet(f"""
                QLabel#routingBadge {{
                    background-color: {t.accent_blue_subtle};
                    color: {t.accent_blue_text};
                    border: 1px solid {t.accent_blue};
                    padding: 3px 9px;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 700;
                }}
            """)

    def update_navigation(
        self,
        prev_school: SchoolContact | None,
        prev_result: str | None,
        next_school: SchoolContact | None,
    ) -> None:
        """Aktualizuje spodní karty předchozí a další školy včetně výsledku hovoru."""
        t = theme_manager.tokens

        # 1. Předchozí škola
        if prev_school:
            short_prev = prev_school.name if len(prev_school.name) <= 44 else prev_school.name[:41] + "..."
            self.lbl_prev_name.setText(short_prev)
            self.lbl_prev_name.setToolTip(prev_school.name)
            self.btn_prev_school.setEnabled(True)

            res_str = prev_result or "Zpracováno"
            self.lbl_prev_result.setText(res_str)

            if "Zaujali" in res_str:
                c = t.accent_green_text
                bg = t.accent_green_subtle
                b = t.accent_green
            elif "Nezájem" in res_str:
                c = t.accent_red_text
                bg = t.accent_red_subtle
                b = t.accent_red
            elif "Asi ok" in res_str:
                c = t.accent_blue_text
                bg = t.accent_blue_subtle
                b = t.accent_blue
            elif "Nedovoláno" in res_str or "mail" in res_str.lower():
                c = t.accent_amber_text
                bg = t.accent_amber_subtle
                b = t.accent_amber
            elif "Přeskočeno" in res_str:
                c = t.text_muted
                bg = t.bg_card_secondary
                b = t.border_subtle
            else:
                c = t.text_secondary
                bg = t.bg_card_secondary
                b = t.border_subtle

            self.lbl_prev_result.setStyleSheet(f"""
                QLabel#navResultBadge {{
                    color: {c};
                    background-color: {bg};
                    border: 1px solid {b};
                    padding: 2px 7px;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 700;
                }}
            """)
        else:
            self.lbl_prev_name.setText("— Na začátku fronty —")
            self.lbl_prev_name.setToolTip("")
            self.lbl_prev_result.setText("—")
            self.lbl_prev_result.setStyleSheet(f"""
                QLabel#navResultBadge {{
                    color: {t.text_dimmed};
                    background-color: transparent;
                    border: none;
                    font-size: 11px;
                }}
            """)
            self.btn_prev_school.setEnabled(False)

        # 2. Další škola
        if next_school:
            short_next = next_school.name if len(next_school.name) <= 44 else next_school.name[:41] + "..."
            self.lbl_next_name.setText(short_next)
            self.lbl_next_name.setToolTip(next_school.name)
            parts = []
            if next_school.city:
                parts.append(next_school.city)
            if next_school.phone:
                parts.append(next_school.phone)
            self.lbl_next_info.setText(" • ".join(parts) or "Připraveno ve frontě")
            self.btn_next_school.setEnabled(True)
        else:
            self.lbl_next_name.setText("— Konec fronty —")
            self.lbl_next_name.setToolTip("")
            self.lbl_next_info.setText("Všechny školy zkontrolovány")
            self.btn_next_school.setEnabled(False)

    def set_school(self, school: SchoolContact | None) -> None:
        """Naplní dossier daty o vybrané škole."""
        if not school:
            self._current_phone = ""
            self.lbl_school_name.setText("— Žádné nezavolané školy —")
            self.lbl_city.setText("Všechny školy přiřazené k tomuto volajícímu jsou vyřízené.")
            self.lbl_contact_person.setText("—")
            self.lbl_phone.setText("—")
            self.lbl_routing_badge.setVisible(False)
            self.btn_copy_phone.setVisible(False)
            self.lbl_email.setText("—")
            self.btn_edit_email.setVisible(False)
            self.lbl_organizer.setText("—")
            self.txt_history.setPlainText("V tabulce nejsou nalezeny žádné další nezavolané školy přiřazené k vašemu jménu v sloupci A.")
            return

        self._current_phone = school.phone or school.clean_phone
        self.lbl_school_name.setText(school.name)
        self.lbl_city.setText(f"Město: {school.city}" if school.city else "Město: neuvedeno")
        self.lbl_contact_person.setText(school.contact_person or "Neuvedena")
        self.lbl_phone.setText(school.phone or "Neuveden")
        self.btn_copy_phone.setVisible(bool(school.phone))
        self.lbl_email.setText(school.email or "Neuveden")
        self.btn_edit_email.setVisible(True)
        self.btn_edit_email.setText("✏️ Napsat adresu" if school.email else "➕ Napsat adresu")
        self.lbl_organizer.setText(school.caller if school.caller else "Volné (zatím nepřiřazeno)")
        self.txt_history.setPlainText(school.previous_notes or "Zatím žádná zaznamenaná historie.")

        self.lbl_routing_badge.setVisible(True)
        self._update_badge_style(is_slovak=school.is_slovak)
