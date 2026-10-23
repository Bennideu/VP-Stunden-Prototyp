from django.shortcuts import render
from django.http import HttpRequest, JsonResponse

from vp_stunden.sicherheit import melde_an, melde_ab, aendere_passwort, pruefe_zugriff, lege_konto_an, setze_passwort_zurueck
from vp_stunden.models import Benutzerkonto

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