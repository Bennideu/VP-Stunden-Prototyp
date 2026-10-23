from django.core.exceptions import ValidationError
from .models import Untersuchung

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