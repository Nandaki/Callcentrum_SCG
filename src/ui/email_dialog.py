from __future__ import annotations

import threading
from typing import Optional

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QImage, QTextDocument
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabBar,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..config import AppConfig
from ..core.mailer import EmailSender, is_valid_email
from ..models.school import SchoolContact
from .theme import theme_manager


class EmailComposerDialog(QDialog):
    """
    Moderní dialog pro náhled, úpravu a odeslání e-mailu škole.
    Umožňuje přepínání mezi věrným grafickým HTML náhledem (s barvami, odkazy a logy)
    a textovým editorem pro rychlé úpravy před odesláním.
    """

    email_sent = Signal(str, str)  # to_email, message_info
    email_address_updated = Signal(str, bool)  # new_email, sync_to_sheet

    def __init__(
        self,
        config: AppConfig,
        school: Optional[SchoolContact] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.config = config
        self.school = school
        self.mailer = EmailSender(config)

        self.setWindowTitle("Odeslat e-mail škole — SCG Call Centrum")
        self.resize(700, 680)
        self.setMinimumSize(580, 520)
        self.setStyleSheet(theme_manager.get_stylesheet())

        self._is_sending = False
        self._current_html = ""

        self._setup_ui()
        self._apply_theme()
        self._load_data()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        # 1. Záhlaví
        top_box = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        lbl_title = QLabel("✉️ Příprava e-mailu pro školu")
        lbl_title.setObjectName("dialogTitle")
        title_box.addWidget(lbl_title)

        school_title = self.school.name if self.school else "Ukázková škola"
        self.lbl_school = QLabel(f"Příjemce: <b>{school_title}</b>")
        self.lbl_school.setObjectName("dialogSubtitle")
        title_box.addWidget(self.lbl_school)
        top_box.addLayout(title_box)
        top_box.addStretch()
        layout.addLayout(top_box)

        # 2. Formulář: Adresa příjemce
        lbl_to = QLabel("KOMU (E-mailová adresa):")
        lbl_to.setObjectName("sectionKicker")
        layout.addWidget(lbl_to)

        to_row = QHBoxLayout()
        to_row.setSpacing(8)

        self.txt_to = QLineEdit()
        self.txt_to.setObjectName("txtEmailTo")
        self.txt_to.setFixedHeight(36)
        self.txt_to.setPlaceholderText("např. novak@skola.cz (nutno zadat pro odeslání)")
        to_row.addWidget(self.txt_to, stretch=1)

        self.btn_save_addr = QPushButton("💾 Uložit adresu")
        self.btn_save_addr.setObjectName("btnSaveAddr")
        self.btn_save_addr.setFixedHeight(36)
        self.btn_save_addr.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_addr.setToolTip("Uložit tuto e-mailovou adresu do karty školy a Google Tabulky")
        self.btn_save_addr.clicked.connect(self._on_save_address_clicked)
        to_row.addWidget(self.btn_save_addr)

        layout.addLayout(to_row)

        # 3. Formulář: Předmět
        lbl_subj = QLabel("PŘEDMĚT ZPRÁVY:")
        lbl_subj.setObjectName("sectionKicker")
        layout.addWidget(lbl_subj)

        self.txt_subject = QLineEdit()
        self.txt_subject.setObjectName("txtEmailSubject")
        self.txt_subject.setFixedHeight(36)
        layout.addWidget(self.txt_subject)

        # 4. Záložky: HTML Náhled (Design) a Textové úpravy
        lbl_body_kicker = QLabel("OBSAH ZPRÁVY (DESIGN & TEXT):")
        lbl_body_kicker.setObjectName("sectionKicker")
        layout.addWidget(lbl_body_kicker)

        self.tabs_content = QTabWidget()
        self.tabs_content.setObjectName("emailTabs")

        # Tab 1: Věrný HTML náhled s designem
        self.browser_preview = QTextBrowser()
        self.browser_preview.setObjectName("browserEmailPreview")
        self.browser_preview.setOpenExternalLinks(True)
        self._register_preview_resources()
        self.tabs_content.addTab(self.browser_preview, "🎨  Grafický náhled (HTML design)")

        # Tab 2: Textové úpravy
        self.txt_body = QTextEdit()
        self.txt_body.setObjectName("txtEmailBody")
        self.txt_body.setAcceptRichText(False)
        self.txt_body.textChanged.connect(self._on_text_body_changed)
        self.tabs_content.addTab(self.txt_body, "✏️  Text zprávy (Editace)")

        layout.addWidget(self.tabs_content, stretch=1)

        # 5. Stavový řádek a progress bar
        self.lbl_status = QLabel("")
        self.lbl_status.setObjectName("lblEmailStatus")
        layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 6. Akční tlačítka
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)

        self.btn_close = QPushButton("Zavřít")
        self.btn_close.setObjectName("btnSecondary")
        self.btn_close.setFixedHeight(40)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self.reject)
        btn_bar.addWidget(self.btn_close)

        btn_bar.addStretch()

        self.btn_open_client = QPushButton("🌐 Otevřít v poštovním klientovi")
        self.btn_open_client.setObjectName("btnMailto")
        self.btn_open_client.setFixedHeight(40)
        self.btn_open_client.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_client.setToolTip("Otevře zprávu ve vašem výchozím e-mailovém programu (Thunderbird, Outlook apod.)")
        self.btn_open_client.clicked.connect(self._on_open_client_clicked)
        btn_bar.addWidget(self.btn_open_client)

        self.btn_send_smtp = QPushButton("🚀 Odeslat e-mail s designem (SMTP)")
        self.btn_send_smtp.setObjectName("btnSendPrimary")
        self.btn_send_smtp.setFixedHeight(40)
        self.btn_send_smtp.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send_smtp.setToolTip(f"Odeslat přímo přes SMTP účet ({self.config.smtp_user})")
        self.btn_send_smtp.clicked.connect(self._on_send_smtp_clicked)
        btn_bar.addWidget(self.btn_send_smtp)

        layout.addLayout(btn_bar)

    def _register_preview_resources(self) -> None:
        """Zaregistruje ikony sociálních sítí do QTextDocument pod CID schématem."""
        doc = self.browser_preview.document()
        assets_dir = self.mailer.get_assets_dir()
        icon_map = {
            "icon_web": "icon_web.png",
            "icon_instagram": "icon_instagram.png",
            "icon_facebook": "icon_facebook.png",
        }
        for cid, fn in icon_map.items():
            p = assets_dir / fn
            if p.exists():
                img = QImage(str(p))
                doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl(f"cid:{cid}"), img)

    def _apply_theme(self) -> None:
        t = theme_manager.tokens
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {t.bg_card};
                border: 1px solid {t.border_card};
                border-radius: 10px;
            }}
            QLabel#dialogTitle {{
                font-size: 17px;
                font-weight: 800;
                color: {t.text_primary};
            }}
            QLabel#dialogSubtitle {{
                font-size: 13px;
                color: {t.accent_blue};
            }}
            QLabel#sectionKicker {{
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
                color: {t.text_muted};
            }}
            QLineEdit#txtEmailTo, QLineEdit#txtEmailSubject {{
                background-color: {t.bg_card_secondary};
                color: {t.text_primary};
                border: 1px solid {t.border_subtle};
                border-radius: 6px;
                padding: 0 12px;
                font-size: 13px;
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border-color: {t.accent_blue};
            }}
            QTabWidget#emailTabs::pane {{
                border: 1px solid {t.border_subtle};
                border-radius: 6px;
                background-color: {t.bg_card_secondary};
            }}
            QTabBar::tab {{
                padding: 8px 14px;
                font-weight: 600;
                font-size: 12px;
                color: {t.text_secondary};
                background: {t.bg_card};
                border: 1px solid {t.border_subtle};
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
            }}
            QTabBar::tab:selected {{
                color: {t.text_primary};
                background: {t.bg_card_secondary};
                font-weight: 700;
            }}
            QTextBrowser#browserEmailPreview {{
                background-color: #ffffff;
                color: #222222;
                border: none;
                border-radius: 6px;
                padding: 16px;
                font-size: 13px;
            }}
            QTextEdit#txtEmailBody {{
                background-color: {t.bg_card_secondary};
                color: {t.text_primary};
                border: none;
                border-radius: 6px;
                padding: 12px;
                font-size: 13px;
                line-height: 1.4;
            }}
            QPushButton#btnSaveAddr {{
                background-color: {t.bg_card_secondary};
                color: {t.text_primary};
                border: 1px solid {t.border_subtle};
                border-radius: 6px;
                padding: 0 12px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton#btnSaveAddr:hover {{
                border-color: {t.accent_blue};
                color: {t.accent_blue};
            }}
            QPushButton#btnSecondary {{
                background-color: {t.btn_secondary_bg};
                color: {t.btn_secondary_text};
                border: 1px solid {t.border_subtle};
                border-radius: 6px;
                padding: 0 16px;
                font-weight: 600;
            }}
            QPushButton#btnMailto {{
                background-color: {t.bg_card_secondary};
                color: {t.text_primary};
                border: 1px solid {t.border_subtle};
                border-radius: 6px;
                padding: 0 16px;
                font-weight: 600;
            }}
            QPushButton#btnMailto:hover {{
                border-color: {t.accent_blue};
            }}
            QPushButton#btnSendPrimary {{
                background-color: {t.btn_primary_bg};
                color: {t.btn_primary_text};
                border: none;
                border-radius: 6px;
                padding: 0 20px;
                font-weight: 700;
                font-size: 13px;
            }}
            QPushButton#btnSendPrimary:hover {{
                background-color: {t.btn_primary_hover};
            }}
            QLabel#lblEmailStatus {{
                font-size: 12px;
                font-weight: 600;
            }}
        """)

    def _load_data(self) -> None:
        """Předvyplní formulář údaji o škole a šablonou."""
        cur_email = (self.school.email if self.school else "").strip()
        self.txt_to.setText(cur_email)

        subject = self.mailer.format_template(
            self.config.email_subject_template or "Pojďte se zapojit do pIšQworek",
            self.school,
            self.config.operator_name,
        )
        self.txt_subject.setText(subject)

        # Načteme HTML šablonu s designem
        raw_html = self.mailer.get_html_template()
        self._current_html = self.mailer.format_template(raw_html, self.school, self.config.operator_name)
        self.browser_preview.setHtml(self._current_html)

        # Načteme i textovou verzi
        plain_text = self.mailer.format_template(
            self.config.email_body_template or "",
            self.school,
            self.config.operator_name,
        )
        self.txt_body.blockSignals(True)
        self.txt_body.setText(plain_text)
        self.txt_body.blockSignals(False)

        if not cur_email:
            self._set_status("⚠️ Tato škola zatím nemá zadanou e-mailovou adresu. Zadejte ji výše.", is_error=True)
            self.txt_to.setFocus()
        else:
            self._set_status(f"Připraveno k odeslání z účtu {self.config.smtp_user or 'SMTP'}.", is_error=False)

    def _on_text_body_changed(self) -> None:
        """Pokud uživatel upraví plain text v záložce editace, aktualizujeme stav."""
        # Ponecháváme HTML náhled s designem
        pass

    def _set_status(self, msg: str, is_error: bool = False, is_success: bool = False) -> None:
        t = theme_manager.tokens
        self.lbl_status.setText(msg)
        if is_error:
            self.lbl_status.setStyleSheet(f"color: {t.accent_red};")
        elif is_success:
            self.lbl_status.setStyleSheet(f"color: {t.accent_green_text};")
        else:
            self.lbl_status.setStyleSheet(f"color: {t.text_secondary};")

    def _on_save_address_clicked(self) -> None:
        addr = self.txt_to.text().strip()
        if not addr:
            QMessageBox.warning(self, "Chyba", "Zadejte e-mailovou adresu.")
            return

        if not is_valid_email(addr):
            reply = QMessageBox.question(
                self,
                "Upozornění",
                f"Adresa '{addr}' neodpovídá běžnému formátu e-mailu. Chcete ji přesto uložit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        can_sync = bool(self.school and self.school.row_index > 0)
        self.email_address_updated.emit(addr, can_sync)
        if self.school:
            self.school.email = addr
        self._set_status(f"Adresa '{addr}' uložena do karty školy{' a Google Tabulky' if can_sync else ''}.", is_success=True)

    def _on_open_client_clicked(self) -> None:
        addr = self.txt_to.text().strip()
        subject = self.txt_subject.text().strip()
        body = self.txt_body.toPlainText()

        ok, msg = self.mailer.open_in_mail_client(addr, subject, body)
        if ok:
            self._set_status(msg, is_success=True)
            if addr and self.school and self.school.email != addr:
                self.email_address_updated.emit(addr, self.school.row_index > 0)
                self.school.email = addr
            self.email_sent.emit(addr, "Otevřeno v klientovi")
        else:
            self._set_status(msg, is_error=True)
            QMessageBox.warning(self, "Chyba", msg)

    def _on_send_smtp_clicked(self) -> None:
        if self._is_sending:
            return

        addr = self.txt_to.text().strip()
        if not addr:
            self._set_status("Chyba: Zadejte e-mailovou adresu příjemce.", is_error=True)
            self.txt_to.setFocus()
            return

        if not is_valid_email(addr):
            QMessageBox.warning(self, "Chyba", f"'{addr}' není platná e-mailová adresa.")
            self.txt_to.setFocus()
            return

        subject = self.txt_subject.text().strip()
        body = self.txt_body.toPlainText()
        html_content = self._current_html

        self._is_sending = True
        self.progress_bar.setVisible(True)
        self.btn_send_smtp.setEnabled(False)
        self.btn_open_client.setEnabled(False)
        self._set_status(f"Odesílám formátovaný e-mail s designem na {addr} přes SMTP...")

        def send_task():
            ok, msg = self.mailer.send_email_smtp(
                to_email=addr,
                subject=subject,
                body=body,
                html_body=html_content,
            )
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._on_send_finished(ok, msg, addr))

        threading.Thread(target=send_task, daemon=True).start()

    def _on_send_finished(self, ok: bool, msg: str, to_addr: str) -> None:
        self._is_sending = False
        self.progress_bar.setVisible(False)
        self.btn_send_smtp.setEnabled(True)
        self.btn_open_client.setEnabled(True)

        if ok:
            self._set_status(msg, is_success=True)
            if self.school and self.school.email != to_addr:
                self.email_address_updated.emit(to_addr, self.school.row_index > 0)
                self.school.email = to_addr
            self.email_sent.emit(to_addr, msg)
            QMessageBox.information(self, "E-mail odeslán", f"E-mail s designem byl úspěšně doručen na:\n{to_addr}")
            self.accept()
        else:
            self._set_status("Chyba při odesílání e-mailu přes SMTP.", is_error=True)
            self._show_smtp_error_dialog(msg)

    def _show_smtp_error_dialog(self, error_details: str) -> None:
        """Zobrazí dialog s chybou a tlačítkem pro přímé vygenerování Hesla aplikace."""
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("Chyba odeslání přes Google SMTP")

        if "534" in error_details or "535" in error_details or "Heslo aplikace" in error_details:
            msg_box.setText("<h3>Google odmítl přihlášení (kód 534/535)</h3>")
            msg_box.setInformativeText(
                "Google pro účty (@scg.cz a @gmail.com) <b>zakázal</b> používat běžné přihlašovací heslo pro SMTP.<br><br>"
                "<b>Řešení:</b> V Google účtu si vygenerujte 16místné <b>Heslo aplikace</b>:<br>"
                "1. Klikněte níže na tlačítko <i>Otevřít generování hesla</i><br>"
                "2. Přihlaste se ke svému účtu Google<br>"
                "3. Zadejte název např. <code>Call Centrum</code> a klikněte na <b>Vytvořit</b><br>"
                "4. Zkopírujte vygenerované 16místné heslo a vložte ho v Nastavení aplikace do pole <i>Heslo aplikace (SMTP)</i>."
            )
            btn_open = msg_box.addButton("🔑 Otevřít generování hesla v prohlížeči", QMessageBox.ButtonRole.ActionRole)
            btn_cancel = msg_box.addButton("Zavřít", QMessageBox.ButtonRole.RejectRole)
            msg_box.exec()
            if msg_box.clickedButton() == btn_open:
                QDesktopServices.openUrl(QUrl("https://myaccount.google.com/apppasswords"))
        else:
            msg_box.setText("Odeslání e-mailu selhalo")
            msg_box.setInformativeText(error_details)
            msg_box.exec()
