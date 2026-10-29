from django.shortcuts import render
from django.http import HttpRequest,HttpResponse, JsonResponse

from vp_stunden.sicherheit import melde_an, melde_ab, aendere_passwort, pruefe_zugriff, lege_konto_an, setze_passwort_zurueck
from vp_stunden.models import Benutzerkonto
from vp_stunden.vp_daten import loesche_teilnahmedaten,suche_teilnahmen, berechne_stunden, suche_untersuchungen, korrigiere_untersuchung
from vp_stunden.reports import erzeuge_report
from vp_stunden.importe import importiere_untersuchung, importiere_uebergangsdatei

def melde_an_view(anfrage: HttpRequest) -> JsonResponse:
    """
    Nimmt die Http-Anfrage entgegen, ruft melde_an() auf und liefert eine JSON-Antwort

    :param anfrage: Die Http-Anfrage, die die Anmeldedaten enthält.
    :return: Eine JSON-Antwort, die den Erfolg oder Misserfolg der Anmeldung angibt.
    """
    # Anmeldungen ausschließlich über die HTTP-Methode POST zulassen
    if anfrage.method != 'POST':
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'HTTP-Methode nicht erlaubt.'
            },
            status=405,  # Die verwendete HTTP-Methode ist nicht zugelassen
            headers={'Allow': 'POST'}  # Der Allow-Header nennt die erlaubte Methode
        )


    # Extrahiere die Anmeldedaten aus der Http-Anfrage
    benutzername = anfrage.POST.get('benutzername')
    passwort = anfrage.POST.get('passwort')

    # Überprüfe, ob die Anmeldedaten vorhanden sind
    if not benutzername or not passwort:
        return JsonResponse({'erfolg': False, 'nachricht': 'Ungültige Anmeldedaten.'}, status=400)

    # Rufe die Sicherheitsfunktion zur Anmeldung auf
    fehlerliste = melde_an(anfrage, benutzername, passwort)

    if fehlerliste:
        # `erfolg` und `nachricht` sind selbst gewählte Schlüssel. status ist ein Parameter von JsonResponse
        return JsonResponse(
            {
                'erfolg': False,  # Kennzeichnet die Anmeldung als fehlgeschlagen
                'nachricht': 'Anmeldung fehlgeschlagen.'  # Meldung für die Benutzeroberfläche
            },
            status=400  # HTTP-Statuscode: Die Anfrage wurde wegen fehlerhafter Angaben abgewiesen
        )
    else:
        # Ohne ausdrückliche status-Angabe verwendet JsonResponse HTTP-Status 200 (OK)
        return JsonResponse(
            {
                'erfolg': True,  # Kennzeichnet die Anmeldung als erfolgreich
                'nachricht': 'Anmeldung erfolgreich.'  # Meldung für die Benutzeroberfläche
            }
        )

def melde_ab_view(anfrage: HttpRequest) -> JsonResponse:
    """
    Nimmt die Http-Anfrage entgegen, ruft melde_ab() auf und liefert eine JSON-Antwort

    :param anfrage: Die HTTP-Anfrage mit der zu beendenden Sitzung.
    :return: Eine JSON-Antwort, die den Erfolg oder Misserfolg der Abmeldung angibt.

    1. Überprüft, ob die HTTP-Methode der Anfrage POST ist.
    2. Wenn die Methode nicht POST ist, gibt eine JSON-Antwort mit einem Fehlerstatus und einer entsprechenden Nachricht zurück.
    3. Ruft die Funktion melde_ab() auf, um die Anmeldung zu beenden und die Sitzung zu invalidieren.
    4. Gibt eine JSON-Antwort zurück, die den Erfolg der Abmeldung bestätigt.
    """
    # Abmeldungen ausschließlich über die HTTP-Methode POST zulassen
    if anfrage.method != 'POST':
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'HTTP-Methode nicht erlaubt.'
            },
            status=405,  # Die verwendete HTTP-Methode ist nicht zugelassen
            headers={'Allow': 'POST'}  # Der Allow-Header nennt die erlaubte Methode
        )

    # Die Anmeldung beenden und die serverseitige Sitzung ungültig machen
    melde_ab(anfrage)

    # Die erfolgreiche Abmeldung als JSON-Antwort bestätigen
    return JsonResponse(
        {
            'erfolg': True,
            'nachricht': 'Abmeldung erfolgreich.'
        }
    )

def aendere_passwort_view(anfrage: HttpRequest) -> JsonResponse:
    """
    Verarbeitet eine HTTP-Anfrage zur Änderung des eigenen Passworts.

    :param anfrage: Die HTTP-Anfrage mit bisherigem Passwort,
        neuem Passwort und Wiederholung des neuen Passworts.
    :return: Eine JSON-Antwort zum Ergebnis der Passwortänderung.

    1. Überprüft, ob die HTTP-Methode der Anfrage POST ist.
    2. Wenn die Methode nicht POST ist, gibt eine JSON-Antwort mit einem Fehlerstatus und einer entsprechenden Nachricht zurück.
    3. Extrahiert die Passwörter aus der Anfrage.
    4. Überprüft, ob alle Passwörter vorhanden sind und ob das neue Passwort korrekt wiederholt wurde.
    5. Prüft den Zugriff für die vorgesehenen Systemrollen (Lehrperson und Administrator).
    6. Ruft die Sicherheitsfunktion aendere_passwort() auf, um das Passwort zu ändern.
    7. Gibt eine JSON-Antwort zurück, die den Erfolg oder Misserfolg der Passwortänderung angibt.
    8. Bei Fehlern werden die entsprechenden Fehlermeldungen in der JSON-Antwort zurückgegeben.
    """

    # Passwortänderungen ausschließlich über die HTTP-Methode POST zulassen
    if anfrage.method != 'POST':
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'HTTP-Methode nicht erlaubt.'
            },
            status=405,  # Die verwendete HTTP-Methode ist nicht zugelassen
            headers={'Allow': 'POST'}  # Der Allow-Header nennt die erlaubte Methode
        )

    # Extrahiere die Passwörter aus der Http-Anfrage
    bisheriges_passwort = anfrage.POST.get('bisheriges_passwort')
    neues_passwort = anfrage.POST.get('neues_passwort')
    wiederholung_neues_passwort = anfrage.POST.get('wiederholung_neues_passwort')

    # Überprüfe, ob alle Passwörter vorhanden sind
    if not bisheriges_passwort or not neues_passwort or not wiederholung_neues_passwort:
        return JsonResponse({'erfolg': False, 'nachricht': 'Ungültige Passwortangaben.'}, status=400)

    # Unterschiedliche Eingaben für das neue Passwort abweisen
    if neues_passwort != wiederholung_neues_passwort:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Die neuen Passwörter stimmen nicht überein.'
            },
            status=400
        )

    # Den Zugriff für beide vorgesehenen Systemrollen prüfen
    fehlerliste_zugriff = pruefe_zugriff(
        anfrage,
        [Benutzerkonto.LEHRPERSON, Benutzerkonto.ADMINISTRATOR]
    )

    # Die Passwortänderung bei verweigertem Zugriff abbrechen
    if fehlerliste_zugriff:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Zugriff verweigert.'
            },
            status=403  # Der Zugriff auf die Aktion ist nicht gestattet
        )

    # Rufe die Sicherheitsfunktion zur Passwortänderung auf
    fehlerliste = aendere_passwort(anfrage, bisheriges_passwort, neues_passwort)

    if fehlerliste:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Passwortänderung fehlgeschlagen.',
                'fehlerliste': fehlerliste  # Liste der Fehler zurückgeben
            },
            status=400  # HTTP-Statuscode: Die Anfrage wurde wegen fehlerhafter Angaben abgewiesen
        )
    else:
        return JsonResponse(
            {
                'erfolg': True,
                'nachricht': 'Passwortänderung erfolgreich.'
            }
        )


def lege_konto_an_view(anfrage: HttpRequest) -> JsonResponse:
    """
    Verarbeitet die administrative Erstellung eines neuen Benutzerkontos.

    :param anfrage: Die HTTP-Anfrage mit Benutzernamen, Passwort und Rolle.
    :return: Eine JSON-Antwort zum Ergebnis der Kontoerstellung.

    1. Überprüft, ob die HTTP-Methode der Anfrage POST ist.
    2. Wenn die Methode nicht POST ist, gibt eine JSON-Antwort mit einem Fehlerstatus und einer entsprechenden Nachricht zurück.
    3. Extrahiert die Kontodaten (Benutzername, Passwort, Rolle) aus der Anfrage.
    4. Überprüft, ob alle Kontodaten vorhanden sind.
    5. Prüft den Zugriff für Administratoren.
    6. Ruft die Sicherheitsfunktion lege_konto_an() auf, um das Konto zu erstellen.
    7. Gibt eine JSON-Antwort zurück, die den Erfolg oder Misserfolg der Kontoerstellung angibt.
    8. Bei Fehlern werden die entsprechenden Fehlermeldungen in der JSON-Antwort zurückgegeben.
    9. Bei erfolgreicher Kontoerstellung wird eine Bestätigung in der JSON-Antwort zurückgegeben.
    10. Die Funktion stellt sicher, dass nur Administratoren neue Konten erstellen können.
    """

    # Kontoerstellungen ausschließlich über die HTTP-Methode POST zulassen
    if anfrage.method != 'POST':
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'HTTP-Methode nicht erlaubt.'
            },
            status=405,  # Die verwendete HTTP-Methode ist nicht zugelassen
            headers={'Allow': 'POST'}  # Der Allow-Header nennt die erlaubte Methode
        )

    # Extrahiere die Kontodaten aus der Http-Anfrage
    benutzername = anfrage.POST.get('benutzername')
    passwort = anfrage.POST.get('passwort')
    rolle = anfrage.POST.get('rolle')

    # Überprüfe, ob alle Kontodaten vorhanden sind
    if not benutzername or not passwort or not rolle:
        return JsonResponse({'erfolg': False, 'nachricht': 'Ungültige Kontodaten.'}, status=400)

    # Den Zugriff nur für Administratoren zulassen
    fehlerliste_zugriff = pruefe_zugriff(anfrage, [Benutzerkonto.ADMINISTRATOR])
    if fehlerliste_zugriff:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Zugriff verweigert.'
            },
            status=403  # Der Zugriff auf die Aktion ist nicht gestattet
        )


    # Rufe die Sicherheitsfunktion zur Kontoerstellung auf
    konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)

    if fehlerliste:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Kontoerstellung fehlgeschlagen.',
                'fehlerliste': fehlerliste  # Liste der Fehler zurückgeben
            },
            status=400  # HTTP-Statuscode: Die Anfrage wurde wegen fehlerhafter Angaben abgewiesen
        )
    else:
        return JsonResponse(
            {
                'erfolg': True,
                'nachricht': 'Kontoerstellung erfolgreich.'
            }
        )

def setze_passwort_zurueck_view(anfrage: HttpRequest) -> JsonResponse:
    """
    Verarbeitet das administrative Zurücksetzen eines Passworts.

    :param anfrage: Die HTTP-Anfrage mit der Konto-ID
        und dem neuen Passwort für dieses Konto.
    :return: Eine JSON-Antwort zum Ergebnis der Rücksetzung.

    1. Überprüft, ob die HTTP-Methode der Anfrage POST ist.
    2. Wenn die Methode nicht POST ist, gibt eine JSON-Antwort mit einem Fehlerstatus und einer entsprechenden Nachricht zurück.
    3. Extrahiert die Kontodaten (Konto-ID und neues Passwort) aus der Anfrage.
    4. Überprüft, ob alle Kontodaten vorhanden sind und ob die Konto-ID eine gültige Ganzzahl ist.
    5. Prüft den Zugriff für Administratoren.
    6. Ruft die Sicherheitsfunktion setze_passwort_zurueck() auf, um das Passwort zurückzusetzen.
    7. Gibt eine JSON-Antwort zurück, die den Erfolg oder Misserfolg der Passwortzurücksetzung angibt.
    8. Bei Fehlern werden die entsprechenden Fehlermeldungen in der JSON-Antwort zurückgegeben.
    9. Bei erfolgreicher Passwortzurücksetzung wird eine Bestätigung in der JSON-Antwort zurückgegeben.
    10. Die Funktion stellt sicher, dass nur Administratoren Passwörter zurücksetzen können.
    11. Die Konto-ID wird in eine Ganzzahl umgewandelt, um sicherzustellen, dass sie korrekt verarbeitet werden kann.
    12. Die Funktion behandelt auch den Fall, dass die Konto-ID keine gültige Ganzzahl ist, und gibt eine entsprechende Fehlermeldung zurück.
    13. Die Funktion verwendet die Sicherheitsfunktion setze_passwort_zurueck(), um die eigentliche Passwortzurücksetzung durchzuführen, und gibt die Ergebnisse in der JSON-Antwort zurück.
    14. Die Funktion stellt sicher, dass die Passwortzurücksetzung nur für Administratoren zugänglich ist, indem sie den Zugriff überprüft und bei verweigertem Zugriff eine entsprechende Fehlermeldung zurückgibt.
    """

    # Passwortzurücksetzungen ausschließlich über die HTTP-Methode POST zulassen
    if anfrage.method != 'POST':
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'HTTP-Methode nicht erlaubt.'
            },
            status=405,  # Die verwendete HTTP-Methode ist nicht zugelassen
            headers={'Allow': 'POST'}  # Der Allow-Header nennt die erlaubte Methode
        )

    # Extrahiere die Kontodaten aus der Http-Anfrage
    konto_id = anfrage.POST.get('konto_id')
    neues_passwort = anfrage.POST.get('neues_passwort')

    # Überprüfe, ob alle Kontodaten vorhanden sind
    if not konto_id or not neues_passwort:
        return JsonResponse({'erfolg': False, 'nachricht': 'Ungültige Kontodaten.'}, status=400)

    # Die Konto-ID aus dem Formulartext in eine Ganzzahl umwandeln
    try:
        konto_id = int(konto_id)
    except ValueError:
        # Angaben abweisen, die keine gültige Ganzzahl darstellen
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Ungültige Konto-ID.'
            },
            status=400
        )

    # Den Zugriff nur für Administratoren zulassen
    fehlerliste_zugriff = pruefe_zugriff(anfrage, [Benutzerkonto.ADMINISTRATOR])
    if fehlerliste_zugriff:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Zugriff verweigert.'
            },
            status=403  # Der Zugriff auf die Aktion ist nicht gestattet
        )

    # Rufe die Sicherheitsfunktion zum Zurücksetzen des Passworts auf
    fehlerliste = setze_passwort_zurueck(konto_id, neues_passwort)

    if fehlerliste:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Passwortzurücksetzung fehlgeschlagen.',
                'fehlerliste': fehlerliste  # Liste der Fehler zurückgeben
            },
            status=400  # HTTP-Statuscode: Die Anfrage wurde wegen fehlerhafter Angaben abgewiesen
        )
    else:
        return JsonResponse(
            {
                'erfolg': True,
                'nachricht': 'Passwortzurücksetzung erfolgreich.'
            }
        )


def loesche_teilnahmedaten_view(anfrage: HttpRequest) -> JsonResponse:
    """
    Verarbeitet die HTTP-Anfrage zum Löschen von Teilnahmedaten.

    :param anfrage: Die HTTP-Anfrage mit der Matrikelnummer und der Bestätigung der externen Ablage.
    :return: Eine JSON-Antwort zum Ergebnis der Löschung.

    1. Überprüft, ob die HTTP-Methode der Anfrage POST ist.
    2. Wenn die Methode nicht POST ist, gibt eine JSON-Antwort mit einem Fehlerstatus und einer entsprechenden Nachricht zurück.
    3. Extrahiert die Matrikelnummer und die Bestätigung der externen Ablage aus der Anfrage.
    4. Überprüft, ob alle erforderlichen Daten vorhanden sind.
    5. Prüft den Zugriff für Administratoren.
    6. Ruft die Funktion loesche_teilnahmedaten() auf, um die Teilnahmedaten zu löschen.
    7. Gibt eine JSON-Antwort zurück, die den Erfolg oder Misserfolg der Löschung angibt.
    8. Bei Fehlern werden die entsprechenden Fehlermeldungen in der JSON-Antwort zurückgegeben.
    9. Bei erfolgreicher Löschung wird eine Bestätigung in der JSON-Antwort zurückgegeben.
    10. Die Funktion stellt sicher, dass nur Administratoren Teilnahmedaten löschen können.
    """

    # Löschungen ausschließlich über die HTTP-Methode POST zulassen
    if anfrage.method != 'POST':
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'HTTP-Methode nicht erlaubt.'
            },
            status=405,  # Die verwendete HTTP-Methode ist nicht zugelassen
            headers={'Allow': 'POST'}  # Der Allow-Header nennt die erlaubte Methode
        )

    # Extrahiere die Matrikelnummer und die Bestätigung der externen Ablage aus der Http-Anfrage
    matrikelnummer = anfrage.POST.get('matrikelnummer')
    ablage_bestaetigt = anfrage.POST.get('ablage_bestaetigt') == 'true'

    # Überprüfe, ob alle erforderlichen Daten vorhanden sind
    if not matrikelnummer:
        return JsonResponse({'erfolg': False, 'nachricht': 'Ungültige Angaben.'}, status=400)

    # Den Zugriff nur für Administratoren zulassen
    fehlerliste_zugriff = pruefe_zugriff(anfrage, [Benutzerkonto.ADMINISTRATOR])
    if fehlerliste_zugriff:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Zugriff verweigert.'
            },
            status=403  # Der Zugriff auf die Aktion ist nicht gestattet
        )

    # Rufe die Funktion zum Löschen der Teilnahmedaten auf
    fehlerliste = loesche_teilnahmedaten(matrikelnummer, ablage_bestaetigt)

    if fehlerliste:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Löschung fehlgeschlagen.',
                'fehlerliste': fehlerliste  # Liste der Fehler zurückgeben
            },
            status=400  # HTTP-Statuscode: Die Anfrage wurde wegen fehlerhafter Angaben abgewiesen
        )
    else:
        return JsonResponse(
            {
                'erfolg': True,
                'nachricht': 'Löschung erfolgreich.'
            }
        )


def suche_teilnahmen_view(anfrage: HttpRequest) -> JsonResponse:
    """
    Verarbeitet die HTTP-Anfrage zur Suche von Teilnahmedaten.

    :param anfrage: Die HTTP-Anfrage mit der Matrikelnummer.
    :return: Eine JSON-Antwort mit den gefundenen Teilnahmedaten oder einer Fehlermeldung.

    """


    # Suchen ausschließlich über die HTTP-Methode POST zulassen
    if anfrage.method != 'POST':
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'HTTP-Methode nicht erlaubt.'
            },
            status=405,  # Die verwendete HTTP-Methode ist nicht zugelassen
            headers={'Allow': 'POST'}  # Der Allow-Header nennt die erlaubte Methode
        )

    # Extrahiere die Matrikelnummer aus der Http-Anfrage
    matrikelnummer = anfrage.POST.get('matrikelnummer')

    # Überprüfe, ob die Matrikelnummer vorhanden ist
    if not matrikelnummer:
        return JsonResponse({'erfolg': False, 'nachricht': 'Ungültige Angaben.'}, status=400)

    # Den Zugriff nur für Administratoren zulassen
    fehlerliste_zugriff = pruefe_zugriff(anfrage, [Benutzerkonto.ADMINISTRATOR])
    if fehlerliste_zugriff:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Zugriff verweigert.'
            },
            status=403  # Der Zugriff auf die Aktion ist nicht gestattet
        )

    # Rufe die Funktion zum Suchen der Teilnahmedaten auf
    teilnahmen = suche_teilnahmen(matrikelnummer)

    if not teilnahmen:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Keine Teilnahmedaten gefunden.'
            },
            status=404  # HTTP-Statuscode: Die angeforderten Daten wurden nicht gefunden
        )

    # Berechne die Stundenwerte und den Erfüllungsstatus der gefundenen Teilnahmen
    berechnung = berechne_stunden(teilnahmen)

    # Bereite die Teilnahmedaten für die JSON-Antwort vor
    teilnahmedaten = []

    # Füge die Informationen jeder Teilnahme in die Liste der Teilnahmedaten ein
    for teilnahme in teilnahmen:
        untersuchung = teilnahme.untersuchung
        teilnahmedaten.append({
            'matrikelnummer': teilnahme.matrikelnummer,
            'studienname' : untersuchung.studienname,
            'stundenwert': untersuchung.stundenwert,
            'einordnung': untersuchung.einordnung,
            'lehrperson': untersuchung.lehrperson,
            'uploadzeitpunkt' : untersuchung.uploadzeitpunkt
        })

    # Bereite die JSON-Antwort mit den Teilnahmedaten und der Berechnung vor
    return JsonResponse(
        {
            'erfolg': True,
            'nachricht': 'Teilnahmedaten erfolgreich gefunden.',
            'teilnahmen': teilnahmedaten,
            'berechnung': berechnung,
        }
    )


def suche_untersuchungen_view(anfrage: HttpRequest) -> JsonResponse:
    '''
    Durchsucht die Untersuchungen nach dem gegebenen Suchtext.

    :param anfrage: Die HTTP-Anfrage mit dem Suchtext.
    :return: Eine JSON-Antwort mit den gefundenen Untersuchungen oder einer Fehlermeldung.

    1. Überprüft, ob die HTTP-Methode der Anfrage POST ist.
    2. Wenn die Methode nicht POST ist, gibt eine JSON-Antwort mit einem Fehlerstatus und einer entsprechenden Nachricht zurück.
    3. Prüft den Zugriff für Administratoren.
    4. Extrahiert den Suchtext aus der Anfrage.
    5. Überprüft, ob der Suchtext vorhanden ist.
    6. Ruft die Funktion suche_untersuchungen() auf, um die Untersuchungen zu durchsuchen.
    7. Gibt eine JSON-Antwort zurück, die den Erfolg oder Misserfolg der Suche angibt.
    8. Bei Fehlern werden die entsprechenden Fehlermeldungen in der JSON-Antwort zurückgegeben.
    9. Bei erfolgreicher Suche werden die gefundenen Untersuchungen in der JSON-Antwort zurückgegeben.
    '''

    # Suchen ausschließlich über die HTTP-Methode POST zulassen
    if anfrage.method != 'POST':
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'HTTP-Methode nicht erlaubt.'
            },
            status=405,  # Die verwendete HTTP-Methode ist nicht zugelassen
            headers={'Allow': 'POST'}  # Der Allow-Header nennt die erlaubte Methode
        )

    # Nur Administratoren dürfen Untersuchungen durchsuchen
    fehlerliste_zugriff = pruefe_zugriff(anfrage, [Benutzerkonto.ADMINISTRATOR])
    if fehlerliste_zugriff:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Zugriff verweigert.'
            },
            status=403  # Der Zugriff auf die Aktion ist nicht gestattet
        )

    # Extrahiere den Suchtext aus der Http-Anfrage
    # get(...) liefert einen Text oder None, wenn der Schlüssel fehlt. is None weist deshalb ausschließlich den fehlenden Parameter ab.
    suchtext = anfrage.POST.get('suchtext')

    # Einen fehlenden Suchparameter abweisen
    if suchtext is None:
        return JsonResponse(
            {'erfolg': False, 'nachricht': 'Ungültige Angaben.'},
            status=400
        )

    # Die passenden Untersuchungen laden
    untersuchungen = suche_untersuchungen(suchtext)

    # Keinen Treffer gefunden
    if not untersuchungen:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Keine Untersuchungen gefunden.'
            },
            status=404  # HTTP-Statuscode: Die angeforderten Daten wurden nicht gefunden
        )

    # Die Untersuchungen für die JSON-Antwort vorbereiten
    untersuchungsdaten = []
    for untersuchung in untersuchungen:
        untersuchungsdaten.append({
            'untersuchung_id': untersuchung.pk,  # Primärschlüssel der Untersuchung hinzufügen
            'studienname': untersuchung.studienname,
            'stundenwert': untersuchung.stundenwert,
            'einordnung': untersuchung.einordnung,
            'lehrperson': untersuchung.lehrperson,
            'uploadzeitpunkt': untersuchung.uploadzeitpunkt.isoformat()  # Zeitpunkte in ISO-Format umwandeln
        })

    # Die JSON-Antwort mit den Untersuchungsdaten zurückgeben
    return JsonResponse(
        {
            'erfolg': True,
            'nachricht': 'Untersuchungen erfolgreich gefunden.',
            'untersuchungen': untersuchungsdaten,
        }
    )

def korrigiere_untersuchung_view(anfrage: HttpRequest) -> JsonResponse:
    '''
    Korrigiert eine bestehende Untersuchung.

    :param anfrage: Die HTTP-Anfrage mit den Korrekturdaten.
    :return: Eine JSON-Antwort zum Ergebnis der Korrektur.

    '''

    # Korrekturen ausschließlich über die HTTP-Methode POST zulassen
    if anfrage.method != 'POST':
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'HTTP-Methode nicht erlaubt.'
            },
            status=405,  # Die verwendete HTTP-Methode ist nicht zugelassen
            headers={'Allow': 'POST'}  # Der Allow-Header nennt die erlaubte Methode
        )

    # Nur Administratoren dürfen Untersuchungen korrigieren
    fehlerliste_zugriff = pruefe_zugriff(anfrage, [Benutzerkonto.ADMINISTRATOR])
    if fehlerliste_zugriff:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Zugriff verweigert.'
            },
            status=403  # Der Zugriff auf die Aktion ist nicht gestattet
        )

    # Extrahiere die Korrekturdaten aus der Http-Anfrage
    untersuchung_id = anfrage.POST.get('untersuchung_id')
    studienname = anfrage.POST.get('studienname')
    stundenwert = anfrage.POST.get('stundenwert')
    einordnung = anfrage.POST.get('einordnung')
    lehrperson = anfrage.POST.get('lehrperson')

    # Fehlende Parameter mit ihrer Feldbezeichnung melden.
    for feldname, wert in [
        ("Untersuchung", untersuchung_id),
        ("Studienname", studienname),
        ("Stundenwert", stundenwert),
        ("Einordnung", einordnung),
        ("Lehrperson", lehrperson),
    ]:
        if wert is None:
            return JsonResponse(
                {
                    'erfolg': False,
                    'nachricht': 'Ungültige Angaben.',
                    'fehlerliste': [f"{feldname}: Die Angabe fehlt."],
                },
                status=400,
            )

     # Den internen Untersuchungsschlüssel als Ganzzahl vorbereiten.
    try:
        untersuchung_id = int(untersuchung_id)
    except ValueError:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Ungültige Angaben.',
                'fehlerliste': [
                    'Untersuchung: Der Schlüssel muss eine ganze Zahl sein.'
                ],
            },
            status=400,
        )

    # Den Stundenwert als Fließkommazahl vorbereiten.
    try:
        stundenwert = float(stundenwert)
    except ValueError:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Ungültige Angaben.',
                'fehlerliste': ['Stundenwert: Eine Zahl ist erforderlich.'],
            },
            status=400,
        )

    # Die vorbereiteten Angaben prüfen und gemeinsam speichern.
    untersuchung, fehlerliste = korrigiere_untersuchung(
        untersuchung_id=untersuchung_id,
        studienname=studienname,
        stundenwert=stundenwert,
        einordnung=einordnung,
        lehrperson=lehrperson,
    )

    # Feldbezogene Fehlermeldungen an die Oberfläche weitergeben.
    if fehlerliste:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Untersuchungskorrektur fehlgeschlagen.',
                'fehlerliste': fehlerliste,
            },
            status=400,
        )

    # Die gespeicherten Untersuchungsangaben für die Tabellenanzeige liefern.
    return JsonResponse(
        {
            'erfolg': True,
            'nachricht': 'Untersuchung erfolgreich korrigiert.',
            'untersuchung': {
                'untersuchung_id': untersuchung.pk,
                'studienname': untersuchung.studienname,
                'stundenwert': untersuchung.stundenwert,
                'einordnung': untersuchung.einordnung,
                'lehrperson': untersuchung.lehrperson,
                'uploadzeitpunkt': untersuchung.uploadzeitpunkt.isoformat(),
            },
        }
    )


def erzeuge_report_view(anfrage: HttpRequest) -> HttpResponse:
    """
    Verarbeitet die administrative PDF-Reportanfrage für eine Matrikelnummer.

    :param anfrage: Die HTTP-Anfrage mit der Matrikelnummer.
    :return: Eine PDF-Downloadantwort oder eine JSON-Fehlerantwort.

    1. Überprüft, ob die HTTP-Methode der Anfrage POST ist.
    2. Wenn die Methode nicht POST ist, gibt eine JSON-Antwort mit einem Fehlerstatus und einer entsprechenden Nachricht zurück.
    3. Prüft den Zugriff für Administratoren.
    4. Extrahiert die Matrikelnummer aus der Anfrage.
    5. Überprüft, ob die Matrikelnummer vorhanden ist.
    6. Ruft die Funktion suche_teilnahmen() auf, um die Teilnahmedaten zu suchen.
    7. Überprüft, ob Teilnahmedaten gefunden wurden.
    8. Berechnet die Stundenwerte und den Erfüllungsstatus der gefundenen Teilnahmen.
    9. Überprüft, ob die Mindestvorgaben für einen Report erfüllt sind.
    10. Sortiert die gefundenen Teilnahmen nach ihrer internen ID aufsteigend.
    11. Ruft die Funktion erzeuge_report() auf, um den PDF-Inhalt zu erzeugen.
    12. Gibt eine PDF-Downloadantwort zurück, die den PDF-Inhalt enthält und den vorgeschlagenen Downloadnamen mit der Matrikelnummer angibt.
    """

    # Nur POST-Anfragen zulassen
    if anfrage.method != 'POST':
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'HTTP-Methode nicht erlaubt.'
            },
            status=405,  # Die verwendete HTTP-Methode ist nicht zugelassen
            headers={'Allow': 'POST'}  # Der Allow-Header nennt die erlaubte Methode
        )

    # Den Zugriff nur für Administratoren zulassen
    fehlerliste_zugriff = pruefe_zugriff(anfrage, [Benutzerkonto.ADMINISTRATOR])
    if fehlerliste_zugriff:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Zugriff verweigert.'
            },
            status=403  # Der Zugriff auf die Aktion ist nicht gestattet
        )

    # Matrikelnummer auslesen
    matrikelnummer = anfrage.POST.get('matrikelnummer')

    # Überprüfen, ob die Matrikelnummer vorhanden ist
    if not matrikelnummer:
        return JsonResponse({'erfolg': False, 'nachricht': 'Ungültige Angaben.'}, status=400)

    #Teilnahmedaten laden
    teilnahmen = suche_teilnahmen(matrikelnummer)

    # Überprüfen, ob Teilnahmedaten gefunden wurden
    if not teilnahmen:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Keine Teilnahmedaten gefunden.'
            },
            status=404  # HTTP-Statuscode: Die angeforderten Daten wurden nicht gefunden
        )

    # Berechnung der Stundenwerte und des Erfüllungsstatus der gefundenen Teilnahmen
    berechnung = berechne_stunden(teilnahmen)

    # Überprüfen, ob die Mindestvorgaben für einen Report erfüllt sind
    if not berechnung["erfuellt"]:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Die Mindestvorgaben für einen Report sind nicht erfüllt.',
            },
            status=400,
        )

    # Die bereits geladenen Teilnahmen nach ihrer internen ID aufsteigend ordnen.
    teilnahmen.sort(key=lambda teilnahme: teilnahme.pk)

    # Den PDF-Inhalt aus denselben Teilnahmen und ihrer Berechnung erzeugen.
    try:
        pdf_inhalt = erzeuge_report(
            matrikelnummer,
            teilnahmen,
            berechnung,
        )
    except Exception:
        # Technische Erzeugungsfehler ohne interne Fehlerdetails beantworten.
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Der Report konnte nicht erzeugt werden.',
            },
            status=500,
        )

    # Die Matrikelnummer in den vorgeschlagenen Downloadnamen aufnehmen.
    return HttpResponse(
        pdf_inhalt,
        content_type='application/pdf',
        headers={
            'Content-Disposition': (
                f'attachment; filename="vp_stunden_{matrikelnummer}.pdf"'
            ),
        },
    )

def importiere_untersuchung_view(anfrage: HttpRequest) -> JsonResponse:
    """
    Verarbeitet eine HTTP-Anfrage zum regulären Excel-Import.

    :param anfrage: Die HTTP-Anfrage mit der Excel-Datei.
    :return: Eine JSON-Antwort zum Ergebnis des Imports.


    """

    # Nur POST-Anfragen zulassen
    if anfrage.method != 'POST':
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'HTTP-Methode nicht erlaubt.'
            },
            status=405,  # Die verwendete HTTP-Methode ist nicht zugelassen
            headers={'Allow': 'POST'}  # Der Allow-Header nennt die erlaubte Methode
        )

    # Den Zugriff für Administratoren und Lehrpersonen zulassen
    fehlerliste_zugriff = pruefe_zugriff(anfrage, [Benutzerkonto.ADMINISTRATOR, Benutzerkonto.LEHRPERSON])
    if fehlerliste_zugriff:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Zugriff verweigert.'
            },
            status=403  # Der Zugriff auf die Aktion ist nicht gestattet
        )

    # Die Excel-Datei aus der Anfrage extrahieren
    excel_datei = anfrage.FILES.get('excel_datei')

    # Überprüfen, ob eine Datei hochgeladen wurde
    if not excel_datei:
        return JsonResponse({'erfolg': False, 'nachricht': 'Keine Datei hochgeladen.'}, status=400)

    # Die Importfunktion prüft die gesamte Datei und speichert nur gültige Daten.
    fehlerliste = importiere_untersuchung(excel_datei)

    if fehlerliste:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Import fehlgeschlagen.',
                'fehlerliste': fehlerliste  # Liste der Fehler zurückgeben
            },
            status=400  # HTTP-Statuscode: Die Anfrage wurde wegen fehlerhafter Angaben abgewiesen
        )
    else:
        return JsonResponse(
            {
                'erfolg': True,
                'nachricht': 'Import erfolgreich.'
            }
        )


def importiere_uebergangsdatei_view(anfrage: HttpRequest) -> JsonResponse:
    """
    Verarbeitet eine HTTP-Anfrage zum Import einer Übergangsdatei.

    :param anfrage: Die HTTP-Anfrage mit der Übergangsdatei.
    :return: Eine JSON-Antwort zum Ergebnis des Imports.

    """

    # Nur POST-Anfragen zulassen
    if anfrage.method != 'POST':
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'HTTP-Methode nicht erlaubt.'
            },
            status=405,  # Die verwendete HTTP-Methode ist nicht zugelassen
            headers={'Allow': 'POST'}  # Der Allow-Header nennt die erlaubte Methode
        )

    # Den Zugriff nur für Administratoren zulassen
    fehlerliste_zugriff = pruefe_zugriff(anfrage, [Benutzerkonto.ADMINISTRATOR])
    if fehlerliste_zugriff:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Zugriff verweigert.'
            },
            status=403  # Der Zugriff auf die Aktion ist nicht gestattet
        )

    # Die Übergangsdatei aus der Anfrage extrahieren
    uebergangsdatei = anfrage.FILES.get('uebergangsdatei')

    # Überprüfen, ob eine Datei hochgeladen wurde
    if not uebergangsdatei:
        return JsonResponse({'erfolg': False, 'nachricht': 'Keine Datei hochgeladen.'}, status=400)

    # Die Importfunktion prüft die gesamte Datei und speichert nur gültige Daten.
    fehlerliste = importiere_uebergangsdatei(uebergangsdatei)

    if fehlerliste:
        return JsonResponse(
            {
                'erfolg': False,
                'nachricht': 'Import fehlgeschlagen.',
                'fehlerliste': fehlerliste  # Liste der Fehler zurückgeben
            },
            status=400  # HTTP-Statuscode: Die Anfrage wurde wegen fehlerhafter Angaben abgewiesen
        )
    else:
        return JsonResponse(
            {
                'erfolg': True,
                'nachricht': 'Import erfolgreich.'
            }
        )

def zeige_oberflaeche_view(anfrage: HttpRequest) -> HttpResponse:
    """Liefert den gewählten Oberflächenbereich mit den erlaubten Funktionen."""
    # Der Adresszusatz bestimmt den angezeigten Bereich.
    bereich = anfrage.GET.get("bereich", "importe")
    if bereich not in ("administration", "importe", "suche"):
        bereich = "importe"

    # Der Suchbereich ist ausschließlich für Administrator:innen vorgesehen.
    if bereich == "suche" and not (
        anfrage.user.is_authenticated
        and anfrage.user.rolle == Benutzerkonto.ADMINISTRATOR
    ):
        bereich = "importe"

    konten = []

    # Die vorhandene Sitzungs- und Rollenprüfung beibehalten.
    if (
        anfrage.user.is_authenticated
        and anfrage.user.rolle == Benutzerkonto.ADMINISTRATOR
    ):
        fehlerliste_zugriff = pruefe_zugriff(
            anfrage, [Benutzerkonto.ADMINISTRATOR]
        )

        # Die Kontenauswahl wird nur im Administrationsbereich benötigt.
        if not fehlerliste_zugriff and bereich == "administration":
            konten = Benutzerkonto.objects.values(
                "id", "username", "rolle"
            ).order_by("username")

    return render(
        anfrage,
        "vp_stunden/oberflaeche.html",
        {"konten": konten, "bereich": bereich},
    )