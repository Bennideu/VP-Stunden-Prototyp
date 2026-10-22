from django.core.exceptions import ValidationError  # Ausnahme bei ungültigen Eingaben
from django.conf import settings  # Zugriff auf die konfigurierten Anmeldegrenzen
from django.contrib.auth.password_validation import validate_password # Bibliothek für Passwortvalidierung
from .models import Benutzerkonto # Import des benutzerdefinierten Benutzerkontos-Modells
from django.http import HttpRequest # Import für die Verarbeitung von HTTP-Anfragen
from django.utils import timezone # Import für die Verarbeitung von Zeitstempeln
from django.contrib.auth import get_user, login, logout, update_session_auth_hash # Import für die Authentifizierungsfunktionen

def lege_konto_an(benutzername: str, passwort: str, rolle: str) -> tuple[Benutzerkonto | None, list[str]]:
    """
    Erstellt ein neues Benutzerkonto mit den angegebenen Parametern.

    :param benutzername: Der Benutzername für das neue Konto.
    :param passwort: Das Passwort für das neue Konto.
    :param rolle: Die Rolle des Benutzers (Lehrperson oder Administrator).
    :return: Das erstellte Benutzerkonto-Objekt.

    1. Validiert das Passwort.
    2. Validiert die Rolle, um sicherzustellen, dass sie entweder Lehrperson oder Administrator ist.
    3. Überprüft, ob der Benutzername bereits existiert.
    4. Erstellt das Benutzerkonto, wenn alle Validierungen erfolgreich sind.
    5. Gibt eine Liste von Fehlermeldungen zurück, falls eine der Prüfungen fehlschlägt, oder eine leere Liste bei Erfolg.
    6. Beendet die Funktion und gibt die Fehlermeldungen zurück, wenn das Passwort ungültig ist, die Rolle nicht erlaubt ist oder der Benutzername bereits existiert.
    7. Speichert das erstellte Benutzerkonto in der Datenbank, wenn alle Validierungen erfolgreich sind.
    8. Gibt das erstellte Benutzerkonto-Objekt und eine leere Liste von Fehlermeldungen
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

    1. Validiert das neue Passwort.
    2. Ruft das Benutzerkonto aus der Datenbank ab.
    3. Setzt das neue Passwort für das Konto.
    4. Speichert das aktualisierte Konto in der Datenbank.
    5. Gibt eine Liste von Fehlermeldungen zurück, falls eine der Prüfungen fehlschlägt, oder eine leere Liste bei Erfolg.
    6. Beendet die Funktion und gibt die Fehlermeldungen zurück, wenn das Konto nicht existiert oder das Passwort ungültig ist.
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

    1. Überprüft, ob das Benutzerkonto existiert.
    2. Überprüft, ob das Konto gesperrt ist.
    3. Überprüft, ob das Passwort korrekt ist.
    4. Aktualisiert die fehlgeschlagenen Anmeldeversuche und Sperrzeiten entsprechend den konfigurierten Grenzen.
    5. Verknüpft das geprüfte Benutzerkonto mit der Sitzung der Anfrage.
    6. Initialisiert die Sitzungszeitpunkte für den Beginn der Sitzung und die letzte Aktivität.
    7. Gibt eine Liste von Fehlermeldungen zurück, falls eine der Prüfungen fehlschlägt, oder eine leere Liste bei Erfolg.
    8. Beendet die Sitzung und verweigert den Zugriff, wenn das Konto gesperrt ist oder die Anmeldeversuche überschritten wurden.
    9. Beendet die Sitzung und verweigert den Zugriff, wenn das Passwort falsch ist.
    10. Beendet die Sitzung und verweigert den Zugriff, wenn das Benutzerkonto nicht existiert.
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

    # Nach richtigem Passwort Fehlversuchs- und Sperrzustand zurücksetzen
    konto.fehlversuche = 0
    konto.fehlversuchszeitraum_beginn = None
    konto.gesperrt_bis = None
    konto.save()  # Zurückgesetzte Werte in der Datenbank speichern

    # Das geprüfte Benutzerkonto mit der Sitzung der Anfrage verknüpfen
    login(anfrage, konto)

    # Anmeldezeitpunkt als Zahl ermitteln und beide Sitzungszeitpunkte initialisieren
    anmeldezeitpunkt = timezone.now().timestamp()
    anfrage.session['sitzungsbeginn'] = anmeldezeitpunkt  # Fester Beginn der Sitzung
    anfrage.session['letzte_aktivitaet'] = anmeldezeitpunkt  # Zu Beginn derselbe Zeitpunkt

    return []  # Leere Fehlerliste nach dem Sitzungsaufbau zurückgeben


def melde_ab(anfrage: HttpRequest) -> None:
    """
    Beendet die Anmeldung und macht die aktuelle Sitzung serverseitig ungültig.
    """
    # Anmeldung beenden und die serverseitige Sitzung löschen
    logout(anfrage)


def pruefe_zugriff(anfrage: HttpRequest, erlaubte_rollen: list[str]) -> list[str]:
    """
    Prüft den Zugriff auf eine geschützte Ansicht.

    :param anfrage: Die HTTP-Anfrage, die den Zugriff auslöst.
    :param erlaubte_rollen: Liste der Rollen, die Zugriff auf die Ansicht haben.
    :return: Eine Liste von Fehlermeldungen, falls die Zugriffsprüfung fehlschlägt, oder eine leere Liste bei Erfolg.

    1. Prüft, ob der Benutzer angemeldet ist.
    2. Prüft, ob die Sitzung noch gültig ist (Inaktivitätsfrist und maximale Dauer).
    3. Prüft, ob die Rolle des Benutzers in der Liste der erlaubten Rollen enthalten ist.
    4. Aktualisiert die letzte Aktivität in der Sitzung, wenn alle Prüfungen bestanden wurden.
    5. Gibt eine Liste von Fehlermeldungen zurück, falls eine der Prüfungen fehlschlägt, oder eine leere Liste bei Erfolg.
    6. Beendet die Sitzung und verweigert den Zugriff, wenn die Sitzung abgelaufen ist oder die maximale Dauer überschritten wurde.
    7. Beendet die Sitzung und verweigert den Zugriff, wenn die Rolle des Benutzers nicht in der Liste der erlaubten Rollen enthalten ist.
    8. Beendet die Sitzung und verweigert den Zugriff, wenn der Benutzer nicht angemeldet ist.
    """
    fehlerliste = []  # Sammelt Fehlermeldungen der Zugriffsprüfung

    # Das zur Sitzung gehörende Benutzerkonto ermitteln
    konto = get_user(anfrage)

    # Zugriff ohne gültige Anmeldung verweigern
    if not konto.is_authenticated:
        fehlerliste.append('Zugriff verweigert')
        return fehlerliste

    # Gespeicherten Sitzungsbeginn und letzte Aktivität lesen
    # .get() liefert None, falls der jeweilige Schlüssel fehlt
    sitzungsbeginn = anfrage.session.get('sitzungsbeginn')
    letzte_aktivitaet = anfrage.session.get('letzte_aktivitaet')

    # Sitzung bei fehlenden Zeitangaben beenden und den Zugriff verweigern
    if sitzungsbeginn is None or letzte_aktivitaet is None:
        melde_ab(anfrage)
        fehlerliste.append('Zugriff verweigert')
        return fehlerliste

    # Aktuelle Zeit einmal als Sekundenwert für beide Zeitvergleiche erfassen
    jetzt = timezone.now().timestamp()

    # Sitzung beenden, sobald die Inaktivitätsfrist oder die maximale Dauer erreicht ist
    if (
        jetzt - letzte_aktivitaet >= settings.SITZUNG_INAKTIVITAET_SEKUNDEN
        or jetzt - sitzungsbeginn >= settings.SITZUNG_MAX_DAUER_SEKUNDEN
    ):
        melde_ab(anfrage)
        fehlerliste.append('Zugriff verweigert')
        return fehlerliste

    # Überprüfung, ob die Rolle für die angeforderte Aktion freigegeben ist
    if konto.rolle not in erlaubte_rollen:
        fehlerliste.append('Zugriff verweigert')
        return fehlerliste

    # Nach bestandenen Prüfungen die letzte Aktivität aktualisieren
    # Der Sitzungsbeginn bleibt unverändert
    anfrage.session['letzte_aktivitaet'] = jetzt
    return []  # Keine Fehler bei der Zugriffsprüfung


def aendere_passwort(anfrage: HttpRequest, bisheriges_passwort: str, neues_passwort: str) -> list[str]:
    """
    Ändert das Passwort des aktuell angemeldeten Benutzers.

    :param anfrage: Die HTTP-Anfrage, die die Passwortänderung auslöst.
    :param bisheriges_passwort: Das aktuelle Passwort des Benutzers.
    :param neues_passwort: Das neue Passwort, das gesetzt werden soll.
    :return: Eine Liste von Fehlermeldungen, falls die Validierung fehlschlägt, oder eine leere Liste bei Erfolg.

    1. Prüft, ob der Benutzer angemeldet ist.
    2. Prüft, ob das bisherige Passwort korrekt ist.
    3. Validiert das neue Passwort.
    4. Setzt das neue Passwort für den Benutzer und speichert es in der Datenbank.
    5. Gibt eine Liste von Fehlermeldungen zurück, falls eine der Prüfungen fehlschlägt, oder eine leere Liste bei Erfolg.
    6. Beendet die Funktion und gibt die Fehlermeldungen zurück, wenn der Benutzer nicht angemeldet ist oder das bisherige Passwort falsch ist.
    """
    fehlerliste = []  # Sammelt Fehlermeldungen der Passwortänderung

    # Das zur Sitzung gehörende Benutzerkonto ermitteln
    konto = get_user(anfrage)

    # Zugriff ohne gültige Anmeldung verweigern
    if not konto.is_authenticated:
        fehlerliste.append('Passwortänderung fehlgeschlagen')
        return fehlerliste

    # Überprüfung des bisherigen Passworts
    if not konto.check_password(bisheriges_passwort):
        fehlerliste.append('Passwortänderung fehlgeschlagen')
        return fehlerliste

    # Validierung des neuen Passworts
    try:
        validate_password(neues_passwort)
    except ValidationError as e:
        fehlerliste.extend(e.messages)
        return fehlerliste

    # Setzen des neuen Passworts
    konto.set_password(neues_passwort)  # Passwort wird gehasht
    konto.save()  # Speichern des aktualisierten Kontos in der Datenbank

    # Das bereits geprüfte Benutzerkonto an der Anfrage bereitstellen
    anfrage.user = konto

    # Mit Djangos Funktion update_session_auth_hash() den Prüfwert der Sitzung
    # aktualisieren, damit die Anmeldung nach der Passwortänderung gültig bleibt.
    update_session_auth_hash(anfrage, konto)

    return []  # Leere Fehlerliste nach erfolgreicher Passwortänderung zurückgeben