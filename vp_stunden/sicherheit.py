from django.contrib.auth.password_validation import validate_password # Bibliothek für Passwortvalidierung
from django.core.exceptions import ValidationError

from django.conf import settings # Bibliothek für Fehlerbehandlung
from .models import Benutzerkonto # Import des benutzerdefinierten Benutzerkontos-Modells
from django.http import HttpRequest # Import für die Verarbeitung von HTTP-Anfragen
from django.utils import timezone # Import für die Verarbeitung von Zeitstempeln


def lege_konto_an(benutzername: str, passwort: str, rolle: str) -> tuple[Benutzerkonto | None, list[str]]:
    """
    Erstellt ein neues Benutzerkonto mit den angegebenen Parametern.

    :param benutzername: Der Benutzername für das neue Konto.
    :param passwort: Das Passwort für das neue Konto.
    :param rolle: Die Rolle des Benutzers (Lehrperson oder Administrator).
    :return: Das erstellte Benutzerkonto-Objekt.
    """
    Fehlerliste = []

    # Validierung des Passworts
    try:
        validate_password(passwort)
    except ValidationError as e:
        Fehlerliste.extend(e.messages)
        return None, Fehlerliste

    # Validierung der Rolle: Nur Lehrperson und Administrator sind erlaubt
    if rolle not in [Benutzerkonto.LEHRPERSON, Benutzerkonto.ADMINISTRATOR]:
        Fehlerliste.append(f"Ungültige Rolle: {rolle}. Erlaubte Rollen sind '{Benutzerkonto.LEHRPERSON}' und '{Benutzerkonto.ADMINISTRATOR}'.")
        return None, Fehlerliste

    # Validierung des Benutzernamens: Überprüfung, ob der Benutzername bereits existiert
    if Benutzerkonto.objects.filter(username=benutzername).exists():
        Fehlerliste.append(f"Benutzername '{benutzername}' ist bereits vergeben.")
        return None, Fehlerliste

    # Erstellung des Benutzerkontos
    konto = Benutzerkonto(username=benutzername, rolle=rolle)
    konto.set_password(passwort)  # Passwort wird gehasht und dem Objekt angehangen
    konto.save()  # Speichert das Konto in der Datenbank
    return konto, []


def setze_passwort_zurueck(konto_id: int, neues_passwort: str) -> list[str]:
    """
    Setzt das Passwort für ein bestehendes Benutzerkonto zurück.

    :param konto_id: Die ID des Kontos, dessen Passwort zurückgesetzt werden soll.
    :param neues_passwort: Das neue Passwort für das Konto.
    :return: Eine Liste von Fehlermeldungen, falls die Validierung fehlschlägt, oder eine leere Liste bei Erfolg.
    """
    Fehlerliste = []

    # Validierung des neuen Passworts
    try:
        validate_password(neues_passwort)
    except ValidationError as e:
        Fehlerliste.extend(e.messages)
        return Fehlerliste

    # Abrufen des Benutzerkontos aus der Datenbank
    try:
        konto = Benutzerkonto.objects.get(pk=konto_id)
    except Benutzerkonto.DoesNotExist:
        Fehlerliste.append(f"Benutzerkonto mit der ID '{konto_id}' existiert nicht.")
        return Fehlerliste

    # Setzen des neuen Passworts
    konto.set_password(neues_passwort)  # Passwort wird gehasht
    konto.save()  # Speichern des aktualisierten Kontos in der Datenbank
    return []  # Keine Fehler aufgetreten


def melde_an(anfrage: HttpRequest, benutzername: str, passwort: str) -> list[str]:
    """
    Meldet einen Benutzer an, indem die Anmeldedaten überprüft werden.

    :param anfrage: Die HTTP-Anfrage, die die Anmeldedaten enthält.
    :param benutzername: Der Benutzername des Benutzers.
    :param passwort: Das Passwort des Benutzers.
    :return: Eine Liste von Fehlermeldungen, falls die Validierung fehlschlägt, oder eine leere Liste bei Erfolg.
    """
    Fehlerliste = []

    # Abrufen des Benutzerkontos aus der Datenbank
    try:
        konto = Benutzerkonto.objects.get(username=benutzername)
        jetzt = timezone.now()
    except Benutzerkonto.DoesNotExist:
        Fehlerliste.append(f"Anmeldung fehlgeschlagen")
        return Fehlerliste

    # Überprüfung, ob das Konto gesperrt ist
    if konto.gesperrt_bis is not None and konto.gesperrt_bis > jetzt:
        Fehlerliste.append(f"Anmeldung fehlgeschlagen")
        return Fehlerliste

    if konto.gesperrt_bis is not None and konto.gesperrt_bis <= jetzt:
        # Konto ist nicht mehr gesperrt, zurücksetzen der Sperrzeit
        konto.fehlversuche = 0
        konto.fehlversuchszeitraum_beginn = None
        konto.gesperrt_bis = None
        konto.save()

    if konto.fehlversuchszeitraum_beginn is not None and (jetzt - konto.fehlversuchszeitraum_beginn).total_seconds() >= settings.ANMELDE_FENSTER_SEKUNDEN:
        # Zurücksetzen der fehlgeschlagenen Anmeldeversuche, wenn der Zeitraum von 15 Minuten überschritten wurde
        konto.fehlversuche = 0
        konto.fehlversuchszeitraum_beginn = None
        konto.save()

    # Überprüfung des Passworts
    if not konto.check_password(passwort):
        # Passwort ist falsch, erhöhen der fehlgeschlagenen Anmeldeversuche
        if konto.fehlversuchszeitraum_beginn is None:
            konto.fehlversuchszeitraum_beginn = jetzt  # Setze den Beginn des Zeitraums der fehlgeschlagenen Anmeldeversuche

        konto.fehlversuche += 1
        if konto.fehlversuche == settings.ANMELDE_MAX_FEHLVERSUCHE:
            konto.gesperrt_bis = jetzt + timezone.timedelta(seconds=settings.ANMELDE_SPERRDAUER_SEKUNDEN)  # Sperre das Konto für 5 Minuten

        konto.save()
        Fehlerliste.append("Anmeldung fehlgeschlagen")
        return Fehlerliste

    # Anmeldung erfolgreich; Sitzungsaufbau ausstehend
    return []