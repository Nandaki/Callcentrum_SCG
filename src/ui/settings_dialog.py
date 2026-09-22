from __future__ import annotations

import io
import random
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
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
    QTabBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
import qrcode
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

from ..config import AppConfig
from ..core.dialer import PhoneController
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
    theme_manager,
)


def generate_qr_pixmap(data: str, size: int = 220) -> QPixmap:
    """Vygeneruje ostrý černobílý QR kód jako QPixmap."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qimg = QImage()
    qimg.loadFromData(buf.getvalue())
    pixmap = QPixmap.fromImage(qimg)
    return pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


class AdbMdnsPairListener(ServiceListener):
    """mDNS posluchač pro odchycení párovacího požadavku z Android telefonu po naskenování QR kódu."""

    def __init__(self, on_pairing_found_cb):
        super().__init__()
        self.on_pairing_found_cb = on_pairing_found_cb
        self.matched = False

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        if self.matched:
            return
        info = zc.get_service_info(type_, name)
        if not info:
            return
        addrs = info.parsed_scoped_addresses()
        if addrs and info.port:
            self.matched = True
            ip = addrs[0]
            port = info.port
            print(f"[mDNS] Nalezena párovací služba Androidu: {name} na {ip}:{port}", flush=True)
            self.on_pairing_found_cb(ip, port)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass


class AdbQrWorker(QObject):
    """Pracovní objekt na pozadí pro naslouchání QR párování a automatické připojení."""

    pairing_detected = Signal(str, int)
    pairing_finished = Signal(bool, str)
    auto_connected = Signal(bool, str)
    finished = Signal()

    def __init__(self, phone_controller: PhoneController, svc_name: str, pass_code: str):
        super().__init__()
        self.phone = phone_controller
        self.svc_name = svc_name
        self.pass_code = pass_code
        self.zeroconf: Optional[Zeroconf] = None
        self.browser: Optional[ServiceBrowser] = None
        self._is_stopped = False

    def start_listening(self) -> None:
        try:
            self.zeroconf = Zeroconf()
            listener = AdbMdnsPairListener(self._on_device_announced)
            self.browser = ServiceBrowser(self.zeroconf, "_adb-tls-pairing._tcp.local.", listener)
            print(f"[AdbQrWorker] Naslouchám mDNS pro QR párování (kód: {self.pass_code})...", flush=True)
        except Exception as e:
            print(f"[AdbQrWorker] Chyba při spuštění mDNS: {e}", flush=True)

    def _on_device_announced(self, ip: str, port: int) -> None:
        if self._is_stopped:
            return
        self.pairing_detected.emit(ip, port)

        # Spustíme adb pair
        ok, msg = self.phone.pair_wireless(ip, port, self.pass_code)
        self.pairing_finished.emit(ok, msg)

        if ok:
            import time
            time.sleep(1.0)
            open_ports = self.phone.scan_open_ports(ip, 35000, 48000)
            if open_ports:
                conn_port = open_ports[0]
                c_ok, c_msg = self.phone.connect_wireless(ip, conn_port)
                self.auto_connected.emit(c_ok, c_msg)
            else:
                self.auto_connected.emit(False, "Telefon spárován, port pro připojení zadejte ručně.")

        self.stop()
        self.finished.emit()

    def stop(self) -> None:
        self._is_stopped = True
        try:
            if self.zeroconf:
                self.zeroconf.close()
                self.zeroconf = None
        except Exception:
            pass


class SheetsWorker(QObject):
    """Worker pro asynchronní operace s Google Sheets."""

    finished = Signal()
    error = Signal(str)
    auth_success = Signal(str)
    worksheets_loaded = Signal(list)
    headers_loaded = Signal(int, list)

    def __init__(self, service: GoogleSheetsService):
        super().__init__()
        self.service = service

    def do_authenticate(self) -> None:
        try:
            self.service.authenticate_interactive()
            email = self.service.get_user_email() or "Google účet autorizován"
            self.auth_success.emit(email)
        except Exception as e:
            self.error.emit(f"Chyba při přihlašování:\n{e}")
        finally:
            self.finished.emit()

    def do_fetch_worksheets(self, spreadsheet_id: str) -> None:
        try:
            worksheets = self.service.get_worksheets(spreadsheet_id)
            self.worksheets_loaded.emit(worksheets)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()

    def do_fetch_headers(self, spreadsheet_id: str, worksheet_name: str, header_row: int) -> None:
        try:
            row_num, headers = self.service.get_headers(spreadsheet_id, worksheet_name, header_row=header_row)
            self.headers_loaded.emit(row_num, headers)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


def get_card_style() -> str:
    t = theme_manager.tokens
    return f"""
        QGroupBox {{
            background-color: {t.bg_card};
            border: 1px solid {t.border_card};
            border-radius: 8px;
            margin-top: 14px;
            padding: 20px 16px 16px 16px;
            font-size: 13px;
            font-weight: 700;
            color: {t.text_primary};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 14px;
            padding: 0 6px;
            background-color: {t.bg_card};
            color: {t.text_secondary};
            border-radius: 4px;
        }}
    """

CARD_STYLE = ""  # Replaced by get_card_style()


class GlobalSettingsDialog(QDialog):
    """Jednotný dialog pro globální nastavení aplikace (Google Sheets, Telefon & ADB, SMS, Integrace)."""

    config_updated = Signal()

    def __init__(
        self,
        config: AppConfig,
        phone_controller: PhoneController,
        initial_tab: int = 0,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.config = config
        self.phone = phone_controller
        self.sheets_service = GoogleSheetsService(
            client_secret_path=config.oauth_client_secret_path,
            token_path=config.oauth_token_path,
        )
        self._active_threads: Set[QThread] = set()
        self.qr_worker: Optional[AdbQrWorker] = None
        self.qr_thread: Optional[QThread] = None

        self.setWindowTitle("Nastavení aplikace — Call Centrum SCG")
        self.resize(860, 840)
        self.setMinimumSize(720, 620)
        self.setStyleSheet(theme_manager.get_stylesheet())

        self._setup_ui()
        self.tab_widget.setCurrentIndex(initial_tab)
        self._load_all_values()

    def _setup_ui(self) -> None:
        t = theme_manager.tokens
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(14)

        # Záhlaví
        header_box = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QLabel("⚙️ Globální nastavení Call Centra")
        lbl_title.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {t.text_primary};")
        lbl_desc = QLabel("Správa propojení s tabulkou, bezdrátového telefonu, automatických SMS a integrací.")
        lbl_desc.setStyleSheet(f"font-size: 12px; color: {t.text_muted};")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_desc)
        header_box.addLayout(title_box)
        header_box.addStretch()
        main_layout.addLayout(header_box)

        # Tab Widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setCursor(Qt.CursorShape.PointingHandCursor)

        # 1. Záložka: Google Tabulka
        self.tab_sheets = self._create_sheets_tab()
        self.tab_widget.addTab(self.tab_sheets, "📊  Google Tabulka")

        # 2. Záložka: Telefon & Wi-Fi ADB
        self.tab_adb = self._create_adb_tab()
        self.tab_widget.addTab(self.tab_adb, "📱  Telefon & Wi-Fi ADB")

        # 3. Záložka: SMS zprávy
        self.tab_sms = self._create_sms_tab()
        self.tab_widget.addTab(self.tab_sms, "💬  SMS zprávy")

        # 4. Záložka: Integrace & KDE
        self.tab_integrations = self._create_integrations_tab()
        self.tab_widget.addTab(self.tab_integrations, "🔌  Integrace & Zařízení")

        main_layout.addWidget(self.tab_widget, stretch=1)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Oddělovač
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("border-color: #e2e8f0;")
        main_layout.addWidget(sep)

        # Spodní akční lišta
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(12)

        btn_cancel = QPushButton("Zrušit / Zavřít")
        btn_cancel.setFixedHeight(40)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.btn_secondary_bg};
                color: {t.btn_secondary_text};
                font-weight: 600;
                border: 1px solid {t.border_subtle};
                border-radius: 6px;
                padding: 0 18px;
            }}
            QPushButton:hover {{
                background-color: {t.bg_hover};
                border-color: {t.border_focus};
            }}
        """)
        btn_cancel.clicked.connect(self.reject)

        self.btn_save_all = QPushButton("Uložit všechna nastavení")
        self.btn_save_all.setFixedHeight(40)
        self.btn_save_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_all.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.btn_primary_bg};
                color: {t.btn_primary_text};
                font-weight: 700;
                font-size: 13px;
                border-radius: 6px;
                border: none;
                padding: 0 24px;
            }}
            QPushButton:hover {{
                background-color: {t.btn_primary_hover};
            }}
        """)
        self.btn_save_all.clicked.connect(self._save_all_settings)

        btn_bar.addStretch()
        btn_bar.addWidget(btn_cancel)
        btn_bar.addWidget(self.btn_save_all)
        main_layout.addLayout(btn_bar)

    # --------------------------------------------------------
    # TAB 1: Google Tabulka
    # --------------------------------------------------------
    def _create_sheets_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 16, 8)
        layout.setSpacing(18)

        t = theme_manager.tokens

        # Krok 1: OAuth
        g_auth = QGroupBox("Krok 1: Přihlášení přes Google účet (OAuth 2.0)")
        g_auth.setStyleSheet(get_card_style())
        auth_lay = QVBoxLayout(g_auth)
        auth_lay.setSpacing(12)

        st_box = QHBoxLayout()
        lbl_at = QLabel("Aktuální stav účtu:")
        lbl_at.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {t.text_primary};")
        self.lbl_auth_status = QLabel("Zjišťuji stav...")
        self.lbl_auth_status.setStyleSheet(f"font-size: 12px; font-weight: 700; padding: 4px 12px; border-radius: 6px; background-color: {t.bg_card_secondary}; color: {t.text_muted};")
        st_box.addWidget(lbl_at)
        st_box.addWidget(self.lbl_auth_status)
        st_box.addStretch()
        auth_lay.addLayout(st_box)

        self.btn_login = QPushButton("🔑  Přihlásit se přes Google účet (otevře prohlížeč)")
        self.btn_login.setFixedHeight(40)
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.setStyleSheet(f"background-color: {t.accent_blue}; color: #ffffff; font-weight: 700; border-radius: 6px; border: none;")
        self.btn_login.clicked.connect(self._run_google_login)
        auth_lay.addWidget(self.btn_login)

        file_box = QHBoxLayout()
        self.txt_creds_path = QLineEdit(self.config.oauth_client_secret_path)
        self.txt_creds_path.setPlaceholderText("Cesta k credentials.json...")
        btn_browse = QPushButton("📁 Procházet...")
        btn_browse.setFixedHeight(36)
        btn_browse.clicked.connect(self._browse_credentials)
        file_box.addWidget(self.txt_creds_path, stretch=1)
        file_box.addWidget(btn_browse)
        auth_lay.addLayout(file_box)
        layout.addWidget(g_auth)

        # Krok 2: URL
        g_sheet = QGroupBox("Krok 2: Odkaz na Google Tabulku")
        g_sheet.setStyleSheet(get_card_style())
        s_lay = QVBoxLayout(g_sheet)
        s_lay.setSpacing(12)

        self.txt_sheet_url = QLineEdit()
        self.txt_sheet_url.setFixedHeight(38)
        self.txt_sheet_url.setPlaceholderText("https://docs.google.com/spreadsheets/d/...")
        s_lay.addWidget(self.txt_sheet_url)

        self.btn_load_worksheets = QPushButton("🔍  Načíst sešit a seznam listů")
        self.btn_load_worksheets.setFixedHeight(40)
        self.btn_load_worksheets.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_load_worksheets.setStyleSheet(f"background-color: {t.btn_primary_bg}; color: {t.btn_primary_text}; font-weight: 700; border-radius: 6px; border: none;")
        self.btn_load_worksheets.clicked.connect(self._fetch_worksheets)
        s_lay.addWidget(self.btn_load_worksheets)

        self.lbl_sheet_msg = QLabel("")
        self.lbl_sheet_msg.setStyleSheet("font-size: 12px; font-weight: 700; color: #0284c7;")
        s_lay.addWidget(self.lbl_sheet_msg)
        layout.addWidget(g_sheet)

        # Krok 3: List a záhlaví
        g_ws = QGroupBox("Krok 3: Výběr listu a řádku se záhlavím")
        g_ws.setStyleSheet(get_card_style())
        ws_lay = QVBoxLayout(g_ws)
        ws_lay.setSpacing(12)

        ws_form = QFormLayout()
        ws_form.setSpacing(10)
        self.cmb_worksheets = QComboBox()
        self.cmb_worksheets.setFixedHeight(36)
        ws_form.addRow("List (sešit):", self.cmb_worksheets)

        self.spn_header_row = QSpinBox()
        self.spn_header_row.setFixedHeight(36)
        self.spn_header_row.setRange(1, 100)
        self.spn_header_row.setValue(self.config.header_row or 11)
        ws_form.addRow("Řádek se záhlavím (SCG řádek 11):", self.spn_header_row)
        ws_lay.addLayout(ws_form)

        self.btn_load_columns = QPushButton("📋  Načíst sloupce z vybraného listu")
        self.btn_load_columns.setFixedHeight(40)
        self.btn_load_columns.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_load_columns.setStyleSheet(f"background-color: {SCG_BLUE}; color: {TEXT_ON_BLUE}; font-weight: 800; border-radius: 8px; border: none;")
        self.btn_load_columns.clicked.connect(self._fetch_headers)
        ws_lay.addWidget(self.btn_load_columns)
        layout.addWidget(g_ws)

        # Krok 4: Mapování
        g_map = QGroupBox("Krok 4: Propojení sloupců tabulky s aplikací")
        g_map.setStyleSheet(get_card_style())
        map_lay = QVBoxLayout(g_map)
        map_lay.setSpacing(12)

        self.mapping_form = QFormLayout()
        self.mapping_form.setSpacing(10)
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
        for key, lbl_txt in fields:
            lbl = QLabel(lbl_txt)
            lbl.setStyleSheet(f"font-weight: 600; color: {t.text_primary}; font-size: 13px;")
            cb = QComboBox()
            cb.setFixedHeight(34)
            cb.addItem("— Nevybráno —", "")
            self.combos[key] = cb
            self.mapping_form.addRow(lbl, cb)
        map_lay.addLayout(self.mapping_form)
        layout.addWidget(g_map)

        scroll.setWidget(container)
        return scroll

    # --------------------------------------------------------
    # TAB 2: Telefon & Wi-Fi ADB
    # --------------------------------------------------------
    def _create_adb_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 16, 8)
        layout.setSpacing(18)

        # Karta 1: QR kód
        g_qr = QGroupBox("1. Spárování pomocí QR kódu (Doporučeno — nejrychlejší)")
        g_qr.setStyleSheet(get_card_style())
        qr_lay = QVBoxLayout(g_qr)
        qr_lay.setSpacing(12)

        lbl_inst = QLabel(
            "Na telefonu v <b>Nastavení -> Možnosti pro vývojáře -> Bezdrátové ladění</b> klepněte na "
            "<b>„Spárovat zařízení pomocí QR kódu“</b> a namiřte fotoaparát na monitor:"
        )
        lbl_inst.setStyleSheet("font-size: 12px; color: #334155; line-height: 1.4;")
        qr_lay.addWidget(lbl_inst)

        qr_box = QHBoxLayout()
        qr_box.addStretch()
        self.lbl_qr_image = QLabel()
        self.lbl_qr_image.setStyleSheet("border: 2px solid #e2e8f0; border-radius: 12px; background-color: #ffffff; padding: 10px;")
        qr_box.addWidget(self.lbl_qr_image)
        qr_box.addStretch()
        qr_lay.addLayout(qr_box)

        self.lbl_qr_status = QLabel("⏳ Čekám na naskenování QR kódu kamerou telefonu...")
        self.lbl_qr_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_qr_status.setStyleSheet("font-size: 13px; font-weight: 800; color: #0284c7; background-color: #f0f9ff; padding: 8px 14px; border-radius: 8px; border: 1px solid #bae6fd;")
        qr_lay.addWidget(self.lbl_qr_status)

        btn_new_qr = QPushButton("🔄  Vygenerovat nový QR kód")
        btn_new_qr.setFixedHeight(36)
        btn_new_qr.clicked.connect(self._start_qr_listener)
        qr_lay.addWidget(btn_new_qr)
        layout.addWidget(g_qr)

        # Karta 2: Ruční kód
        g_man = QGroupBox("2. Alternativa: Ruční spárování 6místným kódem")
        g_man.setStyleSheet(get_card_style())
        man_lay = QVBoxLayout(g_man)
        man_lay.setSpacing(12)

        p_form = QFormLayout()
        p_form.setSpacing(10)
        self.txt_ip = QLineEdit(self.phone.get_kdeconnect_ip() or "192.168.31.146")
        self.txt_ip.setFixedHeight(36)
        p_form.addRow("IP adresa telefonu:", self.txt_ip)

        self.txt_pair_port = QLineEdit()
        self.txt_pair_port.setFixedHeight(36)
        self.txt_pair_port.setPlaceholderText("např. 38921 (z vyskakovacího okna)")
        p_form.addRow("Párovací port z displeje:", self.txt_pair_port)

        self.txt_pair_code = QLineEdit()
        self.txt_pair_code.setFixedHeight(36)
        self.txt_pair_code.setPlaceholderText("např. 842109 (6 číslic)")
        p_form.addRow("6místný párovací kód:", self.txt_pair_code)
        man_lay.addLayout(p_form)

        btn_manual_pair = QPushButton("🔗  Spárovat ručně")
        btn_manual_pair.setFixedHeight(38)
        btn_manual_pair.clicked.connect(self._run_manual_pair)
        man_lay.addWidget(btn_manual_pair)
        layout.addWidget(g_man)

        # Karta 3: Připojení
        g_conn = QGroupBox("3. Připojení telefonu (pokud již máte spárováno)")
        g_conn.setStyleSheet(get_card_style())
        c_lay = QVBoxLayout(g_conn)
        c_lay.setSpacing(12)

        c_box = QHBoxLayout()
        self.txt_connect_port = QLineEdit()
        self.txt_connect_port.setFixedHeight(36)
        self.txt_connect_port.setPlaceholderText("např. 43255 (z hlavní obrazovky Bezdrátového ladění)")
        btn_scan = QPushButton("🔍 Najít otevřený port")
        btn_scan.setFixedHeight(36)
        btn_scan.clicked.connect(self._run_port_scan)
        c_box.addWidget(self.txt_connect_port, stretch=1)
        c_box.addWidget(btn_scan)
        c_lay.addLayout(c_box)

        btn_conn = QPushButton("⚡  Připojit telefon přes Wi-Fi (ADB Connect)")
        btn_conn.setFixedHeight(40)
        btn_conn.setCursor(Qt.CursorShape.PointingHandCursor)
        t = theme_manager.tokens
        btn_conn.setStyleSheet(f"background-color: {t.btn_primary_bg}; color: {t.btn_primary_text}; font-weight: 700; border-radius: 6px; border: none;")
        btn_conn.clicked.connect(self._run_adb_connect)
        c_lay.addWidget(btn_conn)
        layout.addWidget(g_conn)

        # Karta 4: Stav
        g_st = QGroupBox("4. Aktuální stav ADB připojení")
        g_st.setStyleSheet(get_card_style())
        st_lay = QVBoxLayout(g_st)
        st_lay.setSpacing(10)

        self.lbl_adb_status = QLabel("Ověřuji stav ADB...")
        self.lbl_adb_status.setStyleSheet("font-size: 13px; font-weight: 800; color: #475569;")
        st_lay.addWidget(self.lbl_adb_status)

        st_btn_box = QHBoxLayout()
        btn_ref = QPushButton("🔄 Obnovit stav")
        btn_ref.setFixedHeight(34)
        btn_ref.clicked.connect(self._refresh_adb_status)
        btn_disc = QPushButton("Odpojit ADB")
        btn_disc.setFixedHeight(34)
        btn_disc.setStyleSheet("color: #dc2626; font-weight: bold;")
        btn_disc.clicked.connect(self._disconnect_adb)
        st_btn_box.addWidget(btn_ref)
        st_btn_box.addWidget(btn_disc)
        st_btn_box.addStretch()
        st_lay.addLayout(st_btn_box)
        layout.addWidget(g_st)

        scroll.setWidget(container)
        return scroll

    # --------------------------------------------------------
    # TAB 3: SMS Zprávy
    # --------------------------------------------------------
    def _create_sms_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 16, 8)
        layout.setSpacing(18)

        # Šablona SMS
        g_sms = QGroupBox("Šablona SMS zprávy při nezastižení (odesílá se přes ADB)")
        g_sms.setStyleSheet(get_card_style())
        sms_lay = QVBoxLayout(g_sms)
        sms_lay.setSpacing(12)

        lbl_sms_desc = QLabel(
            "Tento text se <b>automaticky odešle jako SMS přímo z vašeho telefonu</b>, "
            "pokud nikdo nezvedne hovor do 30 sekund.<br>"
            "Text je vždy stejný a můžete si ho zde libovolně upravit:"
        )
        lbl_sms_desc.setStyleSheet("font-size: 12px; color: #475569; line-height: 1.4;")
        sms_lay.addWidget(lbl_sms_desc)

        self.txt_sms_template = QTextEdit()
        self.txt_sms_template.setFixedHeight(110)
        self.txt_sms_template.setText(self.config.silent_sms_template)
        self.txt_sms_template.textChanged.connect(self._update_sms_char_count)
        sms_lay.addWidget(self.txt_sms_template)

        self.lbl_sms_char_count = QLabel("0 znaků")
        self.lbl_sms_char_count.setStyleSheet("font-size: 12px; font-weight: bold; color: #64748b;")
        sms_lay.addWidget(self.lbl_sms_char_count)
        self._update_sms_char_count()

        layout.addWidget(g_sms)

        # Test odeslání SMS
        g_test = QGroupBox("Otestovat odeslání SMS přes ADB na telefon")
        g_test.setStyleSheet(get_card_style())
        test_lay = QVBoxLayout(g_test)
        test_lay.setSpacing(12)

        t_form = QFormLayout()
        t_form.setSpacing(10)
        self.txt_test_phone = QLineEdit("+420733215027")
        self.txt_test_phone.setFixedHeight(36)
        self.txt_test_phone.setPlaceholderText("+420...")
        t_form.addRow("Telefonní číslo pro test:", self.txt_test_phone)
        test_lay.addLayout(t_form)

        btn_test_sms = QPushButton("📨  Odeslat testovací SMS přes ADB nyní")
        btn_test_sms.setFixedHeight(42)
        btn_test_sms.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_test_sms.setStyleSheet(f"background-color: {SCG_BLUE}; color: {TEXT_ON_BLUE}; font-weight: 800; border-radius: 8px; border: none;")
        btn_test_sms.clicked.connect(self._run_test_sms)
        test_lay.addWidget(btn_test_sms)

        self.lbl_test_sms_status = QLabel("")
        self.lbl_test_sms_status.setStyleSheet("font-size: 12px; font-weight: bold; color: #0284c7;")
        test_lay.addWidget(self.lbl_test_sms_status)

        layout.addWidget(g_test)

        # Časovač hovoru
        g_time = QGroupBox("Časový limit pro vyzvánění před odesláním SMS")
        g_time.setStyleSheet(get_card_style())
        time_lay = QVBoxLayout(g_time)
        time_lay.setSpacing(10)

        tm_form = QFormLayout()
        self.spn_call_timeout = QSpinBox()
        self.spn_call_timeout.setFixedHeight(36)
        self.spn_call_timeout.setRange(10, 120)
        self.spn_call_timeout.setValue(self.config.call_timeout_seconds or 30)
        self.spn_call_timeout.setSuffix(" sekund")
        tm_form.addRow("Doba vyzvánění (odpočet):", self.spn_call_timeout)
        time_lay.addLayout(tm_form)

        layout.addWidget(g_time)

        scroll.setWidget(container)
        return scroll

    # --------------------------------------------------------
    # TAB 4: Integrace & Zařízení
    # --------------------------------------------------------
    def _create_integrations_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 16, 8)
        layout.setSpacing(18)

        # KDE Connect
        g_kde = QGroupBox("KDE Connect (místní síť Wi-Fi)")
        g_kde.setStyleSheet(get_card_style())
        kde_lay = QVBoxLayout(g_kde)
        kde_lay.setSpacing(10)

        k_form = QFormLayout()
        k_form.setSpacing(10)
        self.txt_kde_id = QLineEdit(self.config.kdeconnect_device_id)
        self.txt_kde_id.setFixedHeight(36)
        k_form.addRow("ID zařízení:", self.txt_kde_id)

        self.txt_kde_name = QLineEdit(self.config.kdeconnect_device_name)
        self.txt_kde_name.setFixedHeight(36)
        k_form.addRow("Název zařízení:", self.txt_kde_name)
        kde_lay.addLayout(k_form)

        btn_find_kde = QPushButton("🔄 Zjistit spárované zařízení z KDE Connect")
        btn_find_kde.setFixedHeight(36)
        btn_find_kde.clicked.connect(self._auto_detect_kde)
        kde_lay.addWidget(btn_find_kde)
        layout.addWidget(g_kde)

        # VoIP Odorik
        g_voip = QGroupBox("VoIP Zoiper (Slovenské hovory +421)")
        g_voip.setStyleSheet(get_card_style())
        voip_lay = QVBoxLayout(g_voip)
        voip_lay.setSpacing(10)

        v_form = QFormLayout()
        v_form.setSpacing(10)
        self.txt_sip_domain = QLineEdit(self.config.sip_domain)
        self.txt_sip_domain.setFixedHeight(36)
        v_form.addRow("SIP Doména:", self.txt_sip_domain)

        self.txt_zoiper_pkg = QLineEdit(self.config.zoiper_package)
        self.txt_zoiper_pkg.setFixedHeight(36)
        v_form.addRow("Balíček Zoiper:", self.txt_zoiper_pkg)
        voip_lay.addLayout(v_form)
        layout.addWidget(g_voip)

        scroll.setWidget(container)
        return scroll

    # --------------------------------------------------------
    # Logika a události
    # --------------------------------------------------------
    def _update_sms_char_count(self) -> None:
        txt = self.txt_sms_template.toPlainText()
        length = len(txt)
        sms_count = 1 if length <= 160 else (length // 153 + 1)
        self.lbl_sms_char_count.setText(f"{length} znaků ({sms_count} SMS zpráva/zprávy)")

    def _load_all_values(self) -> None:
        # Sheets
        self.txt_sheet_url.setText(self.config.google_sheet_url or self.config.google_sheet_id)
        if self.config.worksheet_name:
            self.cmb_worksheets.addItem(self.config.worksheet_name)
            self.cmb_worksheets.setCurrentText(self.config.worksheet_name)
        if self.config.header_row:
            self.spn_header_row.setValue(self.config.header_row)

        self._update_auth_ui()
        self._refresh_adb_status()
        self._start_qr_listener()

    def _update_auth_ui(self) -> None:
        if self.sheets_service.is_authenticated():
            email = self.sheets_service.get_user_email() or "Token aktivní"
            self.lbl_auth_status.setText(f"🟢 Přihlášen: {email}")
            self.lbl_auth_status.setStyleSheet("font-size: 12px; font-weight: 800; padding: 4px 12px; border-radius: 6px; background-color: #eefbf6; color: #059669; border: 1px solid #5dd0a6;")
            self.btn_login.setText("🔄  Znovu autorizovat Google účet")
        else:
            self.lbl_auth_status.setText("🔴 Nepřihlášen")
            self.lbl_auth_status.setStyleSheet("font-size: 12px; font-weight: 800; padding: 4px 12px; border-radius: 6px; background-color: #fef2f2; color: #dc2626; border: 1px solid #fca5a5;")
            self.btn_login.setText("🔑  Přihlásit se přes Google účet (otevře prohlížeč)")

    def _browse_credentials(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Vyberte credentials.json", str(Path.home()), "JSON (*.json)")
        if path:
            self.txt_creds_path.setText(path)
            self.sheets_service.client_secret_path = Path(path)
            self._update_auth_ui()

    def _run_google_login(self) -> None:
        path = self.txt_creds_path.text().strip()
        if not path or not Path(path).exists():
            QMessageBox.warning(self, "Chyba", f"Soubor credentials.json nebyl nalezen na:\n{path}")
            return
        self.sheets_service.client_secret_path = Path(path)
        self.btn_login.setEnabled(False)

        def do_auth():
            try:
                self.sheets_service.authenticate_interactive()
                email = self.sheets_service.get_user_email() or "Google účet"
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self._on_auth_done(email))
            except Exception as e:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, lambda: QMessageBox.critical(self, "Chyba", str(e)))
            finally:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self.btn_login.setEnabled(True))

        import threading
        threading.Thread(target=do_auth, daemon=True).start()

    def _on_auth_done(self, email: str) -> None:
        self._update_auth_ui()
        QMessageBox.information(self, "Úspěch", f"Google účet připojen:\n{email}")

    def _fetch_worksheets(self) -> None:
        url = self.txt_sheet_url.text().strip()
        s_id = extract_spreadsheet_id(url)
        if not s_id:
            QMessageBox.warning(self, "Chyba", "Zadejte odkaz na tabulku nebo její ID.")
            return

        self.btn_load_worksheets.setEnabled(False)
        self.lbl_sheet_msg.setText("⏳ Stahuji seznam listů z tabulky...")

        def fetch():
            try:
                ws = self.sheets_service.get_worksheets(s_id)
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self._on_worksheets_loaded(ws))
            except Exception as e:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self._on_sheet_error(str(e)))
            finally:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self.btn_load_worksheets.setEnabled(True))

        import threading
        threading.Thread(target=fetch, daemon=True).start()

    def _on_worksheets_loaded(self, sheets: List[str]) -> None:
        self.cmb_worksheets.clear()
        for s in sheets:
            self.cmb_worksheets.addItem(s)
        pref = self.config.worksheet_name or ("CZ SŠ" if "CZ SŠ" in sheets else "")
        if pref and pref in sheets:
            self.cmb_worksheets.setCurrentText(pref)
        self.lbl_sheet_msg.setText(f"✅ Nalezeno {len(sheets)} listů. Přejděte ke Kroku 3.")
        self.lbl_sheet_msg.setStyleSheet("font-size: 12px; font-weight: bold; color: #059669;")

    def _fetch_headers(self) -> None:
        url = self.txt_sheet_url.text().strip()
        s_id = extract_spreadsheet_id(url)
        w_name = self.cmb_worksheets.currentText().strip()
        h_row = self.spn_header_row.value()

        if not s_id or not w_name:
            QMessageBox.warning(self, "Chyba", "Nejprve načtěte tabulku a vyberte list.")
            return

        self.btn_load_columns.setEnabled(False)
        self.lbl_sheet_msg.setText(f"⏳ Načítám sloupce z listu '{w_name}'...")

        def fetch():
            try:
                r_num, headers = self.sheets_service.get_headers(s_id, w_name, header_row=h_row)
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self._on_headers_loaded(r_num, headers))
            except Exception as e:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self._on_sheet_error(str(e)))
            finally:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self.btn_load_columns.setEnabled(True))

        import threading
        threading.Thread(target=fetch, daemon=True).start()

    def _on_headers_loaded(self, row_num: int, headers: List[str]) -> None:
        self.spn_header_row.setValue(row_num)
        saved = self.config.column_mapping or {}

        for key, cb in self.combos.items():
            cb.clear()
            cb.addItem("— Nevybráno —", "")
            for h in headers:
                cb.addItem(h, h)
            val = saved.get(key)
            if val and val in headers:
                cb.setCurrentText(val)
            else:
                self._auto_detect_col(key, headers, cb)

        self.lbl_sheet_msg.setText(f"✅ Načteno {len(headers)} sloupců z řádku {row_num}.")
        self.lbl_sheet_msg.setStyleSheet("font-size: 12px; font-weight: bold; color: #059669;")

    def _auto_detect_col(self, key: str, headers: List[str], cb: QComboBox) -> None:
        kw = {
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
        for h in headers:
            hl = h.lower()
            if any(c == hl or c in hl for c in kw.get(key, [])):
                cb.setCurrentText(h)
                break

    def _on_sheet_error(self, msg: str) -> None:
        self.lbl_sheet_msg.setText("❌ Chyba při operaci.")
        self.lbl_sheet_msg.setStyleSheet("font-size: 12px; font-weight: bold; color: #dc2626;")
        QMessageBox.critical(self, "Chyba", msg)

    # ADB
    def _start_qr_listener(self) -> None:
        self._stop_qr_listener()
        svc = f"callcenter-{random.randint(1000, 9999)}"
        code = f"{random.randint(100000, 999999)}"
        qr_txt = f"WIFI:T:ADB;S:{svc};P:{code};;"

        pix = generate_qr_pixmap(qr_txt, size=210)
        self.lbl_qr_image.setPixmap(pix)
        self.lbl_qr_status.setText("⏳ Čekám na naskenování QR kódu kamerou telefonu...")
        self.lbl_qr_status.setStyleSheet("font-size: 13px; font-weight: 800; color: #0284c7; background-color: #f0f9ff; padding: 8px 14px; border-radius: 8px; border: 1px solid #bae6fd;")

        self.qr_thread = QThread(self)
        self.qr_worker = AdbQrWorker(self.phone, svc, code)
        self.qr_worker.moveToThread(self.qr_thread)

        self.qr_thread.started.connect(self.qr_worker.start_listening)
        self.qr_worker.pairing_detected.connect(lambda ip, port: self.lbl_qr_status.setText(f"🔄 Telefon nalezen na {ip}:{port}, páruji..."))
        self.qr_worker.pairing_finished.connect(self._on_qr_pair_done)
        self.qr_worker.auto_connected.connect(self._on_qr_connected)
        self.qr_worker.finished.connect(self.qr_thread.quit)

        def cleanup():
            self.qr_worker = None
            self.qr_thread = None

        self.qr_thread.finished.connect(cleanup)
        self.qr_thread.start()

    def _stop_qr_listener(self) -> None:
        w = self.qr_worker
        t = self.qr_thread
        self.qr_worker = None
        self.qr_thread = None
        try:
            if w:
                w.stop()
        except Exception:
            pass
        try:
            if t and t.isRunning():
                t.quit()
                t.wait(800)
        except Exception:
            pass

    def _on_qr_pair_done(self, ok: bool, msg: str) -> None:
        if ok:
            self.lbl_qr_status.setText("✅ Spárováno! Připojuji k telefonu...")
            self.lbl_qr_status.setStyleSheet("font-size: 13px; font-weight: 800; color: #059669; background-color: #ecfdf5; padding: 8px 14px; border-radius: 8px; border: 1px solid #a7f3d0;")
        else:
            self.lbl_qr_status.setText(f"❌ Párování selhalo: {msg}")
            self.lbl_qr_status.setStyleSheet("font-size: 13px; font-weight: 800; color: #dc2626; background-color: #fef2f2; padding: 8px 14px; border-radius: 8px; border: 1px solid #fca5a5;")
        self._refresh_adb_status()

    def _on_qr_connected(self, ok: bool, msg: str) -> None:
        if ok:
            self.lbl_qr_status.setText("🎉 Telefon úspěšně spárován a PŘIPOJEN!")
            self.lbl_qr_status.setStyleSheet("font-size: 13px; font-weight: 800; color: #059669; background-color: #d1fae5; padding: 8px 14px; border-radius: 8px; border: 1.5px solid #10b981;")
            QMessageBox.information(self, "Připojeno", "Telefon je připraven pro volání i SMS!")
        self._refresh_adb_status()

    def _run_manual_pair(self) -> None:
        ip = self.txt_ip.text().strip()
        port = self.txt_pair_port.text().strip()
        code = self.txt_pair_code.text().strip()
        if not ip or not port or not code:
            QMessageBox.warning(self, "Chyba", "Vyplňte IP, port i kód.")
            return

        def pair():
            ok, msg = self.phone.pair_wireless(ip, port, code)
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._on_manual_pair_done(ok, msg))

        import threading
        threading.Thread(target=pair, daemon=True).start()

    def _on_manual_pair_done(self, ok: bool, msg: str) -> None:
        if ok:
            QMessageBox.information(self, "Spárováno", f"{msg}\nZadejte port pro připojení a klikněte na Připojit.")
        else:
            QMessageBox.warning(self, "Chyba", msg)
        self._refresh_adb_status()

    def _run_port_scan(self) -> None:
        ip = self.txt_ip.text().strip()
        if not ip:
            QMessageBox.warning(self, "Chyba", "Zadejte IP adresu telefonu.")
            return

        def scan():
            ports = self.phone.scan_open_ports(ip)
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._on_scan_done(ports))

        import threading
        threading.Thread(target=scan, daemon=True).start()

    def _on_scan_done(self, ports: List[int]) -> None:
        if ports:
            p = str(ports[0])
            self.txt_connect_port.setText(p)
            QMessageBox.information(self, "Nalezeno", f"Nalezen otevřený port: {p}")
        else:
            QMessageBox.information(self, "Sken", "Žádný port nebyl nalezen. Zkontrolujte, zda je Bezdrátové ladění ZAPNUTO.")

    def _run_adb_connect(self) -> None:
        ip = self.txt_ip.text().strip()
        port = self.txt_connect_port.text().strip()
        if not ip or not port:
            QMessageBox.warning(self, "Chyba", "Zadejte IP i port pro připojení.")
            return

        def conn():
            ok, msg = self.phone.connect_wireless(ip, port)
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._on_connect_done(ok, msg))

        import threading
        threading.Thread(target=conn, daemon=True).start()

    def _on_connect_done(self, ok: bool, msg: str) -> None:
        if ok:
            QMessageBox.information(self, "Připojeno", msg)
        else:
            QMessageBox.warning(self, "Chyba", msg)
        self._refresh_adb_status()

    def _disconnect_adb(self) -> None:
        self.phone.disconnect_wireless()
        self._refresh_adb_status()

    def _refresh_adb_status(self) -> None:
        devs = self.phone.get_adb_devices()
        if devs:
            self.lbl_adb_status.setText(f"🟢 PŘIPOJENO K ADB: {', '.join(devs)}")
            self.lbl_adb_status.setStyleSheet("font-size: 13px; font-weight: 800; color: #059669;")
        else:
            self.lbl_adb_status.setText("🔴 Není připojeno žádné ADB zařízení.")
            self.lbl_adb_status.setStyleSheet("font-size: 13px; font-weight: 800; color: #dc2626;")

    # SMS
    def _run_test_sms(self) -> None:
        number = self.txt_test_phone.text().strip()
        text = self.txt_sms_template.toPlainText().strip()
        if not number:
            QMessageBox.warning(self, "Chyba", "Zadejte telefonní číslo pro test.")
            return
        if not text:
            QMessageBox.warning(self, "Chyba", "Text SMS nemůže být prázdný.")
            return

        self.lbl_test_sms_status.setText("⏳ Odesílám testovací SMS přes ADB...")
        self.lbl_test_sms_status.setStyleSheet("font-size: 12px; font-weight: bold; color: #d97706;")

        def send():
            ok, msg = self.phone.send_sms_adb(number, text)
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._on_test_sms_done(ok, msg))

        import threading
        threading.Thread(target=send, daemon=True).start()

    def _on_test_sms_done(self, ok: bool, msg: str) -> None:
        if ok:
            self.lbl_test_sms_status.setText(f"✅ {msg}")
            self.lbl_test_sms_status.setStyleSheet("font-size: 12px; font-weight: bold; color: #059669;")
            QMessageBox.information(self, "SMS Odeslána", f"{msg}\nZkontrolujte telefon.")
        else:
            self.lbl_test_sms_status.setText(f"❌ {msg}")
            self.lbl_test_sms_status.setStyleSheet("font-size: 12px; font-weight: bold; color: #dc2626;")
            QMessageBox.warning(self, "Chyba SMS", msg)

    # KDE
    def _auto_detect_kde(self) -> None:
        devs = self.phone.get_kdeconnect_devices()
        if devs:
            d = devs[0]
            self.txt_kde_id.setText(d["id"])
            self.txt_kde_name.setText(d["name"])
            QMessageBox.information(self, "KDE Connect", f"Nalezeno zařízení: {d['name']} ({d['id']})")
        else:
            QMessageBox.warning(self, "KDE Connect", "Nebylo nalezeno žádné aktivní zařízení.")

    # Uložení
    def _save_all_settings(self) -> None:
        # 1. Sheets
        raw_url = self.txt_sheet_url.text().strip()
        s_id = extract_spreadsheet_id(raw_url)
        w_name = self.cmb_worksheets.currentText().strip()
        h_row = self.spn_header_row.value()

        mapping: Dict[str, str] = {}
        for key, cb in self.combos.items():
            val = cb.currentText()
            mapping[key] = "" if val == "— Nevybráno —" else val

        self.config.google_sheet_url = raw_url
        self.config.google_sheet_id = s_id
        self.config.worksheet_name = w_name
        self.config.header_row = h_row
        self.config.column_mapping = mapping
        self.config.oauth_client_secret_path = self.txt_creds_path.text().strip()

        # 2. SMS & Timeout
        self.config.silent_sms_template = self.txt_sms_template.toPlainText().strip()
        self.config.call_timeout_seconds = self.spn_call_timeout.value()

        # 3. KDE & VoIP
        self.config.kdeconnect_device_id = self.txt_kde_id.text().strip()
        self.config.kdeconnect_device_name = self.txt_kde_name.text().strip()
        self.config.sip_domain = self.txt_sip_domain.text().strip()
        self.config.zoiper_package = self.txt_zoiper_pkg.text().strip()

        self.config.save()
        self.config_updated.emit()
        self._stop_qr_listener()
        self.accept()

    def closeEvent(self, event) -> None:
        self._stop_qr_listener()
        super().closeEvent(event)

    def reject(self) -> None:
        self._stop_qr_listener()
        super().reject()
