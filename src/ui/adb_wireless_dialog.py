from __future__ import annotations

import io
import random
import re
import socket
from typing import List, Optional, Set

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog,
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
    QVBoxLayout,
    QWidget,
)
import qrcode
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

from ..config import AppConfig
from ..core.dialer import PhoneController
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
            print(f"[mDNS] Nalezena párovací služba Androidu: {name} na {ip}:{port}")
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
            print(f"[AdbQrWorker] Naslouchám mDNS pro QR párování (kód: {self.pass_code})...")
        except Exception as e:
            print(f"[AdbQrWorker] Chyba při spuštění mDNS: {e}")

    def _on_device_announced(self, ip: str, port: int) -> None:
        if self._is_stopped:
            return
        self.pairing_detected.emit(ip, port)

        # 1. Spustíme adb pair
        ok, msg = self.phone.pair_wireless(ip, port, self.pass_code)
        self.pairing_finished.emit(ok, msg)

        if ok:
            # 2. Po spárování zkusíme automaticky najít port pro připojení
            import time
            time.sleep(1.0)
            open_ports = self.phone.scan_open_ports(ip, 35000, 48000)
            if open_ports:
                conn_port = open_ports[0]
                c_ok, c_msg = self.phone.connect_wireless(ip, conn_port)
                self.auto_connected.emit(c_ok, c_msg)
            else:
                self.auto_connected.emit(False, f"Telefon spárován, ale port pro připojení nebyl nalezen. Zadejte port z displeje ručně.")

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


class AdbAsyncWorker(QObject):
    """Worker pro manuální síťové operace ADB a skenování portů."""

    finished = Signal()
    scan_done = Signal(list)
    pair_done = Signal(bool, str)
    connect_done = Signal(bool, str)

    def __init__(self, phone_controller: PhoneController):
        super().__init__()
        self.phone = phone_controller

    def do_scan(self, ip: str) -> None:
        ports = self.phone.scan_open_ports(ip)
        self.scan_done.emit(ports)
        self.finished.emit()

    def do_pair(self, ip: str, port: str, code: str) -> None:
        ok, msg = self.phone.pair_wireless(ip, port, code)
        self.pair_done.emit(ok, msg)
        self.finished.emit()

    def do_connect(self, ip: str, port: str) -> None:
        ok, msg = self.phone.connect_wireless(ip, port)
        self.connect_done.emit(ok, msg)
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
    QLineEdit {
        background-color: #ffffff;
        color: #1e293b;
        border: 1.5px solid #cbd5e1;
        border-radius: 8px;
        padding: 7px 12px;
        font-size: 13px;
        min-height: 24px;
    }
    QLineEdit:focus {
        border-color: #5d9be6;
        background-color: #ffffff;
    }
"""


class AdbWirelessDialog(QDialog):
    """Moderní dialog pro bezdrátové spárování (QR kódem i ručně) a připojení telefonu přes Wi-Fi."""

    device_connected = Signal()

    def __init__(self, config: AppConfig, phone_controller: PhoneController, parent: QWidget | None = None):
        super().__init__(parent)
        self.config = config
        self.phone = phone_controller
        self._active_threads: Set[QThread] = set()
        self.qr_worker: Optional[AdbQrWorker] = None
        self.qr_thread: Optional[QThread] = None

        self.setWindowTitle("Bezdrátové připojení telefonu (Wi-Fi ADB)")
        self.resize(760, 840)
        self.setMinimumSize(660, 600)
        self.setStyleSheet(f"background-color: #f8fafc; {INPUT_STYLE}")

        self._setup_ui()
        self._start_qr_listener()
        self._refresh_status()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # ----------------------------------------------------
        # Záhlaví dialogu
        # ----------------------------------------------------
        header_box = QVBoxLayout()
        header_box.setSpacing(4)
        lbl_title = QLabel("📶 Bezdrátové připojení telefonu přes Wi-Fi")
        lbl_title.setStyleSheet(f"font-size: 20px; font-weight: 900; color: {SCG_DARK_BLUE};")
        header_box.addWidget(lbl_title)

        lbl_desc = QLabel(
            "Na telefonu zapněte <b>Nastavení -> Možnosti pro vývojáře -> Bezdrátové ladění</b>.<br>"
            "Spárování stačí provést <b>pouze jednou</b> (telefon si počítač zapamatuje)."
        )
        lbl_desc.setStyleSheet("font-size: 13px; color: #64748b; line-height: 1.4;")
        header_box.addWidget(lbl_desc)
        main_layout.addLayout(header_box)

        # ----------------------------------------------------
        # Posuvná oblast s kartami shora dolů
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
        # 1. KARTA: Spárování pomocí QR kódu (Doporučeno)
        # ----------------------------------------------------
        group_qr = QGroupBox("1. Spárování pomocí QR kódu (Nejrychlejší)")
        group_qr.setStyleSheet(CARD_STYLE)
        qr_layout = QVBoxLayout(group_qr)
        qr_layout.setSpacing(14)

        lbl_qr_inst = QLabel(
            "V telefonu klepněte na <b>„Spárovat zařízení pomocí QR kódu“</b> a namiřte fotoaparát na kód níže:"
        )
        lbl_qr_inst.setStyleSheet("font-size: 13px; color: #334155;")
        qr_layout.addWidget(lbl_qr_inst)

        # Středový box pro QR kód
        qr_center_box = QHBoxLayout()
        qr_center_box.addStretch()

        self.lbl_qr_image = QLabel()
        self.lbl_qr_image.setStyleSheet(
            "border: 2px solid #e2e8f0; border-radius: 12px; background-color: #ffffff; padding: 12px;"
        )
        qr_center_box.addWidget(self.lbl_qr_image)
        qr_center_box.addStretch()
        qr_layout.addLayout(qr_center_box)

        # Stav QR párování
        self.lbl_qr_status = QLabel("⏳ Čekám na naskenování QR kódu kamerou telefonu...")
        self.lbl_qr_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_qr_status.setStyleSheet(
            "font-size: 13px; font-weight: 800; color: #0284c7; background-color: #f0f9ff; "
            "padding: 8px 14px; border-radius: 8px; border: 1px solid #bae6fd;"
        )
        qr_layout.addWidget(self.lbl_qr_status)

        # Tlačítko přegenerovat QR
        btn_refresh_qr = QPushButton("🔄  Vygenerovat nový QR kód")
        btn_refresh_qr.setFixedHeight(36)
        btn_refresh_qr.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh_qr.setStyleSheet(f"""
            QPushButton {{
                background-color: #f1f5f9;
                color: {SCG_DARK_BLUE};
                font-weight: 700;
                border: 1.5px solid #cbd5e1;
                border-radius: 8px;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                background-color: #e2e8f0;
                border-color: {SCG_BLUE};
            }}
        """)
        btn_refresh_qr.clicked.connect(self._regenerate_qr)
        qr_layout.addWidget(btn_refresh_qr)

        layout.addWidget(group_qr)

        # ----------------------------------------------------
        # 2. KARTA: Alternativa – Ruční spárování kódem
        # ----------------------------------------------------
        group_manual = QGroupBox("2. Alternativa: Ruční spárování 6místným kódem")
        group_manual.setStyleSheet(CARD_STYLE)
        manual_layout = QVBoxLayout(group_manual)
        manual_layout.setSpacing(14)

        lbl_manual_hint = QLabel(
            "Pokud nemůžete naskenovat QR kód, klepněte v telefonu na <b>„Spárovat zařízení pomocí párovacího kódu“</b> a opište údaje z displeje:"
        )
        lbl_manual_hint.setStyleSheet("font-size: 12px; color: #475569; line-height: 1.4;")
        manual_layout.addWidget(lbl_manual_hint)

        pair_form = QFormLayout()
        pair_form.setSpacing(12)

        # IP adresa
        ip_row = QHBoxLayout()
        default_ip = self.phone.get_kdeconnect_ip() or "192.168.31.146"
        self.txt_ip = QLineEdit(default_ip)
        self.txt_ip.setFixedHeight(38)
        self.txt_ip.setPlaceholderText("např. 192.168.31.146")

        btn_detect_ip = QPushButton("🔄 Zjistit z KDE")
        btn_detect_ip.setFixedHeight(38)
        btn_detect_ip.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_detect_ip.setStyleSheet(f"""
            QPushButton {{
                background-color: #ffffff;
                color: {SCG_DARK_BLUE};
                font-weight: bold;
                border: 1.5px solid #cbd5e1;
                border-radius: 8px;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background-color: #f1f5f9;
                border-color: {SCG_BLUE};
            }}
        """)
        btn_detect_ip.clicked.connect(self._detect_ip)
        ip_row.addWidget(self.txt_ip, stretch=1)
        ip_row.addWidget(btn_detect_ip)

        lbl_ip = QLabel("IP adresa telefonu:")
        lbl_ip.setStyleSheet(f"font-weight: 800; color: {SCG_DARK_BLUE}; font-size: 13px;")
        pair_form.addRow(lbl_ip, ip_row)

        # Párovací port
        self.txt_pair_port = QLineEdit()
        self.txt_pair_port.setFixedHeight(38)
        self.txt_pair_port.setPlaceholderText("např. 38921 (5místné číslo za dvojtečkou z vyskakovacího okna)")
        lbl_pport = QLabel("Párovací port z displeje:")
        lbl_pport.setStyleSheet(f"font-weight: 800; color: {SCG_DARK_BLUE}; font-size: 13px;")
        pair_form.addRow(lbl_pport, self.txt_pair_port)

        # Párovací kód
        self.txt_pair_code = QLineEdit()
        self.txt_pair_code.setFixedHeight(38)
        self.txt_pair_code.setPlaceholderText("např. 842109 (6místný kód z vyskakovacího okna)")
        lbl_pcode = QLabel("6místný párovací kód:")
        lbl_pcode.setStyleSheet(f"font-weight: 800; color: {SCG_DARK_BLUE}; font-size: 13px;")
        pair_form.addRow(lbl_pcode, self.txt_pair_code)

        manual_layout.addLayout(pair_form)

        self.btn_pair = QPushButton("🔗  Spárovat zařízení ručně")
        self.btn_pair.setFixedHeight(40)
        self.btn_pair.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pair.setStyleSheet(f"""
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
        self.btn_pair.clicked.connect(self._run_pair)
        manual_layout.addWidget(self.btn_pair)

        layout.addWidget(group_manual)

        # ----------------------------------------------------
        # 3. KARTA: Připojení k ADB (pokud již spárováno)
        # ----------------------------------------------------
        group_connect = QGroupBox("3. Připojení telefonu (pokud již máte spárováno)")
        group_connect.setStyleSheet(CARD_STYLE)
        conn_layout = QVBoxLayout(group_connect)
        conn_layout.setSpacing(14)

        lbl_conn_desc = QLabel(
            "Po spárování zavřete vyskakovací okno na displeji telefonu.<br>"
            "Zadejte port uvedený pod <b>„IP adresa a port“</b> na hlavní obrazovce Bezdrátového ladění:"
        )
        lbl_conn_desc.setStyleSheet("font-size: 12px; color: #475569; line-height: 1.4;")
        conn_layout.addWidget(lbl_conn_desc)

        conn_form = QFormLayout()
        conn_form.setSpacing(12)

        port_box = QHBoxLayout()
        self.txt_connect_port = QLineEdit()
        self.txt_connect_port.setFixedHeight(38)
        self.txt_connect_port.setPlaceholderText("např. 41235")

        self.btn_scan = QPushButton("🔍 Najít otevřený port")
        self.btn_scan.setFixedHeight(38)
        self.btn_scan.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_scan.setStyleSheet(f"""
            QPushButton {{
                background-color: #ffffff;
                color: {SCG_DARK_BLUE};
                font-weight: bold;
                border: 1.5px solid #cbd5e1;
                border-radius: 8px;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background-color: #f1f5f9;
                border-color: {SCG_BLUE};
            }}
        """)
        self.btn_scan.clicked.connect(self._run_scan)
        port_box.addWidget(self.txt_connect_port, stretch=1)
        port_box.addWidget(self.btn_scan)

        lbl_cport = QLabel("Port pro připojení:")
        lbl_cport.setStyleSheet(f"font-weight: 800; color: {SCG_DARK_BLUE}; font-size: 13px;")
        conn_form.addRow(lbl_cport, port_box)
        conn_layout.addLayout(conn_form)

        self.btn_connect = QPushButton("⚡  Připojit telefon přes Wi-Fi (ADB Connect)")
        self.btn_connect.setFixedHeight(44)
        self.btn_connect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_connect.setStyleSheet(f"""
            QPushButton {{
                background-color: {SCG_DARK_BLUE};
                color: {TEXT_ON_DARK_BLUE};
                font-weight: 800;
                font-size: 14px;
                border-radius: 8px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #282766;
            }}
        """)
        self.btn_connect.clicked.connect(self._run_connect)
        conn_layout.addWidget(self.btn_connect)

        layout.addWidget(group_connect)

        # ----------------------------------------------------
        # 4. KARTA: Aktuální stav připojení
        # ----------------------------------------------------
        group_status = QGroupBox("4. Aktuální stav připojení")
        group_status.setStyleSheet(CARD_STYLE)
        status_layout = QVBoxLayout(group_status)
        status_layout.setSpacing(12)

        self.lbl_status = QLabel("Ověřuji stav ADB...")
        self.lbl_status.setStyleSheet("font-size: 13px; font-weight: 800; color: #475569; padding: 4px 0;")
        status_layout.addWidget(self.lbl_status)

        status_btn_bar = QHBoxLayout()
        status_btn_bar.setSpacing(10)

        btn_refresh = QPushButton("🔄 Obnovit stav")
        btn_refresh.setFixedHeight(36)
        btn_refresh.setStyleSheet("font-weight: bold; padding: 0 14px;")
        btn_refresh.clicked.connect(self._refresh_status)

        btn_disconnect = QPushButton("Odpojit ADB")
        btn_disconnect.setFixedHeight(36)
        btn_disconnect.setStyleSheet("color: #dc2626; font-weight: bold; padding: 0 14px;")
        btn_disconnect.clicked.connect(self._disconnect)

        status_btn_bar.addWidget(btn_refresh)
        status_btn_bar.addWidget(btn_disconnect)
        status_btn_bar.addStretch()
        status_layout.addLayout(status_btn_bar)

        layout.addWidget(group_status)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll, stretch=1)

        # ----------------------------------------------------
        # Spodní zavírací tlačítko
        # ----------------------------------------------------
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("border-color: #e2e8f0;")
        main_layout.addWidget(sep)

        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()

        btn_close = QPushButton("Hotovo / Zavřít okno")
        btn_close.setFixedHeight(44)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {SCG_DARK_BLUE};
                color: {TEXT_ON_DARK_BLUE};
                font-weight: 800;
                font-size: 13px;
                border-radius: 8px;
                border: none;
                padding: 0 28px;
            }}
            QPushButton:hover {{
                background-color: #282766;
            }}
        """)
        btn_close.clicked.connect(self.accept)
        bottom_bar.addWidget(btn_close)
        main_layout.addLayout(bottom_bar)

    def _start_qr_listener(self) -> None:
        """Spustí mDNS naslouchání a vygeneruje unikátní QR kód pro spárování."""
        self._stop_qr_listener()

        # Generování náhodného 6místného párovacího kódu a jména služby
        svc_name = f"callcenter-{random.randint(1000, 9999)}"
        pass_code = f"{random.randint(100000, 999999)}"
        qr_text = f"WIFI:T:ADB;S:{svc_name};P:{pass_code};;"

        # Vykreslení QR kódu do UI
        pixmap = generate_qr_pixmap(qr_text, size=220)
        self.lbl_qr_image.setPixmap(pixmap)
        self.lbl_qr_status.setText("⏳ Čekám na naskenování QR kódu kamerou telefonu...")
        self.lbl_qr_status.setStyleSheet(
            "font-size: 13px; font-weight: 800; color: #0284c7; background-color: #f0f9ff; "
            "padding: 8px 14px; border-radius: 8px; border: 1px solid #bae6fd;"
        )

        # Spuštění workera pro příjem mDNS hlášení
        self.qr_thread = QThread(self)
        self.qr_worker = AdbQrWorker(self.phone, svc_name, pass_code)
        self.qr_worker.moveToThread(self.qr_thread)

        self.qr_thread.started.connect(self.qr_worker.start_listening)
        self.qr_worker.pairing_detected.connect(self._on_qr_pairing_detected)
        self.qr_worker.pairing_finished.connect(self._on_qr_pairing_finished)
        self.qr_worker.auto_connected.connect(self._on_qr_auto_connected)
        self.qr_worker.finished.connect(self.qr_thread.quit)

        def cleanup():
            # Vynulovat reference aby se předešlo přístupu k smazaným C++ objektům
            self.qr_worker = None
            self.qr_thread = None

        self.qr_thread.finished.connect(cleanup)
        self.qr_thread.start()

    def _stop_qr_listener(self) -> None:
        worker = self.qr_worker
        thread = self.qr_thread
        self.qr_worker = None
        self.qr_thread = None

        try:
            if worker:
                worker.stop()
        except (RuntimeError, AttributeError):
            pass

        try:
            if thread and thread.isRunning():
                thread.quit()
                thread.wait(1000)
        except (RuntimeError, AttributeError):
            pass

    def _regenerate_qr(self) -> None:
        self._start_qr_listener()

    def _on_qr_pairing_detected(self, ip: str, port: int) -> None:
        self.txt_ip.setText(ip)
        self.lbl_qr_status.setText(f"🔄 Telefon detekován na {ip}:{port}, probíhá párování...")
        self.lbl_qr_status.setStyleSheet(
            "font-size: 13px; font-weight: 800; color: #d97706; background-color: #fef3c7; "
            "padding: 8px 14px; border-radius: 8px; border: 1px solid #fde68a;"
        )

    def _on_qr_pairing_finished(self, ok: bool, msg: str) -> None:
        if ok:
            self.lbl_qr_status.setText("✅ Úspěšně spárováno! Připojuji k telefonu...")
            self.lbl_qr_status.setStyleSheet(
                "font-size: 13px; font-weight: 800; color: #059669; background-color: #ecfdf5; "
                "padding: 8px 14px; border-radius: 8px; border: 1px solid #a7f3d0;"
            )
        else:
            self.lbl_qr_status.setText(f"❌ Párování selhalo: {msg}")
            self.lbl_qr_status.setStyleSheet(
                "font-size: 13px; font-weight: 800; color: #dc2626; background-color: #fef2f2; "
                "padding: 8px 14px; border-radius: 8px; border: 1px solid #fca5a5;"
            )
        self._refresh_status()

    def _on_qr_auto_connected(self, ok: bool, msg: str) -> None:
        if ok:
            self.lbl_qr_status.setText("🎉 Telefon je úspěšně spárován a PŘIPOJEN přes Wi-Fi!")
            self.lbl_qr_status.setStyleSheet(
                "font-size: 13px; font-weight: 800; color: #059669; background-color: #d1fae5; "
                "padding: 8px 14px; border-radius: 8px; border: 1.5px solid #10b981;"
            )
            self.device_connected.emit()
            QMessageBox.information(
                self,
                "Hotovo!",
                "Telefon byl úspěšně spárován přes QR kód a připojen k ADB přes Wi-Fi!\nNyní můžete volat i automaticky zavěšovat.",
            )
        else:
            self.lbl_qr_status.setText(f"⚠️ Spárováno, ale připojení vyžaduje zadat port z displeje.")
        self._refresh_status()

    def _start_worker(self, fn) -> tuple[QThread, AdbAsyncWorker]:
        self.progress_bar.setVisible(True)
        thread = QThread(self)
        worker = AdbAsyncWorker(self.phone)
        worker.moveToThread(thread)
        self._active_threads.add(thread)

        thread.started.connect(fn)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)

        def cleanup():
            self.progress_bar.setVisible(False)
            self._active_threads.discard(thread)

        thread.finished.connect(cleanup)
        thread.finished.connect(thread.deleteLater)
        return thread, worker

    def _detect_ip(self) -> None:
        ip = self.phone.get_kdeconnect_ip()
        if ip:
            self.txt_ip.setText(ip)
            QMessageBox.information(self, "IP detekována", f"Z KDE Connect byla načtena IP adresa: {ip}")
        else:
            QMessageBox.warning(self, "Chyba", "Nepodařilo se automaticky zjistit IP z KDE Connect. Zadejte ji ručně.")

    def _run_pair(self) -> None:
        ip = self.txt_ip.text().strip()
        port = self.txt_pair_port.text().strip()
        code = self.txt_pair_code.text().strip()

        if not ip or not port or not code:
            QMessageBox.warning(self, "Chybějící údaje", "Zadejte IP adresu, párovací port i 6místný párovací kód z displeje.")
            return

        self.btn_pair.setEnabled(False)
        thread, worker = self._start_worker(lambda: worker.do_pair(ip, port, code))
        worker.pair_done.connect(self._on_pair_done)
        thread.finished.connect(lambda: self.btn_pair.setEnabled(True))
        thread.start()

    def _on_pair_done(self, ok: bool, msg: str) -> None:
        if ok:
            QMessageBox.information(self, "Spárováno", f"{msg}\nNyní zadejte port pro připojení a klikněte na 'Připojit'.")
        else:
            QMessageBox.warning(self, "Chyba párování", msg)
        self._refresh_status()

    def _run_scan(self) -> None:
        ip = self.txt_ip.text().strip()
        if not ip:
            QMessageBox.warning(self, "Chyba", "Zadejte nejprve IP adresu telefonu.")
            return

        self.btn_scan.setEnabled(False)
        thread, worker = self._start_worker(lambda: worker.do_scan(ip))
        worker.scan_done.connect(self._on_scan_done)
        thread.finished.connect(lambda: self.btn_scan.setEnabled(True))
        thread.start()

    def _on_scan_done(self, open_ports: List[int]) -> None:
        if open_ports:
            port = str(open_ports[0])
            self.txt_connect_port.setText(port)
            QMessageBox.information(
                self,
                "Port nalezen!",
                f"Na telefonu byl nalezen otevřený port: {port}\nByl automaticky doplněn do pole pro připojení.",
            )
        else:
            QMessageBox.information(
                self,
                "Skenování dokončeno",
                "Na telefonu nebyl automaticky nalezen žádný otevřený port.\n"
                "Ujistěte se, že je Bezdrátové ladění v telefonu ZAPNUTÉ, a opište port z displeje ručně.",
            )

    def _run_connect(self) -> None:
        ip = self.txt_ip.text().strip()
        port = self.txt_connect_port.text().strip()

        if not ip or not port:
            QMessageBox.warning(self, "Chyba", "Zadejte IP adresu i port pro připojení.")
            return

        self.btn_connect.setEnabled(False)
        thread, worker = self._start_worker(lambda: worker.do_connect(ip, port))
        worker.connect_done.connect(self._on_connect_done)
        thread.finished.connect(lambda: self.btn_connect.setEnabled(True))
        thread.start()

    def _on_connect_done(self, ok: bool, msg: str) -> None:
        if ok:
            QMessageBox.information(self, "Úspěšně připojeno!", f"{msg}\nTelefon je nyní připraven na fyzické vytáčení i zavěšování.")
            self.device_connected.emit()
        else:
            QMessageBox.warning(self, "Chyba připojení", msg)
        self._refresh_status()

    def _disconnect(self) -> None:
        self.phone.disconnect_wireless()
        self._refresh_status()
        self.device_connected.emit()

    def _refresh_status(self) -> None:
        devices = self.phone.get_adb_devices()
        if devices:
            dev_str = ", ".join(devices)
            self.lbl_status.setText(f"🟢 PŘIPOJENO K ADB: {dev_str}")
            self.lbl_status.setStyleSheet("font-size: 13px; font-weight: 800; color: #059669; padding: 4px 0;")
        else:
            self.lbl_status.setText("🔴 Není připojeno žádné ADB zařízení.")
            self.lbl_status.setStyleSheet("font-size: 13px; font-weight: 800; color: #dc2626; padding: 4px 0;")

    def closeEvent(self, event) -> None:
        self._stop_qr_listener()
        super().closeEvent(event)

    def reject(self) -> None:
        self._stop_qr_listener()
        super().reject()

    def accept(self) -> None:
        self._stop_qr_listener()
        super().accept()
