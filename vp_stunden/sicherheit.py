from django.contrib.auth.password_validation import validate_password # Bibliothek für Passwortvalidierung
from django.core.exceptions import ValidationError # Bibliothek für Fehlerbehandlung
from .models import Benutzerkonto # Import des benutzerdefinierten Benutzerkontos-Modells

def lege_konto_an(benutzername: str, passwort: str, rolle: str) -> tuple[Benutzerkonto | None, list[str]]:
    """
    Erstellt ein neues Benutzerkonto mit den angegebenen Parametern.

    :param benutzername: Der Benutzername für das neue Konto.
    :param passwort: Das Passwort für das neue Konto.
    :param rolle: Die Rolle des Benutzers (Lehrperson oder Administrator).
    :return: Das erstellte Benutzerkonto-Objekt.
    """
    Fehlerliste = []
    try:
        validate_password(passwort)
    except ValidationError as e:
        Fehlerliste.extend(e.messages)
        return None, Fehlerliste

    konto = Benutzerkonto(username=benutzername, rolle=rolle)
    konto.set_password(passwort)  # Passwort wird gehasht und dem Objekt angehangen
    konto.save()  # Speichert das Konto in der Datenbank
    return konto, []