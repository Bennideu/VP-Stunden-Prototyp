from django.core.exceptions import ValidationError
from .models import Untersuchung, Teilnahme

def pruefe_einordnung(wert: object) -> str:
    '''
    Validiert die Einordnung einer Untersuchung.

    :param wert: Der zu validierende Wert
    :return: Der validierte Wert, falls er gültig ist
    '''

    if isinstance(wert, str) and wert in [Untersuchung.PRAESENZ, Untersuchung.ONLINE]:
        return wert
    else:
        raise ValidationError(f"Die Einordnung muss exakt P oder O sein.")


def pruefe_matrikelnummer(wert: object) -> str:
    """
    Prüft eine Matrikelnummer vom Typ int und gibt sie als Zeichenfolge zurück.

    :param wert: Der ungeprüfte Zellwert.
    :return: Die siebenstellige Matrikelnummer als Zeichenfolge.
    :raises ValidationError: Wenn der Zellwert ungültig ist.
    """
    fehlermeldung = "Die Matrikelnummer muss eine siebenstellige ganze Zahl sein."

    # Nur Ganzzahlen zulassen.
    # Wahrheitswerte ausschließen, da bool ein Untertyp von int ist.
    if isinstance(wert, bool) or not isinstance(wert, int):
        raise ValidationError(fehlermeldung)

    # Die Ganzzahl muss im siebenstelligen Bereich liegen.
    if not (1_000_000 <= wert <= 9_999_999):
        raise ValidationError(fehlermeldung)

    # Die geprüfte Ganzzahl als Zeichenfolge für die Speicherung zurückgeben.
    return str(wert)


def pruefe_lehrperson(wert: object) -> str:
    """
    Prüft den Lehrpersonennamen und entfernt äußere Leerzeichen.

    :param wert: Der ungeprüfte Zellwert.
    :return: Der bereinigte Lehrpersonennamen.
    :raises ValidationError: Wenn der Zellwert ungültig ist.
    """
    # Nur Zeichenfolgen zulassen.
    if not isinstance(wert, str):
        raise ValidationError("Der Name der Lehrperson muss als Text vorliegen.")

    # Äußere Leerzeichen entfernen, innere Leerzeichen erhalten.
    bereinigter_name = wert.strip()

    # Der bereinigte Name darf weder leer noch länger als 100 Zeichen sein.
    if not bereinigter_name or len(bereinigter_name) > 100:
        raise ValidationError(
            "Der Name der Lehrperson muss zwischen 1 und 100 Zeichen lang sein."
        )

    return bereinigter_name


def pruefe_studienname(wert: object) -> tuple[str, str]:
    """
    Prüft den Studiennamen und entfernt äußere Leerzeichen.

    :param wert: Der ungeprüfte Zellwert.
    :return: Ein Tupel aus bereinigtem Anzeigenamen und internem Vergleichswert.
    :raises ValidationError: Wenn der Zellwert ungültig ist.
    """

    # Nur Zeichenfolgen zulassen.
    if not isinstance(wert, str):
        raise ValidationError("Der Studienname muss als Text vorliegen.")

    # Äußere Leerzeichen entfernen, innere Leerzeichen erhalten.
    anzeigename = wert.strip()

    # Der bereinigte Name darf weder leer noch länger als 100 Zeichen sein.
    if not anzeigename or len(anzeigename) > 100:
        raise ValidationError(
            "Der Studienname muss zwischen 1 und 100 Zeichen lang sein."
        )

    # Vergleichswert bilden
    vergleichswert = anzeigename.casefold() # casefold() für universelle Kleinschreibung

    return anzeigename, vergleichswert


def pruefe_stundenwert(wert: object) -> float:
    """
    Prüft den Stundenwert und gibt ihn als Fließkommazahl zurück.

    :param wert: Der ungeprüfte Zellwert.
    :return: Der Stundenwert als Fließkommazahl.
    :raises ValidationError: Wenn der Zellwert ungültig ist.
    """
    # Nur Ganzzahlen oder Fließkommazahlen zulassen.
    if not isinstance(wert, (int, float)) or isinstance(wert, bool):  # Wahrheitswerte ausschließen, da bool ein Untertyp von int ist.
        raise ValidationError("Der Stundenwert muss eine Zahl sein.")

    # Der Stundenwert muss positiv sein.
    if wert <= 0:
        raise ValidationError("Der Stundenwert muss größer als 0 sein.")

    # Der Stundenwert muss ein Vielfaches von 0,5 sein
    if wert % 0.5 != 0 :
        raise ValidationError("Der Stundenwert muss ein Vielfaches von 0,5 sein.")

    return float(wert)


def berechne_stunden(teilnahmen: list[Teilnahme]) -> dict:
    """
    Berechnet die Gesamtstunden für jede Einordnung (Präsenz und Online) aus einer Liste von Teilnahmen.

    :param teilnahmen: Eine Liste von Teilnahme-Objekten.
    :return: Ein Dictionary mit Präsenz-, Online- und Gesamtstunden sowie dem Erfüllungsstatus.
    """
    praesenzstunden = 0.0
    onlinestunden = 0.0

    for t in teilnahmen:
        if t.untersuchung.einordnung == Untersuchung.PRAESENZ:
            praesenzstunden += t.untersuchung.stundenwert
        elif t.untersuchung.einordnung == Untersuchung.ONLINE:
            onlinestunden += t.untersuchung.stundenwert

    gesamtstunden = praesenzstunden + onlinestunden

    erfuellt = gesamtstunden >= 30 and praesenzstunden >= 15

    return {
        "praesenzstunden": praesenzstunden,
        "onlinestunden": onlinestunden,
        "gesamtstunden": gesamtstunden,
        "erfuellt": erfuellt
    }

def suche_teilnahmen(matrikelnummer: str) -> list[Teilnahme]:
    """
    Sucht alle Teilnahmen für eine gegebene Matrikelnummer.

    :param matrikelnummer: Die Matrikelnummer der Studierenden.
    :return: Eine Liste von Teilnahme-Objekten.
    """
    # Die Teilnahmen für die gegebene Matrikelnummer abfragen.
    abfrage = Teilnahme.objects.filter(matrikelnummer=matrikelnummer)

    # Die zugehörigen Untersuchungen abrufen
    abfrage = abfrage.select_related('untersuchung')

    # __ bedeutet, dass ueber die Beziehung untersuchung zum Feld studienname_vergleich gegangen wird.
    abfrage = abfrage.order_by('untersuchung__studienname_vergleich')  # Sortieren nach dem Vergleichswert des Studiennamens

    return list(abfrage)


def suche_untersuchungen(studienname: str) -> list[Untersuchung]:
    """
    Sucht Untersuchungen nach vollständigem Studiennamen oder enthaltenem Namensteil.

    :param studienname: Der vollständige Studienname oder ein Namensteil.
    :return: Eine nach Studiennamenvergleich sortierte Liste von Untersuchungen.
    """

    suchwert = studienname.casefold()  # Vergleichswert bilden

    abfrage = Untersuchung.objects.filter(studienname_vergleich__contains=suchwert)  # Teilstring-Suche im Vergleichswert
    abfrage = abfrage.order_by('studienname_vergleich')  # Sortieren nach dem Vergleichswert des Studiennamens

    return list(abfrage)
