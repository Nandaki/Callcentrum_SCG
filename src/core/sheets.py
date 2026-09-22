from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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

    def fetch_contacts(
        self,
        spreadsheet_id: str,
        worksheet_name: str,
        column_mapping: Dict[str, str],
        header_row: int = 11,
        only_uncalled: bool = True,
    ) -> List[SchoolContact]:
        """
        Stáhne řádky tabulky začínající za řádkem záhlaví (header_row + 1).
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

        contacts: List[SchoolContact] = []

        # Datové řádky začínají na header_row + 1 (1-indexed)
        for row_offset, row in enumerate(all_values[header_row:], start=header_row + 1):
            def get_val(field_key: str) -> str:
                mapped_col_name = column_mapping.get(field_key)
                if not mapped_col_name:
                    return ""
                col_idx = col_indices.get(mapped_col_name)
                if col_idx is not None and col_idx < len(row):
                    return str(row[col_idx]).strip()
                return ""

            name = get_val("name")
            phone = get_val("phone")

            if not name and not phone:
                continue

            status = get_val("status")

            # Kontrola zda již bylo voláno (buď podle sloupce status nebo sloupce Zavoláno)
            zavolano_idx = col_indices.get("Zavoláno")
            is_already_called = False
            if zavolano_idx is not None and zavolano_idx < len(row):
                val_zavolano = str(row[zavolano_idx]).upper()
                if val_zavolano in ("TRUE", "ANO", "1"):
                    is_already_called = True

            if only_uncalled and (is_already_called or (status and status not in ("Nevoláno", "Nevyřízeno", ""))):
                continue

            contact = SchoolContact(
                id=row_offset,
                name=name or "Neznámá škola",
                city=get_val("city"),
                contact_person=get_val("contact_person"),
                phone=phone,
                email=get_val("email"),
                previous_notes=get_val("previous_notes"),
                status=status or "Nevoláno",
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
    ) -> None:
        """Zapíše výsledek hovoru, poznámku a čas do příslušných buněk v daném řádku."""
        client = self.get_client()
        sheet = client.open_by_key(spreadsheet_id)
        worksheet = sheet.worksheet(worksheet_name)

        header = [str(c).strip() for c in worksheet.row_values(header_row)]
        col_indices: Dict[str, int] = {name: idx + 1 for idx, name in enumerate(header) if name}

        updates = []

        # 1. Stav hovoru
        status_col = column_mapping.get("status") or "Stav"
        if status_col and status_col in col_indices:
            col_num = col_indices[status_col]
            updates.append({
                "range": gspread.utils.rowcol_to_a1(row_index, col_num),
                "values": [[result.result_type.value]],
            })

        # 2. Nastavení checkboxu 'Zavoláno' na TRUE (pokud sloupec existuje)
        if "Zavoláno" in col_indices:
            col_num = col_indices["Zavoláno"]
            updates.append({
                "range": gspread.utils.rowcol_to_a1(row_index, col_num),
                "values": [["TRUE"]],
            })

        # 3. Operátorská poznámka
        note_col = column_mapping.get("operator_note") or column_mapping.get("previous_notes") or "Poznámky"
        if note_col and note_col in col_indices and result.note:
            col_num = col_indices[note_col]
            updates.append({
                "range": gspread.utils.rowcol_to_a1(row_index, col_num),
                "values": [[result.note]],
            })

        # 4. Čas volání
        time_col = column_mapping.get("timestamp")
        if time_col and time_col in col_indices:
            col_num = col_indices[time_col]
            formatted_time = result.timestamp.strftime("%d.%m.%Y %H:%M")
            updates.append({
                "range": gspread.utils.rowcol_to_a1(row_index, col_num),
                "values": [[formatted_time]],
            })

        if updates:
            worksheet.batch_update(updates)
            print(f"[Sheets] Úspěšně zapsán výsledek do řádku {row_index}.")

