"""
Barevná paleta a vizuální styl SCG (Studentská čtenářská / česko-slovenská gramotnost - Prezentiáda, pIšQworky).

Oficiální SCG barvy:
- Modrá: #5d9be6
- Zelená: #5dd0a6
- Červená: #ff7f7f
- Tmavě modrá: #34337e
"""

# Primární SCG barvy
SCG_BLUE = "#5d9be6"
SCG_GREEN = "#5dd0a6"
SCG_RED = "#ff7f7f"
SCG_DARK_BLUE = "#34337e"

# Kontrastní textové barvy k tlačítkům a podkladům (pro maximální čitelnost)
TEXT_DARK_NAVY = "#34337e"
TEXT_ON_GREEN = "#0f3829"     # Tmavě zelená s vysokým kontrastem na mátově zelené (#5dd0a6)
TEXT_ON_RED = "#4a0d0d"       # Tmavě rudá s vysokým kontrastem na červené (#ff7f7f)
TEXT_ON_BLUE = "#ffffff"      # Bílá na syté modré (#5d9be6)
TEXT_ON_DARK_BLUE = "#ffffff" # Bílá na tmavě modré (#34337e)

# Tóny pozadí a ohraničení
BG_WINDOW = "#f4f6fb"
BG_CARD = "#ffffff"
BORDER_CARD = "#cbd5e1"
BORDER_FOCUSED = "#5d9be6"

# Globální stylesheet pro aplikaci
APP_STYLE = f"""
QMainWindow {{
    background-color: {BG_WINDOW};
}}

QGroupBox {{
    font-size: 14px;
    font-weight: bold;
    color: {SCG_DARK_BLUE};
    border: 1px solid {BORDER_CARD};
    border-radius: 10px;
    margin-top: 12px;
    padding-top: 16px;
    background-color: {BG_CARD};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    left: 12px;
    color: {SCG_DARK_BLUE};
}}

QLabel {{
    color: #1e293b;
}}

QLineEdit, QTextEdit {{
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px;
    color: #0f172a;
    font-size: 13px;
}}

QLineEdit:focus, QTextEdit:focus {{
    border: 1px solid {BORDER_FOCUSED};
    background-color: #fcfdfe;
}}

QRadioButton {{
    font-size: 13px;
    font-weight: 500;
    color: #1e293b;
    spacing: 8px;
}}

QRadioButton::indicator {{
    width: 16px;
    height: 16px;
}}

QRadioButton::indicator:checked {{
    border: 2px solid {SCG_DARK_BLUE};
    background-color: {SCG_DARK_BLUE};
    border-radius: 8px;
}}

QCheckBox {{
    font-size: 13px;
    font-weight: 600;
    color: {SCG_DARK_BLUE};
    spacing: 8px;
}}

QStatusBar {{
    background-color: #ffffff;
    color: {SCG_DARK_BLUE};
    font-weight: 500;
    border-top: 1px solid #e2e8f0;
}}
"""

