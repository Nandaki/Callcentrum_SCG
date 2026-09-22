from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict


@dataclass
class AppConfig:
    # Telefon a směrování (KDE Connect & ADB)
    kdeconnect_device_id: str = "6dfda881bfce4dd28b0348f148b6e2da"
    kdeconnect_device_name: str = "Galaxy S24 Ultra"
    adb_device_id: str = ""
    call_timeout_seconds: int = 30
    sip_domain: str = "sip.odorik.cz"
    zoiper_package: str = "com.zoiper.android.app"
    silent_sms_template: str = (
        "Dobrý den, zkoušeli jsme se vám dovolat z týmu studentských projektů Prezentiáda a pIšQworky. "
        "Podrobnosti vám posíláme na e-mail. Přejeme hezký den! (SCG)"
    )
    smtp_user: str = "lalik@scg.cz"

    # Vzhled a téma
    theme_mode: str = "dark"

    # Google OAuth & Google Sheets
    google_sheet_url: str = ""
    google_sheet_id: str = ""
    worksheet_name: str = ""
    header_row: int = 11
    oauth_client_secret_path: str = "credentials/credentials.json"
    oauth_token_path: str = "credentials/token.json"

    # Mapování sloupců: klíč je název pole v aplikaci, hodnota je název sloupce v Google Sheetu
    # např. {"name": "Název školy", "phone": "Telefon", "city": "Město", ...}
    column_mapping: Dict[str, str] = field(default_factory=lambda: {
        "name": "",
        "city": "",
        "contact_person": "",
        "phone": "",
        "email": "",
        "previous_notes": "",
        "status": "",
        "operator_note": "",
        "timestamp": "",
    })

    @classmethod
    def load(cls, path: Path | str | None = None) -> AppConfig:
        config_path = Path(path) if path else Path(__file__).resolve().parent.parent / "config" / "settings.json"
        if not config_path.exists():
            config = cls()
            config.save(config_path)
            return config

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Sloučení existujících polí
            valid_fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
            return cls(**valid_fields)
        except Exception as e:
            print(f"[Config] Chyba při načítání konfigurace ({e}), použity výchozí hodnoty.")
            return cls()

    def save(self, path: Path | str | None = None) -> None:
        config_path = Path(path) if path else Path(__file__).resolve().parent.parent / "config" / "settings.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
