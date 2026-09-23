"""
Linear-style design system and dynamic Theme Engine for Students Can Grow (SCG).
Supports Dark Mode and Light Mode with high contrast, crisp typography, and zero emoji clutter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
from PySide6.QtCore import QObject, Signal


# SCG Brand Colors
SCG_BLUE = "#5d9be6"
SCG_GREEN = "#5dd0a6"
SCG_RED = "#ff7f7f"
SCG_DARK_BLUE = "#34337e"

# Backwards compatibility constants
TEXT_DARK_NAVY = "#34337e"
TEXT_ON_GREEN = "#0f3829"
TEXT_ON_RED = "#4a0d0d"
TEXT_ON_BLUE = "#ffffff"
TEXT_ON_DARK_BLUE = "#ffffff"


@dataclass(frozen=True)
class ThemeTokens:
    name: str
    is_dark: bool

    # Backgrounds
    bg_app: str
    bg_card: str
    bg_card_secondary: str
    bg_input: str
    bg_hover: str
    bg_active: str

    # Borders
    border_subtle: str
    border_card: str
    border_focus: str

    # Text
    text_primary: str
    text_secondary: str
    text_muted: str
    text_dimmed: str

    # Key / Badge
    kbd_bg: str
    kbd_text: str
    kbd_border: str

    # Accent states
    accent_blue: str
    accent_blue_subtle: str
    accent_blue_text: str

    accent_green: str
    accent_green_subtle: str
    accent_green_text: str

    accent_red: str
    accent_red_subtle: str
    accent_red_text: str

    accent_amber: str
    accent_amber_subtle: str
    accent_amber_text: str

    # Buttons
    btn_primary_bg: str
    btn_primary_hover: str
    btn_primary_text: str

    btn_secondary_bg: str
    btn_secondary_hover: str
    btn_secondary_border: str
    btn_secondary_text: str

    # Status & Scrollbar
    statusbar_bg: str
    statusbar_text: str
    statusbar_border: str
    scrollbar_thumb: str
    scrollbar_thumb_hover: str


DARK_TOKENS = ThemeTokens(
    name="dark",
    is_dark=True,
    bg_app="#0c0e12",
    bg_card="#15181e",
    bg_card_secondary="#1c2028",
    bg_input="#121419",
    bg_hover="#20242f",
    bg_active="#282e3b",
    border_subtle="#222631",
    border_card="#282d3b",
    border_focus="#5d9be6",
    text_primary="#ffffff",
    text_secondary="#cbd5e1",
    text_muted="#94a3b8",
    text_dimmed="#64748b",
    kbd_bg="#1e222c",
    kbd_text="#cbd5e1",
    kbd_border="#333948",
    accent_blue="#5d9be6",
    accent_blue_subtle="#132438",
    accent_blue_text="#93c5fd",
    accent_green="#5dd0a6",
    accent_green_subtle="#0e2a22",
    accent_green_text="#6ee7b7",
    accent_red="#ff7f7f",
    accent_red_subtle="#331414",
    accent_red_text="#fca5a5",
    accent_amber="#f59e0b",
    accent_amber_subtle="#2e1d08",
    accent_amber_text="#fcd34d",
    btn_primary_bg="#5d9be6",
    btn_primary_hover="#4a8cd9",
    btn_primary_text="#ffffff",
    btn_secondary_bg="#1c2028",
    btn_secondary_hover="#242934",
    btn_secondary_border="#2d3342",
    btn_secondary_text="#e2e8f0",
    statusbar_bg="#0f1116",
    statusbar_text="#94a3b8",
    statusbar_border="#1e222c",
    scrollbar_thumb="#2e3544",
    scrollbar_thumb_hover="#3e475b",
)

LIGHT_TOKENS = ThemeTokens(
    name="light",
    is_dark=False,
    bg_app="#f8fafc",
    bg_card="#ffffff",
    bg_card_secondary="#f1f5f9",
    bg_input="#ffffff",
    bg_hover="#f1f5f9",
    bg_active="#e2e8f0",
    border_subtle="#e2e8f0",
    border_card="#cbd5e1",
    border_focus="#2563eb",
    text_primary="#0f172a",
    text_secondary="#475569",
    text_muted="#64748b",
    text_dimmed="#94a3b8",
    kbd_bg="#f1f5f9",
    kbd_text="#334155",
    kbd_border="#cbd5e1",
    accent_blue="#2563eb",
    accent_blue_subtle="#eff6ff",
    accent_blue_text="#1e40af",
    accent_green="#059669",
    accent_green_subtle="#ecfdf5",
    accent_green_text="#065f46",
    accent_red="#dc2626",
    accent_red_subtle="#fef2f2",
    accent_red_text="#991b1b",
    accent_amber="#d97706",
    accent_amber_subtle="#fffbeb",
    accent_amber_text="#92400e",
    btn_primary_bg="#34337e",
    btn_primary_hover="#282766",
    btn_primary_text="#ffffff",
    btn_secondary_bg="#ffffff",
    btn_secondary_hover="#f8fafc",
    btn_secondary_border="#cbd5e1",
    btn_secondary_text="#1e293b",
    statusbar_bg="#ffffff",
    statusbar_text="#64748b",
    statusbar_border="#e2e8f0",
    scrollbar_thumb="#cbd5e1",
    scrollbar_thumb_hover="#94a3b8",
)


def generate_stylesheet(t: ThemeTokens) -> str:
    """Generates the full modern Linear-styled Qt stylesheet for the given tokens."""
    return f"""
QMainWindow, QDialog {{
    background-color: {t.bg_app};
    color: {t.text_primary};
}}

QWidget {{
    color: {t.text_primary};
}}

/* Typography defaults */
QLabel {{
    color: {t.text_primary};
    font-size: 13px;
}}

/* Inputs & Textareas */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {{
    background-color: {t.bg_input};
    border: 1px solid {t.border_subtle};
    border-radius: 6px;
    padding: 7px 10px;
    color: {t.text_primary};
    font-size: 13px;
    selection-background-color: {t.accent_blue};
    selection-color: #ffffff;
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1.5px solid {t.border_focus};
    background-color: {t.bg_input};
}}

QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
    background-color: {t.bg_hover};
    color: {t.text_muted};
    border-color: {t.border_subtle};
}}

/* Buttons */
QPushButton {{
    font-size: 13px;
    font-weight: 600;
    border-radius: 6px;
    padding: 7px 14px;
    background-color: {t.btn_secondary_bg};
    color: {t.btn_secondary_text};
    border: 1px solid {t.btn_secondary_border};
}}

QPushButton:hover {{
    background-color: {t.btn_secondary_hover};
    border-color: {t.border_focus};
}}

QPushButton:pressed {{
    background-color: {t.bg_active};
}}

QPushButton:disabled {{
    background-color: {t.bg_hover};
    color: {t.text_dimmed};
    border-color: {t.border_subtle};
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {t.scrollbar_thumb};
    min-height: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {t.scrollbar_thumb_hover};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    background: transparent;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background: {t.scrollbar_thumb};
    min-width: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {t.scrollbar_thumb_hover};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
    background: transparent;
}}

/* GroupBox as clean Linear Card */
QGroupBox {{
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: {t.text_muted};
    border: 1px solid {t.border_card};
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 14px;
    background-color: {t.bg_card};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 12px;
    color: {t.text_muted};
    background-color: {t.bg_card};
}}

/* Tabs */
QTabWidget::pane {{
    border: 1px solid {t.border_card};
    border-radius: 8px;
    background-color: {t.bg_card};
    top: -1px;
}}

QTabBar::tab {{
    background-color: transparent;
    color: {t.text_secondary};
    font-size: 13px;
    font-weight: 600;
    padding: 9px 18px;
    margin-right: 2px;
    border-bottom: 2px solid transparent;
}}

QTabBar::tab:selected {{
    color: {t.accent_blue};
    border-bottom: 2px solid {t.accent_blue};
}}

QTabBar::tab:hover:!selected {{
    color: {t.text_primary};
    background-color: {t.bg_hover};
    border-radius: 6px;
}}

/* Status Bar */
QStatusBar {{
    background-color: {t.statusbar_bg};
    color: {t.statusbar_text};
    font-size: 12px;
    font-weight: 500;
    border-top: 1px solid {t.statusbar_border};
    padding: 2px 8px;
}}

/* ToolTip */
QToolTip {{
    background-color: {t.bg_card_secondary};
    color: {t.text_primary};
    border: 1px solid {t.border_card};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}
"""


class ThemeManager(QObject):
    """Singleton-like manager for dynamic theme switching across the entire application."""

    theme_changed = Signal(str)  # emits "dark" or "light"

    def __init__(self):
        super().__init__()
        self._current_mode = "dark"

    @property
    def mode(self) -> str:
        return self._current_mode

    @property
    def tokens(self) -> ThemeTokens:
        return DARK_TOKENS if self._current_mode == "dark" else LIGHT_TOKENS

    def set_theme(self, mode: str) -> None:
        target = "light" if mode == "light" else "dark"
        if self._current_mode != target:
            self._current_mode = target
            self.theme_changed.emit(target)

    def toggle_theme(self) -> str:
        new_mode = "light" if self._current_mode == "dark" else "dark"
        self.set_theme(new_mode)
        return new_mode

    def get_stylesheet(self) -> str:
        return generate_stylesheet(self.tokens)


# Global singleton instance
theme_manager = ThemeManager()

# Legacy default stylesheet
APP_STYLE = generate_stylesheet(DARK_TOKENS)
