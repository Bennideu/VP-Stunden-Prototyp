from django.shortcuts import render
from django.http import HttpRequest, JsonResponse

from vp_stunden.sicherheit import melde_an, melde_ab, aendere_passwort, pruefe_zugriff
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