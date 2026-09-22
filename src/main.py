#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

# Zajištění kořenového adresáře projektu v sys.path při přímém spuštění `python src/main.py`
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from src.config import AppConfig
from src.ui.main_window import MainWindow


def main() -> int:
    # Povolení High DPI škálování
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Call Centrum")
    app.setApplicationDisplayName("Call Centrum — Students Can Grow")

    # Nastavení čistého systémového fontu
    font = QFont("Inter", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    # Načtení konfigurace
    config = AppConfig.load()

    from src.ui.theme import theme_manager
    theme_manager.set_theme(getattr(config, "theme_mode", "dark") or "dark")
    app.setStyleSheet(theme_manager.get_stylesheet())

    # Vytvoření a zobrazení hlavního okna
    window = MainWindow(config)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

