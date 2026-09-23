from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class CallState(Enum):
    IDLE = "idle"                # Připraveno, nevolá se
    DIALING = "dialing"          # Vytáčí se (běží 30s odpočet)
    CONNECTED = "connected"      # Spojeno (hovor aktivní, časovač zastaven)
    COMPLETED = "completed"      # Hovor ukončen, čeká se na uložení výsledku


class CallResultType(Enum):
    INTERESTED = "Zaujali jsme"
    NOT_INTERESTED = "Nezájem"
    OK_MAYBE = "Asi ok"
    UNANSWERED = "Nedovoláno"
    SEND_MAIL = "poslat mail"
    CUSTOM = "??"


@dataclass
class SchoolContact:
    id: str | int
    name: str
    city: str
    contact_person: str
    phone: str
    email: str
    project: str = ""
    previous_notes: str = ""
    status: str = "Nevoláno"
    caller: str = ""
    row_index: int = 0

    @property
    def clean_phone(self) -> str:
        """Vrátí normalizované telefonní číslo bez mezer a pomlček."""
        cleaned = re.sub(r"[^\d+]", "", self.phone)
        if cleaned.startswith("00"):
            cleaned = "+" + cleaned[2:]
        elif not cleaned.startswith("+"):
            # Pokud nemá předvolbu, předpokládáme ČR (+420)
            if len(cleaned) == 9:
                cleaned = "+420" + cleaned
        return cleaned

    @property
    def is_slovak(self) -> bool:
        """Indikuje, zda se jedná o slovenské číslo (+421)."""
        return self.clean_phone.startswith("+421")

    @property
    def is_czech(self) -> bool:
        """Indikuje, zda se jedná o české číslo (+420)."""
        return self.clean_phone.startswith("+420")


@dataclass
class CallResult:
    result_type: CallResultType
    note: str = ""
    send_email: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CallSession:
    school: SchoolContact
    state: CallState = CallState.IDLE
    started_at: datetime | None = None
    connected_at: datetime | None = None
    ended_at: datetime | None = None
    result: CallResult | None = None

