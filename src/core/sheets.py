from __future__ import annotations

import re
import urllib.parse
from pathlib import Path
from typing import Dict, List, Tuple

import requests

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from ..models.school import CallResult, SchoolContact

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


def extract_spreadsheet_id(url_or_id: str) -> str:
    """Extrahuje ID Google tabulky z URL nebo vrátí původní řetězec, pokud už je to ID."""
    url_or_id = url_or_id.strip()
    match = re.search(r"/spreadsheets/(?:u/\d+/)?d/([a-zA-Z0-9-_]+)", url_or_id)
    if match:
        return match.group(1)
    # Pokud neobsahuje lomítka, může to být přímo ID
    if "/" not in url_or_id and len(url_or_id) > 15:
        return url_or_id
    return url_or_id


class GoogleSheetsService:
    """Služba pro autorizaci přes Google OAuth 2.0 a práci s Google tabulkami."""

    def __init__(self, client_secret_path: str = "credentials/credentials.json", token_path: str = "credentials/token.json"):
        self.client_secret_path = Path(client_secret_path)
        self.token_path = Path(token_path)
        self._client: gspread.Client | None = None
        self._creds: Credentials | None = None

    def is_authenticated(self) -> bool:
        """Zkontroluje, zda máme platné nebo obnovitelné OAuth přihlašovací údaje."""
        try:
            creds = self._get_saved_credentials()
            return creds is not None and (creds.valid or bool(creds.refresh_token))
        except Exception:
            return False

    def get_user_email(self) -> str | None:
        """Vrátí e-mail přihlášeného uživatele (pokud je dostupný v tokenu)."""
        creds = self._get_saved_credentials()
        if creds and hasattr(creds, "id_token") and creds.id_token:
            return creds.id_token.get("email")
        return None

    def _get_saved_credentials(self) -> Credentials | None:
        if self._creds and self._creds.valid:
            return self._creds

        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    # Uložit obnovený token
                    self.token_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.token_path, "w", encoding="utf-8") as token_file:
                        token_file.write(creds.to_json())
                self._creds = creds
                return creds
            except Exception as e:
                print(f"[Sheets] Chyba při načítání tokenu: {e}")
                return None
        return None

    def authenticate_interactive(self) -> gspread.Client:
        """Spustí interaktivní přihlášení v prohlížeči (OAuth Desktop Flow)."""
        if not self.client_secret_path.exists():
            raise FileNotFoundError(
                f"Soubor s OAuth údaji nebyl nalezen na cestě: {self.client_secret_path}\n"
                "Stáhněte si 'credentials.json' (OAuth Client ID - Desktop App) z Google Cloud Console."
            )

        flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secret_path), SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

        # Uložit token pro příště
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.token_path, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

        self._creds = creds
        self._client = gspread.authorize(creds)
        return self._client

    def get_client(self) -> gspread.Client:
        """Vrátí autorizovaného gspread klienta."""
        if self._client:
            return self._client

        creds = self._get_saved_credentials()
        if creds and creds.valid:
            self._client = gspread.authorize(creds)
            return self._client

        return self.authenticate_interactive()

    def get_worksheets(self, spreadsheet_id: str) -> List[str]:
        """Vrátí seznam názvů všech listů v tabulce."""
        client = self.get_client()
        sheet = client.open_by_key(spreadsheet_id)
        return [ws.title for ws in sheet.worksheets()]

    def get_headers(
        self,
        spreadsheet_id: str,
        worksheet_name: str,
        header_row: int | None = None,
    ) -> Tuple[int, List[str]]:
        """
        Načte hlavičky z daného listu.
        Pokud header_row není zadán, pokusí se detekovat řádek se sloupci (např. řádek 11 nebo 3).
        Vrátí tuple: (číslo_řádku, seznam_názvů_sloupců).
        """
        client = self.get_client()
        sheet = client.open_by_key(spreadsheet_id)
        worksheet = sheet.worksheet(worksheet_name)
        rows = worksheet.get_all_values()
        if not rows:
            return 1, []

        # Pokud uživatel zadal konkrétní číslo řádku (1-indexed)
        if header_row and 1 <= header_row <= len(rows):
            r = rows[header_row - 1]
            return header_row, [str(c).strip() for c in r if str(c).strip()]

        # Inteligentní detekce: prohledáme prvních 20 řádků
        keywords = ["nazev", "škola", "skola", "telefon", "volá", "zavoláno", "stav", "mesto", "email"]
        best_row_idx = 0
        best_score = -1

        for idx, r in enumerate(rows[:20]):
            score = sum(1 for cell in r if any(k in str(cell).lower() for k in keywords) and str(cell).strip())
            if score > best_score:
                best_score = score
                best_row_idx = idx

        # Pokud skóre nic nenašlo, vezmeme první neprázdný řádek s alespoň 2 sloupci
        if best_score <= 0:
            for idx, r in enumerate(rows[:20]):
                non_empty = [c for c in r if str(c).strip()]
                if len(non_empty) >= 2:
                    best_row_idx = idx
                    break

        detected_row_num = best_row_idx + 1
        headers = [str(col).strip() for col in rows[best_row_idx] if str(col).strip()]
        return detected_row_num, headers

    def get_organizer_names(self, spreadsheet_id: str) -> List[str]:
        """Načte seznam volajících z listu Tabulka (sloupec B)."""
        try:
            client = self.get_client()
            sheet = client.open_by_key(spreadsheet_id)
            ws_tab = None
            for ws in sheet.worksheets():
                if ws.title.strip().lower() == "tabulka":
                    ws_tab = ws
                    break
            if not ws_tab:
                ws_tab = sheet.worksheet("Tabulka")

            vals = ws_tab.col_values(2)
            names = []
            for val in vals:
                s = str(val).strip()
                if not s:
                    continue
                if s.lower() in ("tabulka volajících", "tabulka volajicich", "volající", "volajici", "jméno", "jmeno", "organizátor", "organizator"):
                    continue
                names.append(s)
            return names or ["Honzík", "Honzík 2"]
        except Exception as e:
            print(f"[Sheets] Chyba při načítání organizátorů z Tabulka sloupec B: {e}")
            return ["Honzík", "Honzík 2"]

    def fetch_contacts(
        self,
        spreadsheet_id: str,
        worksheet_name: str,
        column_mapping: Dict[str, str],
        header_row: int = 11,
        only_uncalled: bool = True,
        operator_name: str = "",
    ) -> List[SchoolContact]:
        """
        Stáhne řádky tabulky začínající za řádkem záhlaví (header_row + 1).
        Filtruje:
        - Zelená pole (školy označené zelenou barvou pozadí nesmí být volány!)
        - Již zavolané školy (checkbox v sloupci Zavoláno/Zav je zaškrtnutý nebo má status)
        - POUZE školy, které má přihlášený volající zapsané na sebe ve sloupci A (Volá)
        """
        client = self.get_client()
        sheet = client.open_by_key(spreadsheet_id)
        worksheet = sheet.worksheet(worksheet_name)

        all_values = worksheet.get_all_values()
        if len(all_values) <= header_row:
            return []

        header = [str(c).strip() for c in all_values[header_row - 1]]
        col_indices: Dict[str, int] = {}
        for idx, col_name in enumerate(header):
            if col_name:
                col_indices[col_name] = idx

        # Detekce zelených polí přes REST API (zkontroluje sloupce A:B)
        is_green_row: Dict[int, bool] = {}
        try:
            creds = self._get_saved_credentials()
            if creds and creds.valid:
                headers = {"Authorization": f"Bearer {creds.token}"}
                safe_range = urllib.parse.quote(f"'{worksheet_name}'!A{header_row}:B")
                url = (
                    f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
                    f"?ranges={safe_range}"
                    "&fields=sheets.data.rowData.values.effectiveFormat.backgroundColor"
                )
                resp = requests.get(url, headers=headers, timeout=12)
                if resp.status_code == 200:
                    raw_rows = resp.json().get("sheets", [{}])[0].get("data", [{}])[0].get("rowData", [])
                    for offset, r in enumerate(raw_rows):
                        row_idx = header_row + offset
                        cells = r.get("values", [])
                        for c in cells:
                            bg = c.get("effectiveFormat", {}).get("backgroundColor", {})
                            if bg.get("green", 0) > 0.7 and bg.get("red", 0) < 0.5:
                                is_green_row[row_idx] = True
                                break
        except Exception as e:
            print(f"[Sheets] Varování při kontrole zelených polí: {e}")

        contacts: List[SchoolContact] = []
        op_clean = operator_name.strip().lower() if operator_name else ""

        for row_offset, row in enumerate(all_values[header_row:], start=header_row + 1):
            # 1. Kontrola zeleného pole
            if is_green_row.get(row_offset, False):
                continue

            def get_val(field_key: str, default_col: str = "") -> str:
                mapped_col_name = column_mapping.get(field_key) or default_col
                if not mapped_col_name:
                    return ""
                col_idx = col_indices.get(mapped_col_name)
                if col_idx is not None and col_idx < len(row):
                    return str(row[col_idx]).strip()
                return ""

            name = get_val("name", "nazev")
            phone = get_val("phone", "telefon_skoly")
            if not name and not phone:
                continue

            # 2. Kontrola zaškrtávacího políčka 'Zavoláno' / 'Zav' (Sloupec B)
            val_called = get_val("called", "Zavoláno") or get_val("called", "Zav")
            if not val_called and 1 < len(row):
                val_called = str(row[1]).strip()

            if val_called.upper() in ("TRUE", "1", "ANO", "CHECKED"):
                continue

            # 3. Kontrola organizátora / volajícího ve sloupci 'Volá' (Sloupec A)
            # Uživatel požaduje mít v aplikaci POUZE školy zapsané na sebe ve sloupci A!
            val_caller = get_val("caller", "Volá")
            if not val_caller and 0 < len(row):
                val_caller = str(row[0]).strip()

            if not val_caller:
                continue

            if not op_clean or val_caller.lower() != op_clean:
                continue

            # 4. Kontrola statusu (Sloupec C)
            status = get_val("status", "Stav")
            if not status and 2 < len(row):
                status = str(row[2]).strip()

            resolved_statuses = ("Zaujali jsme", "Nezájem", "Asi ok", "Nedovoláno", "poslat mail")
            if only_uncalled and status in resolved_statuses:
                continue

            contact = SchoolContact(
                id=row_offset,
                name=name or "Neznámá škola",
                city=get_val("city", "mesto"),
                contact_person=get_val("contact_person", "kontakt_jmeno"),
                phone=phone,
                email=get_val("email", "email_skoly"),
                previous_notes=get_val("previous_notes", "projekty_5let"),
                status=status or "Nevoláno",
                caller=val_caller,
                row_index=row_offset,
            )
            contacts.append(contact)

        return contacts

    def update_call_result(
        self,
        spreadsheet_id: str,
        worksheet_name: str,
        row_index: int,
        column_mapping: Dict[str, str],
        result: CallResult,
        header_row: int = 11,
        operator_name: str = "",
    ) -> None:
        """Zapíše výsledek hovoru, zaškrtne checkbox, nastaví organizátora a poznámku."""
        client = self.get_client()
        sheet = client.open_by_key(spreadsheet_id)
        worksheet = sheet.worksheet(worksheet_name)

        header = [str(c).strip() for c in worksheet.row_values(header_row)]
        col_indices: Dict[str, int] = {name: idx + 1 for idx, name in enumerate(header) if name}

        updates = []

        # 1. Sloupec A ('Volá') - zapíšeme jméno operátora
        caller_col_name = column_mapping.get("caller") or "Volá"
        col_num_a = col_indices.get(caller_col_name, 1)
        if operator_name:
            updates.append({
                "range": gspread.utils.rowcol_to_a1(row_index, col_num_a),
                "values": [[operator_name]],
            })

        # 2. Sloupec B ('Zavoláno' / 'Zav') - zaškrtneme checkbox (TRUE)
        called_col_name = column_mapping.get("called") or "Zavoláno"
        col_num_b = col_indices.get(called_col_name, col_indices.get("Zav", 2))
        updates.append({
            "range": gspread.utils.rowcol_to_a1(row_index, col_num_b),
            "values": [[True]],
        })

        # 3. Sloupec C ('Stav') - zapíšeme výsledek (Zaujali jsme / Nezájem / Asi ok / Nedovoláno / poslat mail)
        status_col_name = column_mapping.get("status") or "Stav"
        col_num_c = col_indices.get(status_col_name, 3)
        updates.append({
            "range": gspread.utils.rowcol_to_a1(row_index, col_num_c),
            "values": [[result.result_type.value]],
        })

        # 4. Sloupec D ('Poznámky') - operátorská poznámka
        note_col_name = column_mapping.get("operator_note") or "Poznámky"
        col_num_d = col_indices.get(note_col_name, 4)
        if result.note:
            updates.append({
                "range": gspread.utils.rowcol_to_a1(row_index, col_num_d),
                "values": [[result.note]],
            })

        # 5. Čas volání (pokud je namapován)
        time_col = column_mapping.get("timestamp")
        if time_col and time_col in col_indices:
            col_num_t = col_indices[time_col]
            formatted_time = result.timestamp.strftime("%d.%m.%Y %H:%M")
            updates.append({
                "range": gspread.utils.rowcol_to_a1(row_index, col_num_t),
                "values": [[formatted_time]],
            })

        if updates:
            worksheet.batch_update(updates, value_input_option="USER_ENTERED")
            print(f"[Sheets] Úspěšně zapsán výsledek do řádku {row_index}: Volá={operator_name}, Zav=TRUE, Stav={result.result_type.value}")

    def update_school_email(
        self,
        spreadsheet_id: str,
        worksheet_name: str,
        row_index: int,
        new_email: str,
        column_mapping: Dict[str, str],
        header_row: int = 11,
    ) -> bool:
        """Zapíše novou e-mailovou adresu do odpovídajícího sloupce (např. email_skoly) v daném řádku."""
        client = self.get_client()
        sheet = client.open_by_key(spreadsheet_id)
        worksheet = sheet.worksheet(worksheet_name)

        header = [str(c).strip() for c in worksheet.row_values(header_row)]
        col_indices: Dict[str, int] = {name: idx + 1 for idx, name in enumerate(header) if name}

        email_col_name = column_mapping.get("email") or "email_skoly"
        col_num = col_indices.get(email_col_name)
        if not col_num:
            for name, idx in col_indices.items():
                if "email" in name.lower() or "e-mail" in name.lower():
                    col_num = idx
                    break

        if not col_num:
            print(f"[Sheets] Sloupec pro e-mail '{email_col_name}' nebyl v záhlaví nalezen.")
            return False

        cell_a1 = gspread.utils.rowcol_to_a1(row_index, col_num)
        worksheet.update([[new_email]], cell_a1, value_input_option="USER_ENTERED")
        print(f"[Sheets] Úspěšně aktualizován e-mail v řádku {row_index} ({cell_a1}): {new_email}")
        return True


