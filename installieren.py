import secrets
import subprocess
import sys
import venv
from pathlib import Path


# Diese Anweisung läuft später mit Django im eingerichteten Projektinterpreter.
ERSTKONTO_EINRICHTEN = """
import warnings
from getpass import GetPassWarning, getpass

from django.core.exceptions import ValidationError
from vp_stunden.models import Benutzerkonto
from vp_stunden.sicherheit import lege_konto_an

if Benutzerkonto.objects.filter(
    rolle=Benutzerkonto.ADMINISTRATOR, is_active=True
).exists():
    print("Ein aktives Administrationskonto ist bereits vorhanden.")
else:
    warnings.simplefilter("error", GetPassWarning)
    print("Erstes Administrationskonto einrichten.")
    try:
        benutzername = input("Benutzername: ").strip()
        benutzername = Benutzerkonto._meta.get_field("username").clean(
            benutzername, None
        )
        passwort = getpass("Passwort (mindestens 15 Zeichen): ")
        wiederholung = getpass("Passwort wiederholen: ")
    except ValidationError as fehler:
        raise SystemExit(" ".join(fehler.messages)) from None
    except GetPassWarning:
        raise SystemExit("Das Passwort muss in einem normalen Terminal eingegeben werden.") from None
    except (EOFError, KeyboardInterrupt):
        raise SystemExit("Die Kontoeinrichtung wurde abgebrochen.") from None

    if passwort != wiederholung:
        raise SystemExit("Die beiden Passwörter stimmen nicht überein.")

    konto, fehlerliste = lege_konto_an(
        benutzername, passwort, Benutzerkonto.ADMINISTRATOR
    )
    if konto is None or fehlerliste:
        raise SystemExit(" ".join(fehlerliste) or "Das Konto wurde nicht angelegt.")

    print("Das Administrationskonto wurde angelegt.")
"""


def main():
    """Richtet den Prototyp für den lokalen Betrieb ein."""
    if sys.version_info[:2] != (3, 14):
        raise SystemExit("Für die Einrichtung wird Python 3.14.x benötigt.")

    if sys.platform not in ("linux", "win32"):
        raise SystemExit("Dieses Skript unterstützt Linux und Windows.")

    # Pfade beziehen sich auf den Skriptstandort, nicht auf den Terminalordner.
    projektordner = Path(__file__).resolve().parent
    umgebung = projektordner / ".venv"
    anforderungen = projektordner / "requirements.txt"

    if not (projektordner / "manage.py").is_file():
        raise SystemExit("Die Projektdatei manage.py fehlt neben dem Skript.")

    if not anforderungen.is_file():
        raise SystemExit("Die Datei requirements.txt fehlt neben dem Skript.")

    if sys.platform == "win32":
        python_datei = umgebung / "Scripts" / "python.exe"
    else:
        python_datei = umgebung / "bin" / "python"

    # Vorhandene Umgebungen werden geprüft und nicht neu erstellt.
    if not umgebung.exists():
        print("Die Projektumgebung .venv wird erstellt.", flush=True)
        venv.EnvBuilder(with_pip=True).create(umgebung)

    if not (umgebung / "pyvenv.cfg").is_file() or not python_datei.is_file():
        raise SystemExit(
            "Die vorhandene .venv ist unvollständig oder unpassend. "
            "Die Paketinstallation wurde nicht gestartet."
        )

    # Der Unterprozess prüft Version und Zugehörigkeit zur Projektumgebung.
    pruefung = (
        "import sys; from pathlib import Path; "
        "gueltig = sys.version_info[:2] == (3, 14) "
        "and sys.prefix != sys.base_prefix "
        "and Path(sys.prefix).resolve() == Path(sys.argv[1]).resolve(); "
        "raise SystemExit(0 if gueltig else 1)"
    )

    try:
        subprocess.run(
            [str(python_datei), "-c", pruefung, str(umgebung)],
            cwd=projektordner,
            check=True,
        )
    except subprocess.CalledProcessError:
        raise SystemExit(
            "Die .venv muss eine eigene Projektumgebung mit Python 3.14.x sein. "
            "Die Paketinstallation wurde nicht gestartet."
        ) from None

    # Alle Paketbefehle verwenden ausdrücklich den geprüften Interpreter.
    subprocess.run(
        [str(python_datei), "-m", "pip", "--version"],
        cwd=projektordner,
        check=True,
    )

    print("Die Pakete aus requirements.txt werden installiert.", flush=True)
    subprocess.run(
        [str(python_datei), "-m", "pip", "install", "-r", str(anforderungen)],
        cwd=projektordner,
        check=True,
    )

    # Exklusives Anlegen verhindert das Überschreiben eines vorhandenen Schlüssels.
    konfiguration = projektordner / "config" / "local_settings.py"
    try:
        with konfiguration.open("x", encoding="utf-8") as datei:
            datei.write(f"SECRET_KEY = {secrets.token_urlsafe(64)!r}\n")
    except FileExistsError:
        print("Die vorhandene lokale Konfiguration wird weiterverwendet.")
    else:
        print("Die lokale Konfiguration wurde angelegt.")

    # Vorhandene Migrationen richten das Schema ein, ohne die Datenbank zu leeren.
    print("Die Datenbank wird eingerichtet.", flush=True)
    subprocess.run(
        [str(python_datei), "manage.py", "migrate", "--noinput"],
        cwd=projektordner,
        check=True,
    )

    # Kontoprüfung und verdeckte Passworteingabe erfolgen im Django-Unterprozess.
    subprocess.run(
        [
            str(python_datei),
            "manage.py",
            "shell",
            "--no-imports",
            "-c",
            ERSTKONTO_EINRICHTEN,
        ],
        cwd=projektordner,
        check=True,
    )

    if sys.platform == "win32":
        startbefehl = (
            r".\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000"
        )
    else:
        startbefehl = ".venv/bin/python manage.py runserver 127.0.0.1:8000"

    print("\nDie lokale Einrichtung ist abgeschlossen.")
    print("Start im Projektordner:")
    print(startbefehl)
    print("Browser: http://127.0.0.1:8000")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as fehler:
        raise SystemExit(
            f"Einrichtung abgebrochen (Rückgabecode {fehler.returncode})."
        ) from None
    except OSError as fehler:
        raise SystemExit(f"Einrichtung abgebrochen: {fehler}") from None
    except KeyboardInterrupt:
        raise SystemExit("Die Einrichtung wurde abgebrochen.") from None
