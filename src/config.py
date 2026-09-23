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
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    smtp_ssl: bool = True
    smtp_password: str = ""
    operator_phone: str = "+420 777 825 705"
    email_subject_template: str = "Pojďte se zapojit do pIšQworek – {school_name}"
    email_body_template: str = (
        "Na základě dnešní telefonické domluvy Vám posílám bližší informace o studentské soutěži pIšQworky.\n\n"
        "Jsme celorepubliková soutěž v oblíbené studentské hře piškvorky. Každý rok se naší soutěže účastní "
        "na 7 000 soutěžících z gymnázií, průmyslových a obchodních škol, ale také učilišť. Studenti soutěží v týmech – "
        "základní školy v tříčlenných, střední školy v pětičlenných. Nejdříve se účastní oblastního turnaje "
        "(jejich seznam najdete na https://pisqworky.cz/turnaje), ze kterého mohou postoupit do turnaje krajského. "
        "Na ty nejlepší pak čeká Grandfinále v Brně. Pro opravdu zapálené piškvorkáře pořádáme také turnaje jednotlivců.\n\n"
        "Před přihlášením týmů i jednotlivců doporučujeme uspořádat školní turnaj. Pro soutěžící je to příležitost "
        "k tréninku, zároveň vám pomůže zapojit více studentů a sestavit tak opravdu ten nejsilnější tým. "
        "Jak na organizaci školního turnaje se dozvíte na našem webu https://pisqworky.cz/skolni-turnaj, "
        "kde se můžete přihlásit na náš webinář / najdete také záznam z našeho webináře.\n\n"
        "Harmonogram soutěže týmů:\n"
        "• 16. října\t\tuzávěrka přihlášek\n"
        "• 2.–20. listopadu\t\toblastní turnaje\n"
        "• 23.–27. listopadu\tkrajské turnaje\n"
        "• 10. prosince\t\tGrandfinále ZŠ\n"
        "• 11. prosince\t\tGrandfinále SŠ\n\n"
        "Harmonogram soutěže jednotlivců:\n"
        "• 16. října\t\tuzávěrka přihlášek\n"
        "• 1. - 7. listopadu\t\t1. online úroveň\n"
        "• 11. - 18. listopadu\t2. online úroveň\n"
        "• Datum bude upřesněno\tGrandfinále\n\n"
        "Zároveň si Vás dovolujeme upozornit, že jedním z našich letošních partnerů je i Nadace O2, díky čemuž "
        "si se svými studenty můžete zcela zdarma zahrát interaktivní hru zaměřenou na kyberbezpečnost (https://nadaceo2.cz).\n\n"
        "Děkujeme, že máte o pIšQworky zájem a že své studenty podporujete v netradičních formách rozvoje. "
        "I díky Vám můžeme dělat školství zábavnější a inkluzivnější.\n\n"
        "S přáním hezkého dne,\n\n"
        "S pozdravem\n\n"
        "{operator_name}\n"
        "Člen marketingového týmu\n"
        "Mobil: {operator_phone}\n\n"
        "students can grow, z. s.\n"
        "Hra školou\n\n"
        "Web: https://pisqworky.cz | Instagram: https://instagram.com/pisqworky | Facebook: https://facebook.com/pisqworky"
    )
    email_html_template: str = ""

    # Vzhled a téma
    theme_mode: str = "dark"

    # Google OAuth & Google Sheets
    google_sheet_url: str = ""
    google_sheet_id: str = ""
    worksheet_name: str = ""
    header_row: int = 11
    oauth_client_secret_path: str = "credentials/credentials.json"
    oauth_token_path: str = "credentials/token.json"

    # Jméno operátora (pro sloupec Volá)
    operator_name: str = "Michal Lalík"

    # Mapování sloupců: klíč je název pole v aplikaci, hodnota je název sloupce v Google Sheetu
    column_mapping: Dict[str, str] = field(default_factory=lambda: {
        "caller": "Volá",
        "called": "Zavoláno",
        "status": "Stav",
        "operator_note": "Poznámky",
        "name": "nazev",
        "city": "mesto",
        "contact_person": "kontakt_jmeno",
        "email": "email_skoly",
        "phone": "telefon_skoly",
        "previous_notes": "projekty_5let",
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
