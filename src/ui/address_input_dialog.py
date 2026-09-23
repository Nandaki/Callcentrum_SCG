from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.mailer import is_valid_email
from ..models.school import SchoolContact
from .theme import theme_manager


class AddressInputDialog(QDialog):
    """Moderní dialog pro rychlé zadání nebo úpravu e-mailové adresy školy."""

    def __init__(
        self,
        school: Optional[SchoolContact] = None,
        current_email: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.school = school
        self.initial_email = current_email or (school.email if school else "")
        self.result_email: str = ""
        self.sync_to_sheet: bool = True

        self.setWindowTitle("Zadat e-mailovou adresu — SCG Call Centrum")
        self.setFixedWidth(460)
        self.setModal(True)
        self.setStyleSheet(theme_manager.get_stylesheet())

        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        # Hlavička
        lbl_title = QLabel("✏️ Napsat e-mailovou adresu")
        lbl_title.setObjectName("dialogTitle")
        layout.addWidget(lbl_title)

        if self.school:
            lbl_school = QLabel(f"Pro: <b>{self.school.name}</b>")
            lbl_school.setObjectName("dialogSubtitle")
            lbl_school.setWordWrap(True)
            layout.addWidget(lbl_school)

        # Popisek a vstupní pole
        lbl_field = QLabel("E-mailová adresa školy nebo kontaktní osoby:")
        lbl_field.setObjectName("fieldLabel")
        layout.addWidget(lbl_field)

        self.txt_email = QLineEdit()
        self.txt_email.setObjectName("txtDialogEmail")
        self.txt_email.setFixedHeight(40)
        self.txt_email.setPlaceholderText("např. novakova@skola.cz nebo info@gymnazium.cz")
        self.txt_email.setText(self.initial_email)
        self.txt_email.selectAll()
        layout.addWidget(self.txt_email)

        # Checkbox pro okamžitou synchronizaci do tabulky
        can_sync = bool(self.school and self.school.row_index > 0)
        self.chk_sync_sheet = QCheckBox("Uložit přímo do sdílené Google Tabulky (sloupec E-mail)")
        self.chk_sync_sheet.setObjectName("chkSyncSheet")
        self.chk_sync_sheet.setChecked(can_sync)
        self.chk_sync_sheet.setEnabled(can_sync)
        layout.addWidget(self.chk_sync_sheet)

        # Spodní tlačítka
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        self.btn_cancel = QPushButton("Zrušit")
        self.btn_cancel.setObjectName("btnDialogCancel")
        self.btn_cancel.setFixedHeight(38)
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel, stretch=1)

        self.btn_save = QPushButton("Uložit adresu")
        self.btn_save.setObjectName("btnDialogSave")
        self.btn_save.setFixedHeight(38)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.clicked.connect(self._on_save_clicked)
        btn_box.addWidget(self.btn_save, stretch=2)

        layout.addLayout(btn_box)

    def _apply_theme(self) -> None:
        t = theme_manager.tokens
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {t.bg_card};
                border: 1px solid {t.border_card};
                border-radius: 10px;
            }}
            QLabel#dialogTitle {{
                font-size: 16px;
                font-weight: 800;
                color: {t.text_primary};
            }}
            QLabel#dialogSubtitle {{
                font-size: 13px;
                color: {t.accent_blue};
            }}
            QLabel#fieldLabel {{
                font-size: 12px;
                font-weight: 600;
                color: {t.text_secondary};
            }}
            QLineEdit#txtDialogEmail {{
                background-color: {t.bg_card_secondary};
                color: {t.text_primary};
                border: 1px solid {t.border_subtle};
                border-radius: 6px;
                padding: 0 12px;
                font-size: 14px;
            }}
            QLineEdit#txtDialogEmail:focus {{
                border-color: {t.accent_blue};
            }}
            QCheckBox#chkSyncSheet {{
                font-size: 12px;
                color: {t.text_secondary};
            }}
            QPushButton#btnDialogCancel {{
                background-color: {t.btn_secondary_bg};
                color: {t.btn_secondary_text};
                border: 1px solid {t.border_subtle};
                border-radius: 6px;
                font-weight: 600;
            }}
            QPushButton#btnDialogSave {{
                background-color: {t.btn_primary_bg};
                color: {t.btn_primary_text};
                border: none;
                border-radius: 6px;
                font-weight: 700;
                font-size: 13px;
            }}
            QPushButton#btnDialogSave:hover {{
                background-color: {t.btn_primary_hover};
            }}
        """)

    def _on_save_clicked(self) -> None:
        val = self.txt_email.text().strip()
        if not val:
            QMessageBox.warning(self, "Chyba", "Zadejte platnou e-mailovou adresu.")
            self.txt_email.setFocus()
            return

        if not is_valid_email(val):
            reply = QMessageBox.question(
                self,
                "Neobvyklý formát e-mailu",
                f"Zadaná adresa '{val}' nemá standardní formát (chybí @ nebo doména).\n\nPřejete si ji přesto uložit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self.txt_email.setFocus()
                return

        self.result_email = val
        self.sync_to_sheet = self.chk_sync_sheet.isChecked()
        self.accept()

    @classmethod
    def get_email(
        cls,
        school: Optional[SchoolContact] = None,
        current_email: str = "",
        parent: Optional[QWidget] = None,
    ) -> Tuple[Optional[str], bool]:
        """Statická pomocná metoda. Vrátí (nova_adresa, synchronizovat_do_tabulky)."""
        dlg = cls(school=school, current_email=current_email, parent=parent)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return dlg.result_email, dlg.sync_to_sheet
        return None, False
