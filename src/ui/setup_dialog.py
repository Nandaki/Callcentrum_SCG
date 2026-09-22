from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Set

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import AppConfig
from ..core.sheets import GoogleSheetsService, extract_spreadsheet_id
from .theme import (
    SCG_BLUE,
    SCG_DARK_BLUE,
    SCG_GREEN,
    SCG_RED,
    TEXT_ON_BLUE,
    TEXT_ON_DARK_BLUE,
    TEXT_ON_GREEN,
    TEXT_ON_RED,
)


class SheetsWorker(QObject):
    """Pracovní objekt pro provádění síťových požadavků ve vedlejším vlákně."""

    finished = Signal()
    error = Signal(str)
    auth_success = Signal(str)
    worksheets_loaded = Signal(list)
    headers_loaded = Signal(int, list)

    def __init__(self, service: GoogleSheetsService):
        super().__init__()
        self.service = service

    def _format_error(self, e: Exception) -> str:
        cause = e.__cause__ if getattr(e, "__cause__", None) else e
        msg = str(cause) if str(cause) else str(e)
        if "Google Sheets API has not been used" in msg or "is disabled" in msg:
            return (
                "⚠️ V Google Cloud projektu není aktivována Google Sheets API!\n\n"
                "Navštivte následující odkaz ve svém prohlížeči a klikněte na 'POVOLIT' (Enable):\n"
                "https://console.developers.google.com/apis/api/sheets.googleapis.com/overview\n\n"
                "Po povolení počkejte cca 30 sekund a zkuste načíst listy znovu."
            )
        if "The caller does not have permission" in msg or "403" in msg:
            return (
                "⚠️ Účet nemá oprávnění pro přístup k této tabulce (Chyba 403).\n"
                "Zkontrolujte, zda je tabulka nasdílená pro váš Google účet."
            )
        return msg or f"Chyba typu {type(e).__name__}"

    def do_authenticate(self) -> None:
        try:
            self.service.authenticate_interactive()
            email = self.service.get_user_email() or "Google účet autorizován"
            self.auth_success.emit(email)
        except Exception as e:
            self.error.emit(f"Chyba při přihlašování:\n{self._format_error(e)}")
        finally:
            self.finished.emit()

    def do_fetch_worksheets(self, spreadsheet_id: str) -> None:
        try:
            worksheets = self.service.get_worksheets(spreadsheet_id)
            self.worksheets_loaded.emit(worksheets)
        except Exception as e:
            self.error.emit(self._format_error(e))
        finally:
            self.finished.emit()

    def do_fetch_headers(self, spreadsheet_id: str, worksheet_name: str, header_row: int) -> None:
        try:
            row_num, headers = self.service.get_headers(spreadsheet_id, worksheet_name, header_row=header_row)
            self.headers_loaded.emit(row_num, headers)
        except Exception as e:
            self.error.emit(self._format_error(e))
        finally:
            self.finished.emit()


CARD_STYLE = f"""
    QGroupBox {{
        background-color: #ffffff;
        border: 1.5px solid #e2e8f0;
        border-radius: 12px;
        margin-top: 14px;
        padding: 22px 20px 20px 20px;
        font-size: 14px;
        font-weight: 800;
        color: {SCG_DARK_BLUE};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 16px;
        padding: 0 8px;
        background-color: #f8fafc;
        border-radius: 4px;
    }}
"""

INPUT_STYLE = """
    QLineEdit, QComboBox, QSpinBox {
        background-color: #ffffff;
        color: #1e293b;
        border: 1.5px solid #cbd5e1;
        border-radius: 8px;
        padding: 7px 12px;
        font-size: 13px;
        min-height: 24px;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
        border-color: #5d9be6;
        background-color: #ffffff;
    }
    QComboBox::drop-down {
        border: none;
        width: 24px;
    }
"""


class SetupDialog(QDialog):
    """Moderní, přehledný dialog pro nastavení Google OAuth a dynamické mapování sloupců shora dolů."""

    config_updated = Signal()

    def __init__(self, config: AppConfig, parent: QWidget | None = None):
        super().__init__(parent)
        self.config = config
        self.sheets_service = GoogleSheetsService(
            client_secret_path=config.oauth_client_secret_path,
            token_path=config.oauth_token_path,
        )
        self.detected_headers: List[str] = []
        self._active_threads: Set[QThread] = set()

        self.setWindowTitle("Nastavení propojení s Google Tabulkou")
        self.resize(800, 840)
        self.setMinimumSize(680, 600)
        self.setStyleSheet(f"background-color: #f8fafc; {INPUT_STYLE}")

        self._setup_ui()
        self._load_current_values()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # ----------------------------------------------------
        # Záhlaví dialogu
        # ----------------------------------------------------
        header_box = QVBoxLayout()
        header_box.setSpacing(4)
        lbl_title = QLabel("⚙️ Nastavení Google Tabulky a účtu")
        lbl_title.setStyleSheet(f"font-size: 20px; font-weight: 900; color: {SCG_DARK_BLUE};")
        header_box.addWidget(lbl_title)

        lbl_subtitle = QLabel("Kroky 1 až 4 vás postupně provedou připojením k databázi škol pro kampaň.")
        lbl_subtitle.setStyleSheet("font-size: 13px; color: #64748b;")
        header_box.addWidget(lbl_subtitle)
        main_layout.addLayout(header_box)

        # ----------------------------------------------------
        # Posuvná oblast (přehledná shora dolů)
        # ----------------------------------------------------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; }")

        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(4, 4, 14, 4)
        layout.setSpacing(20)

        # ----------------------------------------------------
        # KROK 1: Google OAuth Přihlášení
        # ----------------------------------------------------
        group_auth = QGroupBox("Krok 1: Přihlášení přes Google účet (OAuth 2.0)")
        group_auth.setStyleSheet(CARD_STYLE)
        auth_layout = QVBoxLayout(group_auth)
        auth_layout.setSpacing(14)

        lbl_auth_desc = QLabel(
            "Pro čtení kontaktů a zápis výsledků hovorů je potřeba povolit přístup k vašemu Google účtu."
        )
        lbl_auth_desc.setStyleSheet("font-size: 12px; color: #475569; font-weight: normal;")
        auth_layout.addWidget(lbl_auth_desc)

        # Indikátor stavu
        status_box = QHBoxLayout()
        lbl_auth_title = QLabel("Aktuální stav účtu:")
        lbl_auth_title.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {SCG_DARK_BLUE};")
        self.lbl_auth_status = QLabel("Zjišťuji stav...")
        self.lbl_auth_status.setStyleSheet(
            "font-size: 12px; font-weight: 800; padding: 4px 12px; border-radius: 6px; background-color: #f1f5f9; color: #64748b;"
        )
        status_box.addWidget(lbl_auth_title)
        status_box.addWidget(self.lbl_auth_status)
        status_box.addStretch()
        auth_layout.addLayout(status_box)

        # Tlačítko přihlášení
        self.btn_login = QPushButton("🔑  Přihlásit se přes Google účet (otevře prohlížeč)")
        self.btn_login.setFixedHeight(42)
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.setStyleSheet(f"""
            QPushButton {{
                background-color: {SCG_BLUE};
                color: {TEXT_ON_BLUE};
                font-weight: 800;
                font-size: 13px;
                border-radius: 8px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #4a8cd9;
            }}
        """)
        self.btn_login.clicked.connect(self._run_google_login)
        auth_layout.addWidget(self.btn_login)

        # Soubor credentials.json (klidně dole v rámečku)
        lbl_creds = QLabel("Cesta ke konfiguračnímu souboru Google credentials.json:")
        lbl_creds.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748b; margin-top: 4px;")
        auth_layout.addWidget(lbl_creds)

        file_box = QHBoxLayout()
        file_box.setSpacing(10)
        self.txt_creds_path = QLineEdit(self.config.oauth_client_secret_path)
        self.txt_creds_path.setPlaceholderText("Cesta k credentials.json...")
        btn_browse_creds = QPushButton("📁 Procházet...")
        btn_browse_creds.setFixedHeight(36)
        btn_browse_creds.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browse_creds.setStyleSheet(f"""
            QPushButton {{
                background-color: #ffffff;
                color: {SCG_DARK_BLUE};
                font-weight: bold;
                border: 1.5px solid #cbd5e1;
                border-radius: 8px;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                border-color: {SCG_BLUE};
                background-color: #f1f5f9;
            }}
        """)
        btn_browse_creds.clicked.connect(self._browse_credentials)
        file_box.addWidget(self.txt_creds_path, stretch=1)
        file_box.addWidget(btn_browse_creds)
        auth_layout.addLayout(file_box)

        layout.addWidget(group_auth)

        # ----------------------------------------------------
        # KROK 2: Google Tabulka a Načtení listů
        # ----------------------------------------------------
        group_sheet = QGroupBox("Krok 2: Odkaz na Google Tabulku")
        group_sheet.setStyleSheet(CARD_STYLE)
        sheet_layout = QVBoxLayout(group_sheet)
        sheet_layout.setSpacing(14)

        lbl_url_desc = QLabel("Vložte celý odkaz (URL) na tabulku ze svého prohlížeče nebo její ID:")
        lbl_url_desc.setStyleSheet("font-size: 12px; color: #475569; font-weight: normal;")
        sheet_layout.addWidget(lbl_url_desc)

        self.txt_sheet_url = QLineEdit()
        self.txt_sheet_url.setFixedHeight(40)
        self.txt_sheet_url.setPlaceholderText("https://docs.google.com/spreadsheets/d/1SUyIkJLNTTgaDjgn3TmyMoU4ipZRfPCwo0Gs-gXz4-Y/edit...")
        sheet_layout.addWidget(self.txt_sheet_url)

        self.btn_load_worksheets = QPushButton("🔍  Načíst sešit a seznam listů")
        self.btn_load_worksheets.setFixedHeight(42)
        self.btn_load_worksheets.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_load_worksheets.setStyleSheet(f"""
            QPushButton {{
                background-color: {SCG_DARK_BLUE};
                color: {TEXT_ON_DARK_BLUE};
                font-weight: 800;
                font-size: 13px;
                border-radius: 8px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #282766;
            }}
        """)
        self.btn_load_worksheets.clicked.connect(self._fetch_worksheets)
        sheet_layout.addWidget(self.btn_load_worksheets)

        # Zpráva o stavu tabulky
        self.lbl_sheet_msg = QLabel("")
        self.lbl_sheet_msg.setStyleSheet("font-size: 12px; font-weight: 700; color: #0284c7; padding: 2px 0;")
        sheet_layout.addWidget(self.lbl_sheet_msg)

        layout.addWidget(group_sheet)

        # ----------------------------------------------------
        # KROK 3: Výběr listu a řádku se záhlavím
        # ----------------------------------------------------
        group_ws = QGroupBox("Krok 3: Výběr listu a řádku se záhlavím")
        group_ws.setStyleSheet(CARD_STYLE)
        ws_layout = QVBoxLayout(group_ws)
        ws_layout.setSpacing(14)

        lbl_step3_desc = QLabel(
            "Vyberte list (např. <b>CZ SŠ</b> nebo <b>CZ ZŠ</b>) a zadejte číslo řádku, kde začínají názvy sloupců.<br>"
            "<i>V tabulkách SCG je záhlaví operátora obvykle na řádku 11.</i>"
        )
        lbl_step3_desc.setStyleSheet("font-size: 12px; color: #475569; line-height: 1.4; font-weight: normal;")
        ws_layout.addWidget(lbl_step3_desc)

        step3_form = QFormLayout()
        step3_form.setSpacing(12)

        lbl_ws = QLabel("List (sešit):")
        lbl_ws.setStyleSheet(f"font-weight: 800; color: {SCG_DARK_BLUE}; font-size: 13px;")
        self.cmb_worksheets = QComboBox()
        self.cmb_worksheets.setFixedHeight(38)
        step3_form.addRow(lbl_ws, self.cmb_worksheets)

        lbl_header_row = QLabel("Řádek se záhlavím:")
        lbl_header_row.setStyleSheet(f"font-weight: 800; color: {SCG_DARK_BLUE}; font-size: 13px;")
        self.spn_header_row = QSpinBox()
        self.spn_header_row.setFixedHeight(38)
        self.spn_header_row.setRange(1, 100)
        self.spn_header_row.setValue(self.config.header_row or 11)
        step3_form.addRow(lbl_header_row, self.spn_header_row)

        ws_layout.addLayout(step3_form)

        self.btn_load_columns = QPushButton("📋  Načíst sloupce z vybraného listu")
        self.btn_load_columns.setFixedHeight(42)
        self.btn_load_columns.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_load_columns.setStyleSheet(f"""
            QPushButton {{
                background-color: {SCG_BLUE};
                color: {TEXT_ON_BLUE};
                font-weight: 800;
                font-size: 13px;
                border-radius: 8px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #4a8cd9;
            }}
        """)
        self.btn_load_columns.clicked.connect(self._fetch_headers)
        ws_layout.addWidget(self.btn_load_columns)

        layout.addWidget(group_ws)

        # ----------------------------------------------------
        # KROK 4: Dynamické mapování sloupců
        # ----------------------------------------------------
        group_mapping = QGroupBox("Krok 4: Propojení sloupců tabulky s aplikací")
        group_mapping.setStyleSheet(CARD_STYLE)
        mapping_vbox = QVBoxLayout(group_mapping)
        mapping_vbox.setSpacing(14)

        lbl_map_desc = QLabel(
            "Zkontrolujte, zda sloupce v tabulce odpovídají údajům v aplikaci.<br>"
            "Sloupce <b>Název školy</b> a <b>Telefon</b> jsou povinné (*)."
        )
        lbl_map_desc.setStyleSheet("font-size: 12px; color: #475569; line-height: 1.4; font-weight: normal;")
        mapping_vbox.addWidget(lbl_map_desc)

        self.mapping_form = QFormLayout()
        self.mapping_form.setSpacing(12)
        self.mapping_form.setContentsMargins(0, 4, 0, 4)

        self.combos: Dict[str, QComboBox] = {}
        fields = [
            ("name", "🏫 Název školy (*):"),
            ("phone", "📞 Telefon školy (*):"),
            ("city", "📍 Město / Adresa:"),
            ("contact_person", "👤 Kontaktní osoba:"),
            ("email", "✉️ E-mail školy:"),
            ("previous_notes", "📝 Historie a poznámky k hovoru:"),
            ("status", "📊 Sloupec pro Zápis výsledku hovoru:"),
            ("operator_note", "✍️ Sloupec pro Zápis nové poznámky:"),
            ("timestamp", "⏱️ Sloupec pro Zápis času volání:"),
        ]

        for key, label_text in fields:
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"font-weight: 700; color: {SCG_DARK_BLUE}; font-size: 13px;")
            combo = QComboBox()
            combo.setFixedHeight(36)
            combo.addItem("— Nevybráno —", "")
            self.combos[key] = combo
            self.mapping_form.addRow(lbl, combo)

        mapping_vbox.addLayout(self.mapping_form)
        layout.addWidget(group_mapping)

        # Indikátor průběhu
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll, stretch=1)

        # ----------------------------------------------------
        # Spodní akční lišta
        # ----------------------------------------------------
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("border-color: #e2e8f0;")
        main_layout.addWidget(sep)

        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(12)

        btn_cancel = QPushButton("Zrušit / Zavřít")
        btn_cancel.setFixedHeight(44)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #475569;
                font-weight: bold;
                border: 1.5px solid #cbd5e1;
                border-radius: 8px;
                padding: 0 18px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                border-color: #94a3b8;
            }
        """)
        btn_cancel.clicked.connect(self.reject)

        self.btn_save = QPushButton("💾  Uložit nastavení a synchronizovat data")
        self.btn_save.setFixedHeight(44)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {SCG_DARK_BLUE};
                color: {TEXT_ON_DARK_BLUE};
                font-weight: 800;
                font-size: 14px;
                border-radius: 8px;
                border: none;
                padding: 0 24px;
            }}
            QPushButton:hover {{
                background-color: #282766;
            }}
        """)
        self.btn_save.clicked.connect(self._save_settings)

        btn_bar.addStretch()
        btn_bar.addWidget(btn_cancel)
        btn_bar.addWidget(self.btn_save)
        main_layout.addLayout(btn_bar)

        self._update_auth_ui()

    def _browse_credentials(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Vyberte credentials.json z Google Cloud Console",
            str(Path.home()),
            "JSON soubory (*.json);;Všechny soubory (*)",
        )
        if path:
            self.txt_creds_path.setText(path)
            self.sheets_service.client_secret_path = Path(path)
            self._update_auth_ui()

    def _update_auth_ui(self) -> None:
        if self.sheets_service.is_authenticated():
            email = self.sheets_service.get_user_email() or "Token aktivní"
            self.lbl_auth_status.setText(f"🟢 Přihlášen: {email}")
            self.lbl_auth_status.setStyleSheet(
                "font-size: 12px; font-weight: 800; padding: 4px 12px; border-radius: 6px; background-color: #eefbf6; color: #059669; border: 1px solid #5dd0a6;"
            )
            self.btn_login.setText("🔄  Znovu autorizovat Google účet")
        else:
            self.lbl_auth_status.setText("🔴 Nepřihlášen (vyžadována autorizace)")
            self.lbl_auth_status.setStyleSheet(
                "font-size: 12px; font-weight: 800; padding: 4px 12px; border-radius: 6px; background-color: #fef2f2; color: #dc2626; border: 1px solid #fca5a5;"
            )
            self.btn_login.setText("🔑  Přihlásit se přes Google účet (otevře prohlížeč)")

    def _load_current_values(self) -> None:
        self.txt_sheet_url.setText(self.config.google_sheet_url or self.config.google_sheet_id)
        if self.config.worksheet_name:
            self.cmb_worksheets.addItem(self.config.worksheet_name)
            self.cmb_worksheets.setCurrentText(self.config.worksheet_name)
        if self.config.header_row:
            self.spn_header_row.setValue(self.config.header_row)

    def _start_worker(self, worker_action, on_success=None, on_error=None) -> tuple[QThread, SheetsWorker]:
        """Bezpečné spuštění operace ve vedlejším vlákně chráněné před předčasnou garbage collection."""
        self.progress_bar.setVisible(True)

        thread = QThread(self)
        worker = SheetsWorker(self.sheets_service)
        worker.moveToThread(thread)

        self._active_threads.add(thread)

        thread.started.connect(worker_action)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)

        def cleanup():
            self.progress_bar.setVisible(False)
            self._active_threads.discard(thread)

        thread.finished.connect(cleanup)
        thread.finished.connect(thread.deleteLater)

        if on_error:
            worker.error.connect(on_error)
        else:
            worker.error.connect(self._on_error)

        return thread, worker

    def _run_google_login(self) -> None:
        creds_path = self.txt_creds_path.text().strip()
        if not creds_path or not Path(creds_path).exists():
            QMessageBox.warning(
                self,
                "Chybí credentials.json",
                f"Soubor s OAuth údaji nebyl nalezen na cestě:\n{creds_path}\n\n"
                "Stáhněte si 'credentials.json' (OAuth Client ID - Desktop App) z Google Cloud Console.",
            )
            return

        self.sheets_service.client_secret_path = Path(creds_path)
        self.btn_login.setEnabled(False)

        thread, worker = self._start_worker(worker.do_authenticate)
        worker.auth_success.connect(self._on_auth_success)
        thread.finished.connect(lambda: self.btn_login.setEnabled(True))
        thread.start()

    def _on_auth_success(self, email: str) -> None:
        self._update_auth_ui()
        QMessageBox.information(self, "Úspěch", f"Google účet byl úspěšně připojen:\n{email}")

    def _fetch_worksheets(self) -> None:
        raw_url = self.txt_sheet_url.text().strip()
        sheet_id = extract_spreadsheet_id(raw_url)
        if not sheet_id:
            QMessageBox.warning(self, "Chyba", "Zadejte platný odkaz na Google tabulku nebo její ID.")
            return

        self.btn_load_worksheets.setEnabled(False)
        self.lbl_sheet_msg.setText("⏳ Stahuji seznam listů z tabulky...")

        thread, worker = self._start_worker(lambda: worker.do_fetch_worksheets(sheet_id))
        worker.worksheets_loaded.connect(self._on_worksheets_loaded)
        thread.finished.connect(lambda: self.btn_load_worksheets.setEnabled(True))
        thread.start()

    def _on_worksheets_loaded(self, sheets: List[str]) -> None:
        self.cmb_worksheets.clear()
        for s in sheets:
            self.cmb_worksheets.addItem(s)

        # Inteligentní předvýběr: pokud existuje uložený list, nebo 'CZ SŠ' či 'CZ ZŠ'
        preferred = self.config.worksheet_name or ("CZ SŠ" if "CZ SŠ" in sheets else "")
        if preferred and preferred in sheets:
            self.cmb_worksheets.setCurrentText(preferred)

        self.lbl_sheet_msg.setText(f"✅ Nalezeno {len(sheets)} listů. Přejděte ke Kroku 3.")
        self.lbl_sheet_msg.setStyleSheet("font-size: 12px; font-weight: bold; color: #059669;")

    def _fetch_headers(self) -> None:
        raw_url = self.txt_sheet_url.text().strip()
        sheet_id = extract_spreadsheet_id(raw_url)
        worksheet_name = self.cmb_worksheets.currentText().strip()
        header_row = self.spn_header_row.value()

        if not sheet_id or not worksheet_name:
            QMessageBox.warning(self, "Chyba", "Nejprve načtěte tabulku a vyberte list.")
            return

        self.btn_load_columns.setEnabled(False)
        self.lbl_sheet_msg.setText(f"⏳ Načítám sloupce z listu '{worksheet_name}' (řádek {header_row})...")

        thread, worker = self._start_worker(lambda: worker.do_fetch_headers(sheet_id, worksheet_name, header_row))
        worker.headers_loaded.connect(self._on_headers_loaded)
        thread.finished.connect(lambda: self.btn_load_columns.setEnabled(True))
        thread.start()

    def _on_headers_loaded(self, row_num: int, headers: List[str]) -> None:
        self.detected_headers = headers
        self.spn_header_row.setValue(row_num)

        saved_mapping = self.config.column_mapping or {}

        for key, combo in self.combos.items():
            combo.clear()
            combo.addItem("— Nevybráno —", "")
            for h in headers:
                combo.addItem(h, h)

            # Obnova předchozího uložení nebo inteligentní autodetekce
            target_val = saved_mapping.get(key)
            if target_val and target_val in headers:
                combo.setCurrentText(target_val)
            else:
                self._auto_detect_column(key, headers, combo)

        self.lbl_sheet_msg.setText(f"✅ Načteno {len(headers)} sloupců z řádku {row_num}. Zkontrolujte mapování níže v Kroku 4.")
        self.lbl_sheet_msg.setStyleSheet("font-size: 12px; font-weight: bold; color: #059669;")

    def _auto_detect_column(self, field_key: str, headers: List[str], combo: QComboBox) -> None:
        """Automaticky navrhne sloupec podle obvyklých názvů ve sloupcích."""
        keywords = {
            "name": ["nazev", "škola", "skola", "název školy"],
            "phone": ["telefon_skoly", "kontakt_telefon", "telefon", "mobil", "tel"],
            "city": ["mesto", "město", "obec", "adresa", "ulice"],
            "contact_person": ["kontakt_jmeno", "kontakt", "osoba", "jméno"],
            "email": ["email_skoly", "kontakt_email", "email", "e-mail"],
            "previous_notes": ["projekty_5let", "poznamka", "historie", "info"],
            "status": ["Stav", "stav", "výsledek", "status"],
            "operator_note": ["Poznámky", "poznámka", "nová poznámka"],
            "timestamp": ["Čas", "čas", "datum"],
        }
        candidates = keywords.get(field_key, [])
        for h in headers:
            h_lower = h.lower()
            if any(c.lower() == h_lower or c.lower() in h_lower for c in candidates):
                combo.setCurrentText(h)
                break

    def _on_error(self, err_msg: str) -> None:
        self.lbl_sheet_msg.setText("❌ Chyba při operaci.")
        self.lbl_sheet_msg.setStyleSheet("font-size: 12px; font-weight: bold; color: #dc2626;")
        QMessageBox.critical(self, "Chyba", err_msg)

    def _save_settings(self) -> None:
        raw_url = self.txt_sheet_url.text().strip()
        sheet_id = extract_spreadsheet_id(raw_url)
        worksheet_name = self.cmb_worksheets.currentText().strip()
        header_row = self.spn_header_row.value()

        name_col = self.combos["name"].currentText()
        phone_col = self.combos["phone"].currentText()

        if name_col == "— Nevybráno —" or phone_col == "— Nevybráno —":
            QMessageBox.warning(
                self,
                "Neúplné mapování",
                "Sloupce pro 'Název školy' a 'Telefon' jsou povinné pro fungování aplikace.",
            )
            return

        mapping: Dict[str, str] = {}
        for key, combo in self.combos.items():
            val = combo.currentText()
            mapping[key] = "" if val == "— Nevybráno —" else val

        self.config.oauth_client_secret_path = self.txt_creds_path.text().strip()
        self.config.google_sheet_url = raw_url
        self.config.google_sheet_id = sheet_id
        self.config.worksheet_name = worksheet_name
        self.config.header_row = header_row
        self.config.column_mapping = mapping
        self.config.save()

        self.config_updated.emit()
        self.accept()
