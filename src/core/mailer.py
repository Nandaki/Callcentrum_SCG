from __future__ import annotations

import html
import re
import smtplib
import ssl
import urllib.parse
from email.header import Header
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional, Tuple

from ..config import AppConfig
from ..models.school import SchoolContact


DEFAULT_PISQWORKY_HTML = """<div style="font-family: Arial, Helvetica, sans-serif; font-size: 14px; color: #222222; line-height: 1.5; max-width: 650px;">
  <p>Na základě dnešní telefonické domluvy Vám posílám bližší informace o studentské soutěži <strong>pIšQworky</strong>.</p>

  <p>Jsme celorepubliková soutěž v oblíbené studentské hře piškvorky. Každý rok se naší soutěže účastní na 7 000 soutěžících z gymnázií, průmyslových a obchodních škol, ale také učilišť. Studenti soutěží v týmech – základní školy v tříčlenných, střední školy v pětičlenných. Nejdříve se účastní oblastního turnaje (jejich seznam najdete <a href="https://pisqworky.cz/turnaje" style="color: #1976d2; text-decoration: underline;">zde</a>), ze kterého mohou postoupit do turnaje krajského. Na ty nejlepší pak čeká Grandfinále v Brně. Pro opravdu zapálené piškvorkáře pořádáme také turnaje jednotlivců.</p>

  <p>Před přihlášením týmů i jednotlivců doporučujeme uspořádat školní turnaj. Pro soutěžící je to příležitost k tréninku, zároveň vám pomůže zapojit více studentů a sestavit tak opravdu ten nejsilnější tým. Jak na organizaci školního turnaje se dozvíte na našem <a href="https://pisqworky.cz/skolni-turnaj" style="color: #1976d2; text-decoration: underline;">webu</a>, kde se můžete přihlásit na náš webinář / najdete také záznam z našeho webináře.</p>

  <p style="margin-bottom: 4px;"><strong>Harmonogram soutěže týmů:</strong></p>
  <table style="border-collapse: collapse; margin-left: 12px; margin-bottom: 14px; font-size: 14px;">
    <tr><td style="padding: 2px 18px 2px 0;">• 16. října</td><td>uzávěrka přihlášek</td></tr>
    <tr><td style="padding: 2px 18px 2px 0;">• 2.–20. listopadu</td><td>oblastní turnaje</td></tr>
    <tr><td style="padding: 2px 18px 2px 0;">• 23.–27. listopadu</td><td>krajské turnaje</td></tr>
    <tr><td style="padding: 2px 18px 2px 0;">• 10. prosince</td><td>Grandfinále ZŠ</td></tr>
    <tr><td style="padding: 2px 18px 2px 0;">• 11. prosince</td><td>Grandfinále SŠ</td></tr>
  </table>

  <p style="margin-bottom: 4px;"><strong>Harmonogram soutěže jednotlivců:</strong></p>
  <table style="border-collapse: collapse; margin-left: 12px; margin-bottom: 14px; font-size: 14px;">
    <tr><td style="padding: 2px 18px 2px 0;">• 16. října</td><td>uzávěrka přihlášek</td></tr>
    <tr><td style="padding: 2px 18px 2px 0;">• 1. - 7. listopadu</td><td>1. online úroveň</td></tr>
    <tr><td style="padding: 2px 18px 2px 0;">• 11. - 18. listopadu</td><td>2. online úroveň</td></tr>
    <tr><td style="padding: 2px 18px 2px 0;">• Datum bude upřesněno</td><td>Grandfinále</td></tr>
  </table>

  <p>Zároveň si Vás dovolujeme upozornit, že jedním z našich letošních partnerů je i <strong>Nadace O2</strong>, díky čemuž si se svými studenty můžete <strong>zcela zdarma</strong> zahrát <a href="https://nadaceo2.cz" style="color: #1976d2; text-decoration: underline;">interaktivní hru</a> zaměřenou na kyberbezpečnost.</p>

  <p>Děkujeme, že máte o pIšQworky zájem a že své studenty podporujete v netradičních formách rozvoje. I díky Vám můžeme dělat školství zábavnější a inkluzivnější.</p>

  <p>S přáním hezkého dne,<br><br>S pozdravem</p>

  <div style="margin-top: 18px;">
    <div style="color: #d32f2f; font-weight: bold; font-size: 15px;">{operator_name}</div>
    <div style="color: #1976d2; font-weight: bold; font-size: 13px;">Člen marketingového týmu</div>
    <div style="color: #1976d2; font-size: 13px;">Mobil: {operator_phone}</div>
    <div style="margin-top: 8px; color: #d32f2f; font-style: italic; font-size: 13px;">students can grow, z. s.</div>
    <div style="color: #1976d2; font-style: italic; font-size: 13px;">Hra školou</div>
    
    <div style="margin-top: 12px;">
      <a href="https://pisqworky.cz" target="_blank" style="text-decoration: none; margin-right: 8px;">
        <img src="cid:icon_web" alt="Web" width="28" height="28" style="vertical-align: middle; border: 0;">
      </a>
      <a href="https://instagram.com/pisqworky" target="_blank" style="text-decoration: none; margin-right: 8px;">
        <img src="cid:icon_instagram" alt="Instagram" width="28" height="28" style="vertical-align: middle; border: 0;">
      </a>
      <a href="https://facebook.com/pisqworky" target="_blank" style="text-decoration: none;">
        <img src="cid:icon_facebook" alt="Facebook" width="28" height="28" style="vertical-align: middle; border: 0;">
      </a>
    </div>
  </div>
</div>"""


def is_valid_email(email: str | None) -> bool:
    """Ověří základní validitu e-mailové adresy."""
    if not email:
        return False
    email = email.strip()
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))


def strip_html_tags(text: str) -> str:
    """Převede HTML text na čistý čitelný plain text."""
    if not text:
        return ""
    # Nahradíme řádkové elementy odřádkováním
    clean = re.sub(r"<(?:br|p|div|tr|h\d)[^>]*>", "\n", text, flags=re.IGNORECASE)
    clean = re.sub(r"<td[^>]*>", "  ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"<[^>]+>", "", clean)
    clean = html.unescape(clean)
    # Zredukujeme nadbytečné prázdné řádky
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean.strip()


class EmailSender:
    """Správce a odesílač e-mailových zpráv školám přes SMTP (HTML i plain) nebo výchozího poštovního klienta."""

    def __init__(self, config: AppConfig):
        self.config = config

    def get_assets_dir(self) -> Path:
        """Vrátí cestu ke složce s grafickými prvky (assets)."""
        return Path(__file__).resolve().parent.parent.parent / "assets"

    def get_html_template(self) -> str:
        """Vrátí nastavenou HTML šablonu, případně výchozí šablonu s designem pIšQworky."""
        tmpl = getattr(self.config, "email_html_template", "") or ""
        if tmpl and "<div" in tmpl:
            return tmpl
        return DEFAULT_PISQWORKY_HTML

    def format_template(
        self,
        template: str,
        school: Optional[SchoolContact] = None,
        operator_name: str = "",
    ) -> str:
        """
        Bezpečně dosadí proměnné školy a operátora do textové i HTML šablony.
        Nepadá na neznámých zástupných znacích v textu.
        """
        if not template:
            return ""

        op_name = operator_name or self.config.operator_name or "Michal Lalík"
        op_email = self.config.smtp_user or "info@scg.cz"
        op_phone = getattr(self.config, "operator_phone", "+420 777 825 705") or "+420 777 825 705"

        school_name = school.name if school else ""
        contact_person = school.contact_person if school else ""
        city = school.city if school else ""
        phone = school.phone if school else ""
        email = school.email if school else ""

        replacements = {
            "school_name": school_name,
            "nazev": school_name,
            "nazev_skoly": school_name,
            "contact_person": contact_person,
            "kontakt": contact_person,
            "kontakt_jmeno": contact_person,
            "city": city,
            "mesto": city,
            "adresa": city,
            "operator_name": op_name,
            "operator": op_name,
            "volajici": op_name,
            "operator_email": op_email,
            "operator_phone": op_phone,
            "telefon_operatora": op_phone,
            "mobil": op_phone,
            "phone": phone,
            "telefon": phone,
            "email": email,
        }

        result = template
        for k, v in replacements.items():
            result = result.replace(f"{{{k}}}", v)

        return result

    def send_email_smtp(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Odešle formátovaný e-mail (HTML + plain text s vloženými ikonami) přes SMTP server.
        Podporuje SSL (port 465) i STARTTLS (port 587) a poskytuje detailní diagnostiku Google SMTP.
        """
        clean_to = (to_email or "").strip()
        if not clean_to:
            return False, "E-mailová adresa příjemce je prázdná."

        if not is_valid_email(clean_to):
            return False, f"Neplatný formát e-mailové adresy: '{clean_to}'."

        smtp_user = (self.config.smtp_user or "").strip()
        smtp_password = (self.config.smtp_password or "").strip()
        smtp_host = (self.config.smtp_host or "smtp.gmail.com").strip()
        smtp_port = int(self.config.smtp_port or 465)
        use_ssl = bool(self.config.smtp_ssl)

        if not smtp_user:
            return False, "V nastavení není vyplněn přihlašovací e-mail pro SMTP."

        if not smtp_password:
            return (
                False,
                "V nastavení není vyplněno SMTP heslo. Pro Google Workspace (@scg.cz) "
                "si vygenerujte 16místné 'Heslo aplikace' na https://myaccount.google.com/apppasswords.",
            )

        # Příprava HTML a plain textu
        is_html = bool(html_body or ("<div" in body or "<p>" in body or "<table" in body))
        final_html = html_body if html_body else (body if is_html else None)
        final_plain = strip_html_tags(body) if is_html else body

        # Sestavení MIME zprávy
        if final_html:
            # Sestavení zprávy s podporou vložených obrázků (Content-ID inline)
            msg = MIMEMultipart("related")
            msg["From"] = smtp_user
            msg["To"] = clean_to
            msg["Subject"] = Header(subject, "utf-8").encode()
            msg["Reply-To"] = smtp_user

            alt_part = MIMEMultipart("alternative")
            alt_part.attach(MIMEText(final_plain, "plain", "utf-8"))
            alt_part.attach(MIMEText(final_html, "html", "utf-8"))
            msg.attach(alt_part)

            # Připojení ikon pro podpis (CID)
            assets_dir = self.get_assets_dir()
            icon_map = {
                "icon_web": "icon_web.png",
                "icon_instagram": "icon_instagram.png",
                "icon_facebook": "icon_facebook.png",
            }
            for cid_name, file_name in icon_map.items():
                if f"cid:{cid_name}" in final_html:
                    img_file = assets_dir / file_name
                    if img_file.exists():
                        try:
                            with open(img_file, "rb") as f:
                                img = MIMEImage(f.read())
                                img.add_header("Content-ID", f"<{cid_name}>")
                                img.add_header("Content-Disposition", "inline", filename=file_name)
                                msg.attach(img)
                        except Exception as e:
                            print(f"[Mailer] Nelze připojit inline ikonu {file_name}: {e}")
        else:
            msg = MIMEMultipart("alternative")
            msg["From"] = smtp_user
            msg["To"] = clean_to
            msg["Subject"] = Header(subject, "utf-8").encode()
            msg["Reply-To"] = smtp_user
            msg.attach(MIMEText(final_plain, "plain", "utf-8"))

        try:
            if use_ssl or smtp_port == 465:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=15) as server:
                    server.login(smtp_user, smtp_password)
                    server.sendmail(smtp_user, [clean_to], msg.as_string())
            else:
                with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                    server.ehlo()
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                    server.ehlo()
                    server.login(smtp_user, smtp_password)
                    server.sendmail(smtp_user, [clean_to], msg.as_string())

            return True, f"E-mail byl úspěšně odeslán na {clean_to}."

        except smtplib.SMTPAuthenticationError as e:
            if e.smtp_code in (534, 535):
                return (
                    False,
                    f"Google odmítl přihlášení (kód {e.smtp_code}): Neplatné přihlašovací údaje.\n\n"
                    "DŮVOD: Google pro účty (@scg.cz i @gmail.com) zakazuje běžné heslo pro SMTP.\n"
                    "ŘEŠENÍ: Je nutné si v Google účtu vygenerovat 16místné 'Heslo aplikace' (App Password):\n"
                    "1. Přejděte na: https://myaccount.google.com/apppasswords\n"
                    "2. Přihlaste se jako lalik@scg.cz\n"
                    "3. Zadejte název např. 'Call Centrum' a klikněte na Vytvořit\n"
                    "4. Vygenerované 16místné heslo vložte v Nastavení do pole 'Heslo aplikace (SMTP)'.",
                )
            return (
                False,
                f"Chyba přihlášení k SMTP ({e.smtp_code}): Zkontrolujte uživatelské jméno a heslo aplikace.",
            )
        except smtplib.SMTPRecipientsRefused:
            return False, f"Server odmítl příjemce {clean_to}."
        except smtplib.SMTPException as e:
            return False, f"Chyba protokolu SMTP: {e}"
        except TimeoutError:
            return False, f"Vypršel časový limit při připojování k {smtp_host}:{smtp_port}."
        except Exception as e:
            return False, f"Chyba při odesílání e-mailu: {e}"

    def open_in_mail_client(
        self,
        to_email: str,
        subject: str,
        body: str,
    ) -> Tuple[bool, str]:
        """
        Otevře výchozího systémového poštovního klienta (Thunderbird, webmail, Outlook apod.)
        přes protokol mailto: s předvyplněným příjemcem, předmětem a tělem zprávy.
        """
        clean_to = (to_email or "").strip()
        plain_body = strip_html_tags(body) if ("<div" in body or "<p>" in body) else body

        params = {}
        if subject:
            params["subject"] = subject
        if plain_body:
            params["body"] = plain_body

        query_string = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        mailto_url = f"mailto:{clean_to}"
        if query_string:
            mailto_url += f"?{query_string}"

        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            ok = QDesktopServices.openUrl(QUrl(mailto_url))
            if ok:
                return True, "Zpráva byla otevřena ve vašem e-mailovém klientovi."
            return False, "Nepodařilo se otevřít systémového e-mailového klienta."
        except Exception:
            try:
                import subprocess
                subprocess.Popen(["xdg-open", mailto_url])
                return True, "Otevřeno přes xdg-open."
            except Exception as e:
                return False, f"Chyba při otevírání mailto odkazu: {e}"
