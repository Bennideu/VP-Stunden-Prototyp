from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from .models import Untersuchung, Teilnahme

def pruefe_einordnung(wert: object) -> str:
    '''
    Validiert die Einordnung einer Untersuchung.

    :param wert: Der zu validierende Wert
    :return: Der validierte Wert, falls er gültig ist

    1. Der Wert muss eine Zeichenkette sein.
    2. Der Wert muss entweder 'P' (für Präsenz) oder 'O' (für Online) sein.
    3. Wenn der Wert gültig ist, wird er zurückgegeben, andernfalls wird eine ValidationError ausgelöst.
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

    1. Der Wert muss eine Zeichenfolge sein.
    2. Äußere Leerzeichen werden entfernt, innere Leerzeichen bleiben erhalten.
    3. Der bereinigte Name darf weder leer noch länger als 100 Zeichen sein.
    4. Wenn der Wert gültig ist, wird er zurückgegeben, andernfalls wird eine ValidationError ausgelöst.
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

    1. Der Wert muss eine Zeichenfolge sein.
    2. Äußere Leerzeichen werden entfernt, innere Leerzeichen bleiben erhalten.
    3. Der bereinigte Name darf weder leer noch länger als 100 Zeichen sein.
    4. Der Vergleichswert wird in Kleinschreibung erstellt.
    5. Wenn der Wert gültig ist, wird ein Tupel aus bereinigtem Anzeigenamen und internem Vergleichswert zurückgegeben, andernfalls wird eine ValidationError ausgelöst.
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

    1. Der Wert muss eine Zahl (int oder float) sein, Wahrheitswerte sind nicht erlaubt.
    2. Der Wert muss größer als 0 sein.
    3. Der Wert muss ein Vielfaches von 0,5 sein.
    4. Wenn der Wert gültig ist, wird er als Fließkommazahl zurückgegeben, andernfalls wird eine ValidationError ausgelöst.
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

    1. Die Funktion iteriert über die Liste der Teilnahmen.
    2. Für jede Teilnahme wird die Einordnung der zugehörigen Untersuchung überprüft.
    3. Die Stundenwerte werden entsprechend der Einordnung summiert.
    4. Die Gesamtstunden werden berechnet.
    5. Der Erfüllungsstatus wird bestimmt: erfüllt, wenn die Gesamtstunden >= 30 und die Präsenzstunden >= 15 sind.
    6. Ein Dictionary mit den berechneten Werten wird zurückgegeben.
    7. Wenn die Liste der Teilnahmen leer ist, werden alle Stunden auf 0 gesetzt und der Erfüllungsstatus auf False.
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

    1. Die Funktion filtert die Teilnahme-Objekte nach der gegebenen Matrikelnummer.
    2. Die zugehörigen Untersuchungen werden mit select_related abgerufen, um die Anzahl der Datenbankabfragen zu minimieren.
    3. Die Ergebnisse werden nach dem Vergleichswert des Studiennamens der zugehörigen Untersuchung sortiert.
    4. Die sortierte Liste der Teilnahmen wird zurückgegeben.
    5. Wenn keine Teilnahmen gefunden werden, wird eine leere Liste zurückgegeben.
    6. Die Funktion behandelt die Matrikelnummer als Zeichenfolge, um sicherzustellen, dass sie korrekt verglichen wird.
    7. Die Funktion gibt eine Liste von Teilnahme-Objekten zurück, die die Matrikelnummer enthalten, unabhängig davon, ob die Einordnung der Untersuchung Präsenz oder Online ist.
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

    1. Die Funktion erstellt einen Vergleichswert, indem der gegebene Studienname in Kleinschreibung umgewandelt wird.
    2. Die Untersuchungen werden gefiltert, um diejenigen zu finden, deren Vergleichswert den gegebenen Vergleichswert enthält.
    3. Die Ergebnisse werden nach dem Vergleichswert des Studiennamens sortiert.
    4. Die sortierte Liste der Untersuchungen wird zurückgegeben.
    5. Wenn keine Untersuchungen gefunden werden, wird eine leere Liste zurückgegeben.

    """

    suchwert = studienname.casefold()  # Vergleichswert bilden

    abfrage = Untersuchung.objects.filter(studienname_vergleich__contains=suchwert)  # Teilstring-Suche im Vergleichswert
    abfrage = abfrage.order_by('studienname_vergleich')  # Sortieren nach dem Vergleichswert des Studiennamens

    return list(abfrage)


def korrigiere_untersuchung(
        untersuchung_id: int,
        studienname: str,
        stundenwert: float,
        einordnung: str,
        lehrperson: str
) -> tuple[Untersuchung | None, list[str]]:
    """
    Korrigiert die Daten einer Untersuchung.

    :param untersuchung_id: Die ID der zu korrigierenden Untersuchung.
    :param studienname: Der neue Studienname.
    :param stundenwert: Der neue Stundenwert.
    :param einordnung: Die neue Einordnung (Präsenz oder Online).
    :param lehrperson: Der neue Name der Lehrperson.
    :return: Ein Tupel aus der korrigierten Untersuchung (oder None bei Fehlern) und einer Liste von Fehlermeldungen.

    1. Die Funktion validiert die Eingabewerte für Studienname, Stundenwert, Einordnung und Lehrperson.
    2. Wenn Validierungsfehler auftreten, werden diese in einer Liste gesammelt und zurückgegeben.
    3. Die Funktion versucht, die Untersuchung anhand der gegebenen ID zu laden.
    4. Wenn die Untersuchung nicht gefunden wird, wird eine entsprechende Fehlermeldung zurückgegeben.
    5. Die Funktion prüft, ob der neue Studienname bereits für eine andere Untersuchung vergeben ist.
    6. Wenn der Studienname bereits vergeben ist, wird eine entsprechende Fehlermeldung zurückgegeben.
    7. Wenn alle Prüfungen erfolgreich sind, werden die Änderungen an der Untersuchung innerhalb einer Datenbanktransaktion gespeichert.
    8. Bei einem Datenbankfehler wird eine entsprechende Fehlermeldung zurückgegeben.
    9. Nach erfolgreicher Speicherung wird das aktualisierte Untersuchung-Objekt zurückgegeben.
    10. Die Funktion gibt ein Tupel zurück, das entweder die korrigierte Untersuchung und eine leere Fehlermeldungsliste oder None und eine Liste von Fehlermeldungen enthält.
    """
    fehlerliste = []

    # Studienname prüfen und beide bereinigten Werte übernehmen
    try:
        anzeigename, vergleichswert = pruefe_studienname(studienname)
    except ValidationError as fehler:
        for meldung in fehler.messages:
            fehlerliste.append(f"Studienname: {meldung}")

    # Stundenwert prüfen
    try:
        stundenwert = pruefe_stundenwert(stundenwert)
    except ValidationError as fehler:
        for meldung in fehler.messages:
            fehlerliste.append(f"Stundenwert: {meldung}")

    # Einordnung prüfen
    try:
        einordnung = pruefe_einordnung(einordnung)
    except ValidationError as fehler:
        for meldung in fehler.messages:
            fehlerliste.append(f"Einordnung: {meldung}")

    # Lehrperson prüfen
    try:
        lehrperson = pruefe_lehrperson(lehrperson)
    except ValidationError as fehler:
        for meldung in fehler.messages:
            fehlerliste.append(f"Lehrperson: {meldung}")

    if fehlerliste:
        return None, fehlerliste

    # Die zu korrigierende Untersuchung anhand ihres Primärschlüssels laden.
    try:
        untersuchung = Untersuchung.objects.get(pk=untersuchung_id)
    except Untersuchung.DoesNotExist:
        return None, ["Untersuchung: Die ausgewählte Untersuchung wurde nicht gefunden."]

    # Beim Namensvergleich die bearbeitete Untersuchung selbst ausschließen.
    name_vergeben = Untersuchung.objects.filter(
        studienname_vergleich=vergleichswert
    ).exclude(pk=untersuchung.pk).exists()

    if name_vergeben:
        return None, ["Studienname: Dieser Studienname ist bereits vergeben."]

    # Die geprüften Angaben gemeinsam speichern.
    try:
        # atomic() sorgt dafür, dass die Änderungen entweder vollständig oder gar nicht gespeichert werden.
        with transaction.atomic():
            # Vier gemeinsame Angaben und den internen Vergleichswert übernehmen.
            untersuchung.studienname = anzeigename
            untersuchung.studienname_vergleich = vergleichswert
            untersuchung.stundenwert = stundenwert
            untersuchung.einordnung = einordnung
            untersuchung.lehrperson = lehrperson

            # Die fünf angegebenen Felder gemeinsam in der Datenbank aktualisieren.
            untersuchung.save(update_fields=[
                "studienname",
                "studienname_vergleich",
                "stundenwert",
                "einordnung",
                "lehrperson",
            ])

    except DatabaseError:
        return None, [
            "Untersuchung: Die Änderungen konnten nicht gespeichert werden."
        ]

    # Nach erfolgreicher Speicherung das aktualisierte Objekt zurückgeben.
    return untersuchung, []



def loesche_teilnahmedaten(matrikelnummer: str, ablage_bestaetigt: bool) -> list[str]:
    """
    Löscht alle Teilnahmedaten für eine gegebene Matrikelnummer.

    :param matrikelnummer: Die Matrikelnummer des Studierenden.
    :param ablage_bestaetigt: Ein boolescher Wert, der angibt, ob die externe Ablage des Reports bestätigt wurde.
    :return: Eine Liste von Fehlermeldungen, falls welche auftreten.

    1. Die Funktion lädt alle Teilnahmen für die gegebene Matrikelnummer und berechnet den Erfüllungsstatus.
    2. Wenn die Mindestanforderungen nicht erfüllt sind, wird eine Fehlermeldung zurückgegeben.
    3. Die Funktion speichert die IDs der betroffenen Untersuchungen, bevor die Teilnahmen gelöscht werden.
    4. Die Funktion löscht alle Teilnahmen für die gegebene Matrikelnummer innerhalb einer Datenbanktransaktion.
    5. Nach der Löschung der Teilnahmen prüft die Funktion, ob die betroffenen Untersuchungen noch Teilnahmen haben. Wenn nicht, werden diese Untersuchungen ebenfalls gelöscht.
    6. Wenn ein Datenbankfehler auftritt, wird eine entsprechende Fehlermeldung zurückgegeben.
    7. Die Funktion gibt eine Liste von Fehlermeldungen zurück, die entweder leer ist (bei Erfolg) oder die aufgetretenen Fehler enthält.
    """
    fehlerliste = []

    if not ablage_bestaetigt:
        fehlerliste.append(
            "Die Ablage der Daten muss bestätigt werden, bevor sie gelöscht werden können."
        )
        return fehlerliste

    try:
        # atomic() sorgt dafür, dass die Löschung entweder vollständig oder gar nicht durchgeführt wird.
        with transaction.atomic():
            # Den aktuellen Bestand laden und den Erfüllungsstatus erneut berechnen
            teilnahmen = suche_teilnahmen(matrikelnummer)
            berechnung = berechne_stunden(teilnahmen)

            if not berechnung["erfuellt"]:
                fehlerliste.append(
                    "Die Teilnahmedaten können nur gelöscht werden, wenn die Mindestanforderungen erfüllt sind."
                )
                return fehlerliste

            # Die betroffenen Untersuchungen vor der Teilnahmelöschung festhalten
            untersuchung_ids = []
            for teilnahme in teilnahmen:
                untersuchung_ids.append(teilnahme.untersuchung_id)

            # sämtliche Teilnahmen für die gegebene Matrikelnummer löschen
            Teilnahme.objects.filter(matrikelnummer=matrikelnummer).delete()

            # Die betroffenen Untersuchungen durchsuchen und prüfen, ob sie noch Teilnahmen haben
            for untersuchung_id in untersuchung_ids:
                if not Teilnahme.objects.filter(untersuchung_id=untersuchung_id).exists():
                    # Wenn keine Teilnahmen mehr existieren, die Untersuchung löschen
                    Untersuchung.objects.filter(pk=untersuchung_id).delete()

    except DatabaseError:
        fehlerliste.append(
            "Die Teilnahmedaten konnten nicht gelöscht werden."
        )

    return fehlerliste
