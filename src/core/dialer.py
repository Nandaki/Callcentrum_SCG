from __future__ import annotations

import re
import subprocess
import time
from typing import Dict, List, Tuple

from ..config import AppConfig
from ..models.school import SchoolContact


class PhoneController:
    """Ovladač telefonu pro vytáčení (KDE Connect / ADB), zavěšování a posílání SMS."""

    def __init__(self, config: AppConfig):
        self.config = config

    def is_adb_connected(self) -> bool:
        """Zkontroluje, zda je přes ADB dostupné alespoň jedno zařízení."""
        devices = self.get_adb_devices()
        return len(devices) > 0

    def get_adb_devices(self) -> List[str]:
        """Vrátí seznam identifikátorů zařízení připojených přes ADB."""
        try:
            res = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=3)
            lines = res.stdout.strip().splitlines()[1:]
            devices = []
            for line in lines:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "device":
                    devices.append(parts[0])
            return devices
        except Exception as e:
            print(f"[ADB] Chyba při hledání zařízení: {e}")
            return []

    def get_kdeconnect_devices(self) -> List[Dict[str, str]]:
        """Vrátí seznam spárovaných a dostupných zařízení v KDE Connect."""
        try:
            res = subprocess.run(["kdeconnect-cli", "-a", "--id-name-only"], capture_output=True, text=True, timeout=4)
            devices = []
            for line in res.stdout.strip().splitlines():
                # Formát výstupu: <id> <name>
                parts = line.strip().split(" ", 1)
                if len(parts) == 2:
                    devices.append({"id": parts[0], "name": parts[1]})
            return devices
        except Exception as e:
            print(f"[KDE Connect] Chyba při zjišťování zařízení: {e}")
            return []

    def get_kdeconnect_ip(self, device_id: str | None = None) -> str | None:
        """Získá IP adresu zařízení z KDE Connect přes DBus."""
        dev_id = device_id or self.config.kdeconnect_device_id
        if dev_id:
            try:
                cmd = ["qdbus", "org.kde.kdeconnect", f"/modules/kdeconnect/devices/{dev_id}", "org.kde.kdeconnect.device.reachableAddresses"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                if res.returncode == 0:
                    for line in res.stdout.strip().splitlines():
                        match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", line)
                        if match:
                            return match.group(0)
            except Exception:
                pass
        return None

    def pair_wireless(self, ip: str, port: int | str, code: str) -> Tuple[bool, str]:
        """Spáruje telefon pomocí příkazu: adb pair <ip>:<port> <code>."""
        ip = ip.strip()
        port = str(port).strip()
        code = str(code).strip()
        if not ip or not port or not code:
            return False, "Zadejte IP adresu, párovací port i párovací kód."

        target = f"{ip}:{port}"
        cmd = ["adb", "pair", target, code]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
            output = (res.stdout + "\n" + res.stderr).strip()
            if "Successfully paired" in output:
                return True, f"Úspěšně spárováno s {target}!"
            return False, output or "Párování selhalo (zkontrolujte kód a port na displeji)."
        except subprocess.TimeoutExpired:
            return False, f"Vypršel časový limit při párování s {target}. Zkontrolujte telefon."
        except Exception as e:
            return False, f"Chyba při volání adb pair: {e}"

    def connect_wireless(self, ip: str, port: int | str) -> Tuple[bool, str]:
        """Připojí se k telefonu pomocí: adb connect <ip>:<port>."""
        ip = ip.strip()
        port = str(port).strip()
        if not ip or not port:
            return False, "Zadejte IP adresu i port pro připojení."

        target = f"{ip}:{port}"
        cmd = ["adb", "connect", target]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            output = (res.stdout + "\n" + res.stderr).strip()
            if "connected to" in output and "cannot connect" not in output:
                self.config.adb_device_id = target
                self.config.save()
                return True, f"Úspěšně připojeno k {target}!"
            return False, output or f"Nepodařilo se připojit k {target}."
        except Exception as e:
            return False, f"Chyba při volání adb connect: {e}"

    def disconnect_wireless(self, target: str = "") -> Tuple[bool, str]:
        """Odpojí ADB zařízení."""
        cmd = ["adb", "disconnect"]
        if target:
            cmd.append(target)
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return True, (res.stdout + "\n" + res.stderr).strip()
        except Exception as e:
            return False, f"Chyba při odpojování: {e}"

    def scan_open_ports(self, ip: str, start_port: int = 30000, end_port: int = 50000) -> List[int]:
        """Rychlý paralelní scan otevřených portů na telefonu pro nalezení ADB."""
        import asyncio

        async def check(target_ip: str, p: int):
            try:
                conn = asyncio.open_connection(target_ip, p)
                _, writer = await asyncio.wait_for(conn, timeout=0.12)
                writer.close()
                await writer.wait_closed()
                return p
            except Exception:
                return None

        async def run_scan():
            found = []
            step = 2500
            for b_start in range(start_port, end_port, step):
                b_end = min(b_start + step, end_port)
                tasks = [check(ip, port) for port in range(b_start, b_end)]
                results = await asyncio.gather(*tasks)
                found.extend([p for p in results if p is not None])
                if found:
                    break
            return found

        try:
            return asyncio.run(run_scan())
        except Exception as e:
            print(f"[PortScan] Chyba: {e}")
            return []

    def _get_adb_prefix(self) -> List[str]:
        """Vrátí základ příkazu ADB s volitelným specifikátorem zařízení (-s <id>)."""
        cmd = ["adb"]
        active_devices = self.get_adb_devices()
        if not active_devices:
            return cmd

        # Pokud je v configu zadané zařízení a je stále aktivní, použijeme ho
        if self.config.adb_device_id and self.config.adb_device_id in active_devices:
            cmd.extend(["-s", self.config.adb_device_id])
        elif len(active_devices) == 1:
            # Pokud je aktivní právě jedno zařízení, použijeme ho automaticky
            target = active_devices[0]
            cmd.extend(["-s", target])
            if self.config.adb_device_id != target:
                self.config.adb_device_id = target
                self.config.save()
        return cmd

    def dial(self, school: SchoolContact) -> Tuple[bool, str]:
        """
        Inteligentně vytočí hovor podle země:
        - Slovensko (+421) -> Odorik VoIP přes Zoiper aplikaci v telefonu
        - Česko (+420) a ostatní -> GSM hovor přes SIM (KDE Connect nebo ADB CALL)
        """
        clean_num = school.clean_phone
        if school.is_slovak:
            return self.dial_slovak_voip(clean_num)
        else:
            return self.dial_czech_gsm(clean_num)

    def dial_czech_gsm(self, phone_number: str) -> Tuple[bool, str]:
        """
        Vytočí české číslo přes normální GSM SIM.
        Pokud je připojeno ADB, použije přímý příkaz android.intent.action.CALL.
        Pokud ne, zkusí kdeconnect-handler tel:<cislo>.
        """
        clean_num = re.sub(r"[^\d+]", "", phone_number)
        print(f"[Dialer] Vytáčím ČR GSM hovor na číslo {clean_num}")

        # 1. Zkusíme ADB přímé volání (fyzicky okamžitě začne vytáčet přes SIM)
        if self.is_adb_connected():
            cmd = self._get_adb_prefix() + [
                "shell", "am", "start",
                "-a", "android.intent.action.CALL",
                "-d", f"tel:{clean_num}"
            ]
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    return True, f"Hovor zahájen přes ADB SIM: {clean_num}"
                else:
                    print(f"[ADB] Chyba vytáčení: {res.stderr}")
            except Exception as e:
                print(f"[ADB] Výjimka při vytáčení: {e}")

        # 2. Záložní cesta: KDE Connect handler s tel: URI (neblokující spuštění)
        device_id = self.config.kdeconnect_device_id
        if device_id:
            cmd = ["kdeconnect-handler", "--device", device_id, "--open", f"tel:{clean_num}"]
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True, f"Číslo odesláno do telefonu přes KDE Connect: {clean_num}"
            except Exception as e:
                return False, f"Chyba při volání KDE Connect: {e}"

        return False, "Telefon není dostupný přes ADB ani KDE Connect."

    def dial_slovak_voip(self, phone_number: str) -> Tuple[bool, str]:
        """
        Vytočí slovenské číslo přes VoIP Odorik v aplikaci Zoiper přes ADB.
        Příkaz: adb shell am start -a android.intent.action.CALL -d "sip:<cislo>@sip.odorik.cz" -p com.zoiper.android.app
        """
        clean_num = re.sub(r"[^\d+]", "", phone_number)
        sip_uri = f"sip:{clean_num}@{self.config.sip_domain}"
        print(f"[Dialer] Vytáčím SK VoIP přes Zoiper: {sip_uri}")

        if not self.is_adb_connected():
            return False, "Pro VoIP hovor přes Zoiper musí být telefon připojen přes ADB (USB nebo Wi-Fi ladění)."

        cmd = self._get_adb_prefix() + [
            "shell", "am", "start",
            "-a", "android.intent.action.CALL",
            "-d", sip_uri,
            "-p", self.config.zoiper_package
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                return True, f"VoIP hovor spuštěn v Zoiperu: {sip_uri}"
            else:
                return False, f"Chyba spuštění Zoiperu přes ADB: {res.stderr}"
        except Exception as e:
            return False, f"Výjimka při volání Zoiperu: {e}"

    def hangup(self) -> Tuple[bool, str]:
        """
        Zavěsí probíhající hovor stiskem klávesy KEYCODE_ENDCALL (6) přes ADB.
        Příkaz: adb shell input keyevent 6
        """
        print("[Dialer] Zavěšuji hovor (KEYCODE_ENDCALL)...")
        if not self.is_adb_connected():
            return False, "Telefon není připojen přes ADB, nelze automaticky stisknout tlačítko zavěšení."

        cmd = self._get_adb_prefix() + ["shell", "input", "keyevent", "6"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
            if res.returncode == 0:
                return True, "Hovor úspěšně zavěšen přes ADB."
            else:
                return False, f"Chyba při zavěšování: {res.stderr}"
        except Exception as e:
            return False, f"Výjimka při zavěšování: {e}"

    def get_screen_size(self) -> Tuple[int, int]:
        """Vrátí rozlišení displeje (šířka, výška) z příkazu 'adb shell wm size'."""
        prefix = self._get_adb_prefix()
        try:
            res = subprocess.run(prefix + ["shell", "wm", "size"], capture_output=True, text=True, timeout=3)
            match = re.search(r"(\d+)x(\d+)", res.stdout)
            if match:
                return int(match.group(1)), int(match.group(2))
        except Exception:
            pass
        return 1440, 3120

    def send_sms_adb(self, phone_number: str, message: str | None = None) -> Tuple[bool, str]:
        """
        Odešle SMS přímo přes ADB pomocí systémové aplikace Zprávy (Google Messages).
        1. Probudí displej.
        2. Otevře konverzaci s předvyplněným textem.
        3. Stiskne tlačítko Odeslat.
        4. Vrátí telefon na domovskou obrazovku.
        """
        clean_num = re.sub(r"[^\d+]", "", phone_number)
        text = message or self.config.silent_sms_template
        if not clean_num:
            return False, "Neplatné telefonní číslo pro SMS."

        if not self.is_adb_connected():
            return False, "Telefon není připojen přes ADB."

        print(f"[ADB SMS] Odesílám SMS na číslo {clean_num}: {text[:50]}...", flush=True)

        prefix = self._get_adb_prefix()

        # 1. Probudíme displej pokud spal
        try:
            subprocess.run(prefix + ["shell", "input", "keyevent", "224"], timeout=3)
        except Exception:
            pass

        # 2. Otevřeme draft zprávy přes SENDTO intent
        escaped_text = text.replace('"', '\\"')
        cmd_open = prefix + [
            "shell",
            f'am start -a android.intent.action.SENDTO -d sms:{clean_num} --es sms_body "{escaped_text}"'
        ]
        try:
            res_open = subprocess.run(cmd_open, capture_output=True, text=True, timeout=6)
            if res_open.returncode != 0:
                print(f"[ADB SMS] Chyba SENDTO: {res_open.stderr}", flush=True)
                return False, f"Chyba při otevírání SMS: {res_open.stderr}"
        except Exception as e:
            return False, f"Výjimka při volání SENDTO: {e}"

        time.sleep(0.6)

        # 3. Určíme souřadnice tlačítka Odeslat podle rozlišení displeje
        w, h = self.get_screen_size()
        cx = int(w * 0.906)
        cy = int(h * 0.9388)
        # Použijeme stisk s trváním 100 ms (input swipe X Y X Y 100), aby Android zaregistroval kliknutí i v Compose UI
        cmd_tap = prefix + ["shell", "input", "swipe", str(cx), str(cy), str(cx), str(cy), "100"]
        try:
            subprocess.run(cmd_tap, capture_output=True, text=True, timeout=4)
        except Exception as e:
            return False, f"Chyba při klepnutí na Odeslat: {e}"

        time.sleep(0.3)

        # 4. Vrátíme telefon na domovskou obrazovku
        try:
            subprocess.run(prefix + ["shell", "input", "keyevent", "3"], timeout=3)
        except Exception:
            pass

        return True, f"SMS úspěšně odeslána přes ADB na {clean_num}"

    def send_silent_sms(self, phone_number: str, message: str | None = None) -> Tuple[bool, str]:
        """
        Odešle tichou SMS po vypršení 30s limitu:
        - Primárně přes ADB
        - Pokud ADB není dostupné, záložně přes KDE Connect
        """
        clean_num = re.sub(r"[^\d+]", "", phone_number)
        text = message or self.config.silent_sms_template

        if self.is_adb_connected():
            return self.send_sms_adb(clean_num, text)

        # Záložní metoda přes KDE Connect
        device_id = self.config.kdeconnect_device_id
        if device_id:
            print(f"[Dialer] Odesílám SMS na {clean_num} přes KDE Connect...", flush=True)
            cmd = [
                "kdeconnect-cli",
                "--send-sms", text,
                "--destination", clean_num,
                "-d", device_id
            ]
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
                if res.returncode == 0:
                    return True, f"SMS odeslána přes KDE Connect na {clean_num}"
                return False, f"KDE Connect SMS chyba: {res.stderr}"
            except Exception as e:
                return False, f"Výjimka KDE Connect: {e}"

        return False, "Telefon není připojen přes ADB ani KDE Connect."

    def handle_timeout(self, school: SchoolContact) -> Tuple[bool, str]:
        """
        Automatická akce po vypršení 30s odpočtu:
        1. Zavěsí hovor přes ADB (pokud je dostupné).
        2. Počká 0.4 sekundy.
        3. Odešle tichou SMS přes ADB (nebo KDE Connect).
        """
        hangup_ok, hangup_msg = self.hangup()
        time.sleep(0.4)
        sms_ok, sms_msg = self.send_silent_sms(school.clean_phone)

        msg = f"{hangup_msg} | {sms_msg}"
        return sms_ok, msg
