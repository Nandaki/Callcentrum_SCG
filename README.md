# Call Centrum — SCG

Interní desktopová aplikace pro operátory call centra Student Cyber Games (Prezentiáda, pIšQworky). Slouží k rychlému obvolávání škol, evidenci výsledků hovorů a automatickému zápisu do sdílených Google tabulek.

Aplikace se bezdrátově propojuje s telefonem s Androidem přes Wi-Fi (ADB) a umožňuje vytáčet hovory a odesílat automatické SMS zprávy při nezastižení bez nutnosti sahat na telefon.

---

## Hlavní funkce

- **Přímé volání přes telefon (Wi-Fi ADB):** Vytáčení hovorů přes mobilní síť (SIM) jedním kliknutím nebo stiskem mezerníku.
- **Automatická SMS při nezastižení:** Pokud hovor do 30 sekund nikdo nezvedne, aplikace hovor automaticky zavěsí a pošle přednastavenou SMS. SMS lze odeslat i manuálně tlačítkem.
- **Obousměrná synchronizace s Google Sheets:**
  - Načítání kontaktů z vybraného listu tabulky (podpora vlastního řádku záhlaví a dynamického mapování sloupců).
  - Zápis výsledků hovoru (stav, poznámka, čas volání, odškrtnutí checkboxu).
- **Párování přes QR kód:** Bezdrátové připojení telefonu přes Android Wireless Debugging (podpora skenování QR kódu nebo ručního zadání portu a kódu).
- **Jednotné nastavení:** Přehledný konfigurační dialog pro Google OAuth, tabulku, Wi-Fi ADB, šablonu SMS a další integrace.

---

## Požadavky

- **OS:** Linux (testováno na Arch Linux) nebo Windows
- **Python:** 3.10+ (vyvíjeno a testováno na Python 3.14)
- **Telefon:** Android 11+ se zapnutým Bezdrátovým laděním (Wireless Debugging) v možnostech pro vývojáře
- **ADB:** Nainstalovaný balíček `android-tools` (`adb`)
- **Google účet:** Projekt v Google Cloud Console s povoleným Google Sheets API a staženým souborem `credentials.json` (OAuth 2.0 Client ID typu Desktop application).

---

## Instalace a zprovoznění

### 1. Klonování repozitáře

```bash
git clone https://github.com/Nandaki/Callcentrum_SCG.git
cd Callcentrum_SCG
```

### 2. Vytvoření virtuálního prostředí a instalace závislostí

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Příprava Google OAuth přihlašovacích údajů

1. V [Google Cloud Console](https://console.cloud.google.com/) vytvořte projekt a povolte **Google Sheets API** a **Google Drive API**.
2. Vytvořte OAuth 2.0 Client ID (typ *Desktop application*) a stáhněte JSON soubor.
3. Uložte jej do složky `credentials/credentials.json`:
   ```bash
   mkdir -p credentials
   cp /cesta/k/stazenemu/client_secret.json credentials/credentials.json
   ```

### 4. Spuštění aplikace

```bash
./venv/bin/python src/main.py
```

---

## První nastavení v aplikaci

Při prvním spuštění klikněte v horní liště na **⚙️ Globální nastavení**:

1. **Google Tabulka:**
   - Klikněte na *Přihlásit se přes Google účet* (otevře se prohlížeč pro udělení přístupu).
   - Vložte odkaz nebo ID vaší Google tabulky a klikněte na *Načíst sešit*.
   - Vyberte list (např. `CZ SŠ` nebo `CZ ZŠ`), zkontrolujte číslo řádku se záhlavím (např. 11) a klikněte na *Načíst sloupce*.
   - Zkontrolujte propojení sloupců a uložte.

2. **Telefon & Wi-Fi ADB:**
   - Na telefonu přejděte do **Nastavení -> Možnosti pro vývojáře -> Bezdrátové ladění**.
   - Zvolte *Spárovat zařízení pomocí QR kódu* a namiřte fotoaparát na obrazovku monitoru s vygenerovaným QR kódem.
   - Aplikace telefon automaticky spáruje a připojí.

3. **SMS zprávy:**
   - Zkontrolujte a upravte šablonu zprávy, která se posílá při nezvednutí hovoru.
   - Můžete vyzkoušet odeslání testovací SMS na vlastní číslo.

---

## Ovládání a klávesové zkratky

- `Mezerník` — Zahájit hovor (ze stavu Připraveno) / Označit hovor jako spojený (během vyzvánění)
- `Escape` — Okamžitě zavěsit hovor
- `Klepnutí na štítek tabulky v liště` — Rychlé otevření nastavení tabulky
- `Klepnutí na štítek telefonu v liště` — Rychlé otevření nastavení telefonu / ADB

*Poznámka: Klávesová zkratka mezerníku je automaticky pozastavena, pokud operátor zrovna píše poznámku do textového pole.*

---

## Struktura projektu

```text
callcetrum/
├── config/
│   ├── settings.example.json   # Vzorový konfigurační soubor
│   └── settings.json           # Lokální konfigurace (v .gitignore)
├── credentials/                # Lokální OAuth tokeny a klíče (v .gitignore)
├── src/
│   ├── core/
│   │   ├── dialer.py           # Řízení telefonu, hovory, ADB příkazy, SMS
│   │   └── sheets.py           # Google Sheets API a OAuth autentizace
│   ├── models/
│   │   └── school.py           # Datové modely (SchoolContact, CallResult)
│   ├── ui/
│   │   ├── main_window.py      # Hlavní okno operátora
│   │   ├── settings_dialog.py  # Globální nastavení (Tabulka, ADB, SMS, Integrace)
│   │   ├── theme.py            # Barevné schéma a vizuální styl SCG
│   │   └── widgets/
│   │       ├── call_control.py # Panel ovládání hovoru (časovač, tlačítka)
│   │       ├── result_panel.py # Panel pro zápis výsledku a tlačítko SMS
│   │       └── school_card.py  # Karta s informacemi o škole a historii
│   └── main.py                 # Vstupní bod aplikace
├── requirements.txt            # Python závislosti
└── README.md
```

---

## Licence

Interní nástroj vyvinutý pro potřeby studentských soutěží spolku Student Cyber Games.

