from __future__ import annotations

from typing import List

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..config import AppConfig
from ..core.dialer import PhoneController
from ..core.sheets import GoogleSheetsService
from ..models.school import CallResult, CallState, SchoolContact
from .settings_dialog import GlobalSettingsDialog
from .theme import theme_manager
from .widgets.call_control import CallControlWidget
from .widgets.result_panel import ResultPanelWidget
from .widgets.school_card import SchoolCardWidget


class DialThread(QThread):
    """Vlákno pro spuštění vytáčení hovoru s emitováním výsledku (ok, msg) zpět do UI."""

    dial_result = Signal(bool, str)

    def __init__(self, phone_controller: PhoneController, school: SchoolContact, parent: QObject | None = None):
        super().__init__(parent)
        self.phone_controller = phone_controller
        self.school = school

    def run(self) -> None:
        try:
            print(f"[DialThread] Zahajuji vytáčení pro: {self.school.name} ({self.school.clean_phone})", flush=True)
            ok, msg = self.phone_controller.dial(self.school)
            print(f"[DialThread] Výsledek dial(): ok={ok}, msg={msg}", flush=True)
            self.dial_result.emit(ok, msg)
        except Exception as e:
            print(f"[DialThread] Výjimka: {e}", flush=True)
            self.dial_result.emit(False, f"Chyba při vytáčení: {e}")


class DataSyncWorker(QObject):
    """Pracovní vlákno pro asynchronní stahování kontaktů a zápis výsledků do Google Sheets."""

    contacts_loaded = Signal(list)
    result_saved = Signal(int)
    error = Signal(str)
    finished = Signal()

    def __init__(self, service: GoogleSheetsService):
        super().__init__()
        self.service = service

    def _format_error(self, e: Exception) -> str:
        cause = e.__cause__ if getattr(e, "__cause__", None) else e
        msg = str(cause) if str(cause) else str(e)
        if "Google Sheets API has not been used" in msg or "is disabled" in msg:
            return "V Google Cloud projektu není aktivována Google Sheets API! Povolte ji v Google Cloud Console."
        return msg or f"Chyba typu {type(e).__name__}"

    def load_contacts(self, sheet_id: str, worksheet_name: str, mapping: dict, header_row: int = 11) -> None:
        try:
            contacts = self.service.fetch_contacts(
                spreadsheet_id=sheet_id,
                worksheet_name=worksheet_name,
                column_mapping=mapping,
                header_row=header_row,
                only_uncalled=True,
            )
            self.contacts_loaded.emit(contacts)
        except Exception as e:
            self.error.emit(f"Chyba při stahování: {self._format_error(e)}")
        finally:
            self.finished.emit()

    def save_result(self, sheet_id: str, worksheet_name: str, row_index: int, mapping: dict, result: CallResult, header_row: int = 11) -> None:
        try:
            self.service.update_call_result(
                spreadsheet_id=sheet_id,
                worksheet_name=worksheet_name,
                row_index=row_index,
                column_mapping=mapping,
                result=result,
                header_row=header_row,
            )
            self.result_saved.emit(row_index)
        except Exception as e:
            self.error.emit(f"Chyba při zápisu do řádku {row_index}: {e}")
        finally:
            self.finished.emit()


DEFAULT_TEST_SCHOOL = SchoolContact(
    id="test-1",
    name="Gymnázium sv. honzíka",
    city="Praha",
    contact_person="Bára Švejdová",
    phone="+420733215027",
    email="svejdova@scg.cz",
    previous_notes="Prioritní testovací kontakt pro ověření volání, SMS a funkčnosti.",
    row_index=0,
)


class MainWindow(QMainWindow):
    """
    Hlavní okno aplikace Call Centrum ve stylu Linear.
    Navrženo pro Students Can Grow (SCG) s podporou Dark/Light mode a klávesové navigace.
    """

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.sheets_service = GoogleSheetsService(
            client_secret_path=config.oauth_client_secret_path,
            token_path=config.oauth_token_path,
        )
        self.phone_controller = PhoneController(self.config)

        self.setWindowTitle("Call Centrum — Students Can Grow")
        self.resize(1180, 760)
        self.setMinimumSize(980, 650)

        # Inicializace tématu z konfigurace
        theme_mode = getattr(self.config, "theme_mode", "dark") or "dark"
        theme_manager.set_theme(theme_mode)
        self.setStyleSheet(theme_manager.get_stylesheet())
        theme_manager.theme_changed.connect(self._on_theme_changed)

        self.schools_queue: List[SchoolContact] = [DEFAULT_TEST_SCHOOL]
        self.current_school_idx = 0
        self._active_threads = set()
        self._dial_thread = None

        self._setup_ui()
        self._setup_shortcuts()
        self._apply_theme_ui()
        self._display_current_school()
        self._update_device_status()
        self._auto_load_data()

    def _setup_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(18, 14, 18, 14)
        root_layout.setSpacing(12)

        # ----------------------------------------------------
        # 1. Horní informační a ovládací lišta (Linear style)
        # ----------------------------------------------------
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        # Logo / Brand
        self.lbl_app_title = QLabel("SCG Call Centrum")
        self.lbl_app_title.setObjectName("appTitle")
        top_bar.addWidget(self.lbl_app_title)

        top_bar.addSpacing(6)

        # Počítadlo školy ve frontě (monospace kbd styl)
        self.lbl_queue_counter = QLabel("0 / 0")
        self.lbl_queue_counter.setObjectName("queueBadge")
        top_bar.addWidget(self.lbl_queue_counter)

        # Indikátor Google Sheets
        self.lbl_sheet_status = QLabel("● Google Sheets: Zjišťuji...")
        self.lbl_sheet_status.setObjectName("sheetStatusPill")
        self.lbl_sheet_status.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_sheet_status.setToolTip("Kliknutím otevřete nastavení Google Tabulky")
        self.lbl_sheet_status.mousePressEvent = lambda ev: self._open_global_settings(0)
        top_bar.addWidget(self.lbl_sheet_status)

        top_bar.addStretch()

        # Tlačítko Obnovit
        self.btn_refresh = QPushButton("Obnovit")
        self.btn_refresh.setObjectName("btnTopAction")
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.clicked.connect(self._auto_load_data)
        top_bar.addWidget(self.btn_refresh)

        # Přepínač témat (Dark / Light)
        self.btn_theme_toggle = QPushButton("🌙 Tmavý" if theme_manager.mode == "dark" else "☀️ Světlý")
        self.btn_theme_toggle.setObjectName("btnThemeToggle")
        self.btn_theme_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme_toggle.setToolTip("Přepnout mezi tmavým a světlým režimem")
        self.btn_theme_toggle.clicked.connect(self._toggle_theme)
        top_bar.addWidget(self.btn_theme_toggle)

        # Tlačítko Globální nastavení
        self.btn_settings = QPushButton("⚙ Nastavení")
        self.btn_settings.setObjectName("btnTopAction")
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.setToolTip("Otevřít globální nastavení tabulky, telefonu, SMS a integrací")
        self.btn_settings.clicked.connect(lambda: self._open_global_settings(0))
        top_bar.addWidget(self.btn_settings)

        # Indikátor telefonu / ADB
        device_name = self.config.kdeconnect_device_name or "Galaxy S24 Ultra"
        self.lbl_device = QLabel(f"● {device_name}")
        self.lbl_device.setObjectName("deviceStatusPill")
        self.lbl_device.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_device.setToolTip("Kliknutím otevřete nastavení telefonu a Wi-Fi ADB")
        self.lbl_device.mousePressEvent = lambda ev: self._open_global_settings(1)
        top_bar.addWidget(self.lbl_device)

        root_layout.addLayout(top_bar)

        # ----------------------------------------------------
        # 2. Hlavní rozdělení (Levý sloupec: Karta školy, Pravý: Řízení + Zápis)
        # ----------------------------------------------------
        content_layout = QHBoxLayout()
        content_layout.setSpacing(14)

        # Levá část: Karta školy
        self.school_card = SchoolCardWidget(self)
        content_layout.addWidget(self.school_card, stretch=5)

        # Pravá část: Řízení hovoru & Zápis výsledku
        right_panel = QVBoxLayout()
        right_panel.setSpacing(12)

        self.call_control = CallControlWidget(timeout_seconds=self.config.call_timeout_seconds, parent=self)
        right_panel.addWidget(self.call_control)

        self.result_panel = ResultPanelWidget(self)
        right_panel.addWidget(self.result_panel)

        content_layout.addLayout(right_panel, stretch=4)
        root_layout.addLayout(content_layout)

        # Propojení signálů hovoru
        self.call_control.call_requested.connect(self._on_call_started)
        self.call_control.connected_requested.connect(self._on_call_connected)
        self.call_control.hangup_requested.connect(self._on_call_hangup)
        self.call_control.timeout_reached.connect(self._on_call_timeout)

        self.result_panel.result_submitted.connect(self._on_result_submitted)
        self.result_panel.send_sms_requested.connect(self._on_send_sms_requested)

        # 3. Stavová lišta
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Aplikace připravena")

    def _setup_shortcuts(self) -> None:
        """Ergonomické klávesové zkratky bez kolizí s textovými poli."""
        # Mezerník: Volat / Spojeno
        self.shortcut_space = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        self.shortcut_space.activated.connect(self._handle_space_shortcut)

        # Escape: Zavěsit
        self.shortcut_esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.shortcut_esc.activated.connect(self._handle_esc_shortcut)

        # Čísla 1–5: Výsledek hovoru
        for i in range(1, 6):
            key_str = str(i)
            sc = QShortcut(QKeySequence(getattr(Qt.Key, f"Key_{key_str}")), self)
            sc.activated.connect(lambda k=key_str: self._handle_number_shortcut(k))

        # Enter / Return: Uložit výsledek
        self.shortcut_enter = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        self.shortcut_enter.activated.connect(self._handle_enter_shortcut)

        # Klávesa S: Odeslání SMS přes ADB
        self.shortcut_s = QShortcut(QKeySequence(Qt.Key.Key_S), self)
        self.shortcut_s.activated.connect(self._handle_s_shortcut)

    def _is_typing(self) -> bool:
        """Vrátí True, pokud je aktivní textové pole (pro ochranu před přepsáním kláves)."""
        focused = self.focusWidget()
        return isinstance(focused, (QTextEdit, QLineEdit))

    def _handle_space_shortcut(self) -> None:
        if self._is_typing():
            return

        if self.call_control.state == CallState.IDLE:
            self.call_control._on_call_clicked()
        elif self.call_control.state == CallState.DIALING:
            self.call_control._on_connected_clicked()

    def _handle_esc_shortcut(self) -> None:
        if self.call_control.state in (CallState.DIALING, CallState.CONNECTED):
            self.call_control._on_hangup_clicked()

    def _handle_number_shortcut(self, key_str: str) -> None:
        if self._is_typing():
            return
        self.result_panel.select_outcome_by_key(key_str)

    def _handle_enter_shortcut(self) -> None:
        if self._is_typing():
            return
        self.result_panel._on_submit_clicked()

    def _handle_s_shortcut(self) -> None:
        if self._is_typing():
            return
        self.result_panel._on_send_sms_clicked()

    def _toggle_theme(self) -> str:
        new_mode = theme_manager.toggle_theme()
        self.config.theme_mode = new_mode
        self.config.save()
        self.btn_theme_toggle.setText("🌙 Tmavý" if new_mode == "dark" else "☀️ Světlý")
        return new_mode

    def _on_theme_changed(self, mode: str) -> None:
        app = QApplication.instance()
        if app:
            app.setStyleSheet(theme_manager.get_stylesheet())
        else:
            self.setStyleSheet(theme_manager.get_stylesheet())
        self._apply_theme_ui()

    def _apply_theme_ui(self) -> None:
        t = theme_manager.tokens

        self.lbl_app_title.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 800;
            letter-spacing: -0.3px;
            color: {t.text_primary};
        """)

        self.lbl_queue_counter.setStyleSheet(f"""
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 12px;
            font-weight: 700;
            background-color: {t.bg_card};
            color: {t.text_secondary};
            border: 1px solid {t.border_subtle};
            padding: 4px 10px;
            border-radius: 6px;
        """)

        btn_style = f"""
            QPushButton {{
                background-color: {t.bg_card};
                color: {t.text_primary};
                font-size: 12px;
                font-weight: 600;
                border: 1px solid {t.border_subtle};
                border-radius: 6px;
                padding: 5px 12px;
            }}
            QPushButton:hover {{
                background-color: {t.bg_hover};
                border-color: {t.border_focus};
            }}
        """
        self.btn_refresh.setStyleSheet(btn_style)
        self.btn_theme_toggle.setStyleSheet(btn_style)
        self.btn_settings.setStyleSheet(btn_style)

    def _open_global_settings(self, initial_tab: int = 0) -> None:
        dialog = GlobalSettingsDialog(self.config, self.phone_controller, initial_tab=initial_tab, parent=self)
        dialog.config_updated.connect(self._on_config_updated)
        dialog.exec()
        self._update_device_status()

    def _on_config_updated(self) -> None:
        self.status_bar.showMessage("Konfigurace aplikace byla aktualizována.")
        self.call_control.timeout_seconds = self.config.call_timeout_seconds
        self.call_control.remaining_seconds = self.config.call_timeout_seconds
        self.call_control._update_timer_display()
        self._update_device_status()
        self._auto_load_data()

    def _auto_load_data(self) -> None:
        """Pokusí se načíst data z Google Sheets, případně přepne na ukázková mock data."""
        t = theme_manager.tokens
        mapping = self.config.column_mapping or {}
        has_sheet = bool(self.config.google_sheet_id and self.config.worksheet_name and mapping.get("name"))

        if has_sheet and self.sheets_service.is_authenticated():
            self.lbl_sheet_status.setText(f"● Google Sheets: {self.config.worksheet_name} (načítám...)")
            self.lbl_sheet_status.setStyleSheet(f"""
                font-size: 12px;
                font-weight: 600;
                color: {t.accent_blue};
                background-color: {t.accent_blue_subtle};
                border: 1px solid {t.accent_blue};
                padding: 4px 10px;
                border-radius: 6px;
            """)
            self.status_bar.showMessage(f"Stahuji řádky z listu '{self.config.worksheet_name}'...")
            self._load_live_contacts()
        else:
            self.lbl_sheet_status.setText("● Google Sheets: Nepřipojeno")
            self.lbl_sheet_status.setStyleSheet(f"""
                font-size: 12px;
                font-weight: 600;
                color: {t.text_muted};
                background-color: {t.bg_card};
                border: 1px solid {t.border_subtle};
                padding: 4px 10px;
                border-radius: 6px;
            """)
            self._load_mock_schools()

    def _load_live_contacts(self) -> None:
        """Načte živé kontakty z Google tabulky na pozadí."""
        thread = QThread(self)
        worker = DataSyncWorker(self.sheets_service)
        worker.moveToThread(thread)
        thread._worker = worker
        self._active_threads.add(thread)

        thread.started.connect(
            lambda: worker.load_contacts(
                self.config.google_sheet_id,
                self.config.worksheet_name,
                self.config.column_mapping,
                self.config.header_row,
            )
        )
        worker.contacts_loaded.connect(self._on_contacts_loaded)
        worker.error.connect(self._on_sync_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)

        def cleanup():
            self._active_threads.discard(thread)

        thread.finished.connect(cleanup)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _on_contacts_loaded(self, contacts: List[SchoolContact]) -> None:
        t = theme_manager.tokens
        self.schools_queue = [DEFAULT_TEST_SCHOOL] + contacts
        self.current_school_idx = 0
        self.lbl_sheet_status.setText(f"● Google Sheets: {self.config.worksheet_name} ({len(contacts)} škol)")
        self.lbl_sheet_status.setStyleSheet(f"""
            font-size: 12px;
            font-weight: 600;
            color: {t.accent_green_text};
            background-color: {t.accent_green_subtle};
            border: 1px solid {t.accent_green};
            padding: 4px 10px;
            border-radius: 6px;
        """)
        self._display_current_school()
        self.status_bar.showMessage(f"Načteno {len(contacts)} kontaktů z Google Sheets.")

    def _on_sync_error(self, err_msg: str) -> None:
        t = theme_manager.tokens
        self.status_bar.showMessage(f"Chyba synchronizace: {err_msg}")
        self.lbl_sheet_status.setText("● Google Sheets: Chyba synchronizace")
        self.lbl_sheet_status.setStyleSheet(f"""
            font-size: 12px;
            font-weight: 600;
            color: {t.accent_red};
            background-color: {t.accent_red_subtle};
            border: 1px solid {t.accent_red};
            padding: 4px 10px;
            border-radius: 6px;
        """)

    def _load_mock_schools(self) -> None:
        """Záložní ukázková data pro testování rozhraní bez připojené tabulky."""
        self.schools_queue = [
            DEFAULT_TEST_SCHOOL,
            SchoolContact(
                id=1,
                name="Gymnázium Jana Keplera",
                city="Praha 6",
                contact_person="Mgr. Jan Novotný (koordinátor)",
                phone="+420 777 123 456",
                email="novotny@gjk.cz",
                previous_notes="Loni se účastnili s 2 týmy v krajském kole Prezentiády. Byli velmi spokojeni.",
            ),
            SchoolContact(
                id=2,
                name="Gymnázium Poštová",
                city="Košice",
                contact_person="RNDr. Elena Kováčová (zástupkyňa riaditeľa)",
                phone="+421 905 654 321",
                email="kovacova@gpostova.sk",
                previous_notes="Mali záujem o materiály, chceli poslať podrobnosti e-mailom.",
            ),
        ]
        self.current_school_idx = 0
        self._display_current_school()

    def _display_current_school(self) -> None:
        if 0 <= self.current_school_idx < len(self.schools_queue):
            current = self.schools_queue[self.current_school_idx]
            self.school_card.set_school(current)
            self.lbl_queue_counter.setText(f"{self.current_school_idx + 1} / {len(self.schools_queue)}")
            self.call_control.reset()
            self.result_panel.reset()
            self.status_bar.showMessage(f"Načten kontakt: {current.name} (Řádek {current.row_index or '-'})")
        else:
            self.school_card.set_school(None)
            self.lbl_queue_counter.setText("Hotovo")
            self.call_control.reset()
            self.result_panel.reset()
            self.status_bar.showMessage("Všechny školy v aktuální frontě byly zpracovány.")

    def _run_async(self, fn) -> None:
        import threading
        t = threading.Thread(target=fn, daemon=True)
        t.start()

    def _update_device_status(self) -> None:
        """Zaktualizuje indikaci dostupnosti telefonu (KDE Connect & ADB) asynchronně na pozadí."""
        def check():
            device_name = self.config.kdeconnect_device_name or "Galaxy S24 Ultra"
            kde_ok = False
            kde_devices = self.phone_controller.get_kdeconnect_devices()
            for dev in kde_devices:
                if dev["id"] == self.config.kdeconnect_device_id or device_name.lower() in dev["name"].lower():
                    kde_ok = True
                    break

            adb_ok = self.phone_controller.is_adb_connected()
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._apply_device_status(kde_ok, adb_ok))

        self._run_async(check)

    def _apply_device_status(self, kde_ok: bool, adb_ok: bool) -> None:
        t = theme_manager.tokens
        device_name = self.config.kdeconnect_device_name or "Galaxy S24 Ultra"
        kde_str = "KDE" if kde_ok else "KDE ✗"
        adb_str = "ADB" if adb_ok else "ADB ✗"

        self.lbl_device.setText(f"● {device_name} ({kde_str} • {adb_str})")

        if kde_ok and adb_ok:
            self.lbl_device.setStyleSheet(f"""
                font-size: 12px;
                font-weight: 600;
                color: {t.accent_green_text};
                background-color: {t.accent_green_subtle};
                border: 1px solid {t.accent_green};
                padding: 4px 10px;
                border-radius: 6px;
            """)
        elif kde_ok or adb_ok:
            self.lbl_device.setStyleSheet(f"""
                font-size: 12px;
                font-weight: 600;
                color: {t.accent_amber_text};
                background-color: {t.accent_amber_subtle};
                border: 1px solid {t.accent_amber};
                padding: 4px 10px;
                border-radius: 6px;
            """)
        else:
            self.lbl_device.setStyleSheet(f"""
                font-size: 12px;
                font-weight: 600;
                color: {t.accent_red};
                background-color: {t.accent_red_subtle};
                border: 1px solid {t.accent_red};
                padding: 4px 10px;
                border-radius: 6px;
            """)

    # --- Reakce na události hovoru ---

    def _on_call_started(self) -> None:
        school = self._get_current_school()
        if not school:
            self.call_control.dial_failed("Žádná škola k volání.")
            return

        dest = "VoIP (Zoiper)" if school.is_slovak else "GSM (Vodafone)"
        self.status_bar.showMessage(f"Vytáčím {school.clean_phone} přes {dest}...")

        self._dial_thread = DialThread(self.phone_controller, school, self)
        self._dial_thread.dial_result.connect(self._on_dial_result)
        self._dial_thread.start()

    def _on_dial_result(self, ok: bool, msg: str) -> None:
        if ok:
            self.status_bar.showMessage(f"{msg} — Běží odpočet.")
            self.call_control.start_dialing()
        else:
            self.status_bar.showMessage(f"Chyba: {msg}")
            self.call_control.dial_failed(msg)

    def _on_call_connected(self) -> None:
        self.status_bar.showMessage("Hovor spojen! Odpočet byl zastaven.")

    def _on_call_hangup(self) -> None:
        self.status_bar.showMessage("Hovor ukončen. Zvolte výsledek.")

        def do_hangup():
            ok, msg = self.phone_controller.hangup()
            self.status_bar.showMessage(f"{msg}")

        self._run_async(do_hangup)

    def _on_call_timeout(self) -> None:
        self.status_bar.showMessage("Čas vypršel (30s timeout). Odesílám SMS přes ADB...")
        self.result_panel.select_timeout_default()
        school = self._get_current_school()
        if not school:
            return

        def do_timeout():
            ok, msg = self.phone_controller.handle_timeout(school)
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: (
                self.status_bar.showMessage(msg),
                self.result_panel.set_sms_result(ok, msg)
            ))

        self._run_async(do_timeout)

    def _on_send_sms_requested(self) -> None:
        school = self._get_current_school()
        if not school:
            self.result_panel.set_sms_result(False, "Žádná škola k odeslání SMS.")
            return

        self.status_bar.showMessage(f"Odesílám SMS na {school.clean_phone} přes ADB...")

        def do_send():
            ok, msg = self.phone_controller.send_sms_adb(school.clean_phone)
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._on_manual_sms_done(ok, msg))

        self._run_async(do_send)

    def _on_manual_sms_done(self, ok: bool, msg: str) -> None:
        self.result_panel.set_sms_result(ok, msg)
        self.status_bar.showMessage(msg)

    def _on_result_submitted(self, result: CallResult) -> None:
        school = self._get_current_school()
        if not school:
            return

        if school.row_index > 0 and self.config.google_sheet_id:
            self.status_bar.showMessage(f"Zapisuji výsledek do Google Sheets (řádek {school.row_index})...")
            self._save_result_to_sheet(school.row_index, result)

        self.current_school_idx += 1
        if self.current_school_idx < len(self.schools_queue):
            self._display_current_school()
        else:
            self._display_current_school()
            QMessageBox.information(
                self,
                "Hotovo",
                "Všechny školy v aktuální frontě byly úspěšně zpracovány.",
            )

    def _save_result_to_sheet(self, row_index: int, result: CallResult) -> None:
        thread = QThread(self)
        worker = DataSyncWorker(self.sheets_service)
        worker.moveToThread(thread)
        thread._worker = worker
        self._active_threads.add(thread)

        thread.started.connect(
            lambda: worker.save_result(
                self.config.google_sheet_id,
                self.config.worksheet_name,
                row_index,
                self.config.column_mapping,
                result,
                self.config.header_row,
            )
        )
        worker.result_saved.connect(lambda row: self.status_bar.showMessage(f"Výsledek zapsán do Google Sheets (řádek {row})."))
        worker.error.connect(self._on_sync_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)

        def cleanup():
            self._active_threads.discard(thread)

        thread.finished.connect(cleanup)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _get_current_school() -> SchoolContact | None:
        pass
    def _get_current_school(self) -> SchoolContact | None:
        if 0 <= self.current_school_idx < len(self.schools_queue):
            return self.schools_queue[self.current_school_idx]
        return None
