# Anforderungsbezogene Tests für Passwörter, Benutzerkonten und Anmeldebegrenzung

from unittest.mock import DEFAULT, patch  # Einzelne Speicheraufrufe gezielt beeinflussen
from datetime import datetime # datetime wandelt Strings in Zeitpunkte um und erzeugt Zeitpunkte für die Tests
from django.db import DatabaseError, IntegrityError, transaction # Datenbankfehler erwarten und den Fehlversuch zurückrollen
from django.contrib.auth.password_validation import validate_password  # Die konfigurierten Django-Passwortregeln prüfen
from django.core.exceptions import ValidationError  # Ausnahme bei verletzten Validierungsregeln
from django.http import HttpRequest  # HTTP-Anfrageobjekte für direkte Funktionstests erzeugen
from django.test import SimpleTestCase  # Django-Testklasse ohne Datenbankzugriff
from django.utils import timezone  # Zeitzonenbewusste Zeitpunkte und Zeitabstände verwenden
from vp_stunden.models import Benutzerkonto, Untersuchung, Teilnahme  # Die benutzerdefinierten Modelle verwenden
from django.contrib.auth.hashers import get_hasher  # Den konfigurierten Passwort-Hasher abrufen
from django.test import TestCase  # Django-Testklasse für Tests mit Datenbankzugriff
from django.contrib.auth import get_user  # Konto anhand der Sitzungsdaten ermitteln
from vp_stunden.sicherheit import lege_konto_an, melde_an, melde_ab, pruefe_zugriff, setze_passwort_zurueck, aendere_passwort  # Zu prüfende Funktionen für Kontenanlage, Anmeldung, Abmeldung und Zugriffskontrolle
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.auth import SESSION_KEY, get_user
from django.db import IntegrityError, transaction  # Datenbankfehler erwarten und den Fehlversuch zurückrollen
from vp_stunden.vp_daten import pruefe_einordnung, pruefe_matrikelnummer, pruefe_lehrperson, pruefe_studienname, pruefe_stundenwert, berechne_stunden, suche_teilnahmen, suche_untersuchungen, korrigiere_untersuchung, loesche_teilnahmedaten  # Die Einordnungsvalidierung für Untersuchungen prüfen
from vp_stunden.reports import erzeuge_report  # Die Reportgenerierung prüfen
from vp_stunden.views import melde_an_view
from io import BytesIO  # XLSX-Dateien vollständig im Arbeitsspeicher erzeugen
from django.core.files.uploadedfile import SimpleUploadedFile  # Einen Speicherupload bereitstellen
from openpyxl import Workbook  # Eine Excel-Arbeitsmappe erzeugen
from vp_stunden.importe import (
    importiere_uebergangsdatei,
    importiere_untersuchung,
)# Passwortlängen und erlaubte Zeichenfolgen nach QA-01 prüfen
class PasswortregelnTests(SimpleTestCase):

    # 14 Zeichen unterschreiten die Mindestlänge und müssen abgewiesen werden
    def test_qa01_14_zeichen_werden_abgewiesen(self):
        with self.assertRaises(ValidationError):
            validate_password('a' * 14)  # Die Validierung muss eine Ausnahme auslösen


    # Die Mindestlänge von 15 Zeichen muss akzeptiert werden
    def test_qa01_15_zeichen_werden_akzeptiert(self):
        self.assertIsNone(validate_password('a' * 15))


    # Ein Passwort mit 64 Zeichen muss unterstützt werden
    def test_qa01_64_zeichen_werden_akzeptiert(self):
        self.assertIsNone(validate_password('a' * 64))


    # Auch 65 Zeichen werden ohne zusätzliche 64-Zeichen-Obergrenze akzeptiert
    def test_qa01_65_zeichen_werden_akzeptiert(self):
        self.assertIsNone(validate_password('a' * 65))


    # Ein ausreichend langes Zahlenpasswort muss ohne Zeichenklassenregeln akzeptiert werden
    def test_qa01_reines_zahlenpasswort_wird_akzeptiert(self):
        self.assertIsNone(validate_password('123456789012345'))



# Hashvergleich, Argon2id-Parameter und individuellen Salt prüfen
class PasswortHashingTests(SimpleTestCase):


    # Richtiges und falsches Passwort, Hashparameter und unterschiedliche Salts prüfen
    def test_qa01_passwortvergleich(self):
        # Synthetische Testwerte vorbereiten
        testpasswort = 'a' * 64
        konto = Benutzerkonto(username='testuser', rolle=Benutzerkonto.LEHRPERSON)
        konto.set_password(testpasswort)  # Passwort hashen und den kodierten Hash am Kontoobjekt setzen
        self.assertNotEqual(konto.password, testpasswort)
        self.assertTrue(konto.check_password(testpasswort))  # Das erwartete Passwort muss beim Hashvergleich akzeptiert werden


        testpasswort_falsch = 'a' * 63 + 'b'
        self.assertFalse(konto.check_password(testpasswort_falsch))  # Das bisherige oder abweichende Passwort muss abgewiesen werden


        # Den konfigurierten Standard-Hasher und seine Parameter prüfen
        hasher = get_hasher()  # Hasher-Objekt abrufen
        hasher_decoded = hasher.decode(konto.password)  # Algorithmus, Parameter und Salt aus dem kodierten Hash auslesen
        self.assertEqual(hasher_decoded['algorithm'], 'argon2')  # Den konfigurierten Hashalgorithmus prüfen
        self.assertEqual(hasher_decoded['time_cost'], 2)  # Die Anzahl der Iterationen prüfen
        self.assertEqual(hasher_decoded['memory_cost'], 102400)  # Den Speicherparameter in KiB prüfen
        self.assertEqual(hasher_decoded['parallelism'], 8)  # Den Parallelitätsparameter prüfen
        self.assertEqual(hasher_decoded['variety'], 'argon2id')  # Argon2id als verwendete Variante prüfen


        konto.set_password(testpasswort)  # Passwort hashen und den kodierten Hash am Kontoobjekt setzen
        hasher_decoded_neu = hasher.decode(konto.password)  # Algorithmus, Parameter und Salt aus dem kodierten Hash auslesen
        # Beim erneuten Hashen desselben Passworts müssen sich die Salts unterscheiden
        self.assertNotEqual(hasher_decoded['salt'], hasher_decoded_neu['salt'])



# Die Speicherung des Passwort-Hashes in der Datenbank prüfen
class PasswortspeicherungTests(TestCase):


    # Den gespeicherten Hash erneut aus der Datenbank laden und vergleichen
    def test_qa01_hash_wird_gespeichert(self):
        # Synthetische Testwerte vorbereiten
        testpasswort = 'a' * 64
        konto = Benutzerkonto(username='testuser', rolle=Benutzerkonto.LEHRPERSON)
        konto.set_password(testpasswort)  # Passwort hashen und den kodierten Hash am Kontoobjekt setzen
        passwort_hash = konto.password
        konto.save()  # Den vorbereiteten Kontozustand in der Testdatenbank speichern
        # Das gespeicherte Konto erneut aus der Datenbank laden
        konto_aus_db = Benutzerkonto.objects.get(username='testuser')
        self.assertEqual(konto_aus_db.password, passwort_hash)
        self.assertFalse(konto_aus_db.password == testpasswort)
        self.assertTrue(konto_aus_db.check_password(testpasswort))  # Das erwartete Passwort muss beim Hashvergleich akzeptiert werden



# Kontenanlage und Abweisung ungültiger Eingaben nach FA-02 und QA-01 prüfen
class KontoErstellungTests(TestCase):


    # Ein zu kurzes Passwort muss ohne Kontospeicherung abgewiesen werden
    def test_qa01_kurzes_passwort_verhindert_kontoerstellung(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 14
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNone(konto)
        self.assertTrue(fehlerliste)  # Mindestens eine Fehlermeldung erwarten
        self.assertFalse(Benutzerkonto.objects.filter(username=benutzername).exists())


    # Kontenanlage sowie gespeicherten Benutzernamen, Rolle und Passwort-Hash prüfen
    def test_fa02_erfolgreiche_kontoerstellung(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten
        self.assertTrue(Benutzerkonto.objects.filter(username=benutzername).exists())

        # Das gespeicherte Konto erneut aus der Datenbank laden
        benutzerkonto_aus_db = Benutzerkonto.objects.get(username=benutzername)
        self.assertTrue(benutzerkonto_aus_db.check_password(passwort))  # Das erwartete Passwort muss beim Hashvergleich akzeptiert werden
        self.assertEqual(benutzerkonto_aus_db.rolle, rolle)
        self.assertNotEqual(benutzerkonto_aus_db.password, passwort)
        self.assertEqual(benutzerkonto_aus_db.username, benutzername)



    # Eine unzulässige Rolle muss ohne Kontospeicherung abgewiesen werden
    def test_fa02_ungueltige_rolle_verhindert_kontoerstellung(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = 'ungültig'
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNone(konto)
        self.assertTrue(fehlerliste)  # Mindestens eine Fehlermeldung erwarten
        self.assertFalse(Benutzerkonto.objects.filter(username=benutzername).exists())

    # Zwei aufeinanderfolgende Anlageversuche dürfen nur ein Konto mit diesem Namen speichern
    def test_fa02_doppelte_benutzername_verhindert_kontoerstellung(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.LEHRPERSON

        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten


        konto2, fehlerliste2 = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNone(konto2)
        self.assertTrue(fehlerliste2)  # Mindestens eine Fehlermeldung erwarten
        self.assertTrue(Benutzerkonto.objects.filter(username=benutzername).count() == 1)


# Passwortzurücksetzen und unveränderten Bestand bei Fehlern prüfen
class PasswortZuruecksetzenTests(TestCase):


    # Das neue Passwort muss nach dem Zurücksetzen gültig und das bisherige ungültig sein
    def test_fa02_passwort_zuruecksetzen(self):

        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten


        neues_passwort = 'b' * 64
        # Die Rücksetzfunktion mit den vorbereiteten Eingaben aufrufen
        fehlerliste_zuruecksetzen = setze_passwort_zurueck(konto.pk, neues_passwort)
        self.assertFalse(fehlerliste_zuruecksetzen)  # Eine leere Fehlerliste erwarten
        # Die Prüfungen auf den tatsächlich gespeicherten Datenbankzustand beziehen
        konto.refresh_from_db()  # Kontoobjekt aus der Datenbank aktualisieren
        self.assertTrue(konto.check_password(neues_passwort))  # Das erwartete Passwort muss beim Hashvergleich akzeptiert werden
        self.assertFalse(konto.check_password(passwort))  # Das bisherige oder abweichende Passwort muss abgewiesen werden


    # Ein zu kurzes neues Passwort muss den bisherigen gespeicherten Hash unverändert lassen
    def test_qa01_zu_kurzes_passwort_laesst_altes_passwort_unveraendert(self):

        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten


        zu_kurzes_passwort = 'c' * 14
        passwort_hash_vorher = konto.password
        # Die Rücksetzfunktion mit den vorbereiteten Eingaben aufrufen
        fehlerliste_zuruecksetzen = setze_passwort_zurueck(konto.pk, zu_kurzes_passwort)
        self.assertTrue(fehlerliste_zuruecksetzen)  # Mindestens eine Fehlermeldung erwarten
        # Die Prüfungen auf den tatsächlich gespeicherten Datenbankzustand beziehen
        konto.refresh_from_db()  # Kontoobjekt aus der Datenbank aktualisieren
        self.assertEqual(konto.password, passwort_hash_vorher)
        self.assertTrue(konto.check_password(passwort))  # Das erwartete Passwort muss beim Hashvergleich akzeptiert werden
        self.assertFalse(konto.check_password(zu_kurzes_passwort))  # Das bisherige oder abweichende Passwort muss abgewiesen werden


    # Das Zurücksetzen für eine nachweislich fehlende Konto-ID muss abgewiesen werden
    def test_fa02_nicht_vorhandenes_konto_wird_abgewiesen(self):

        konto_id = 1
        self.assertFalse(Benutzerkonto.objects.filter(pk=konto_id).exists())
        neues_passwort = 'b' * 64
        # Die Rücksetzfunktion mit den vorbereiteten Eingaben aufrufen
        fehlerliste_zuruecksetzen = setze_passwort_zurueck(konto_id, neues_passwort)
        self.assertTrue(fehlerliste_zuruecksetzen)  # Mindestens eine Fehlermeldung erwarten
        self.assertFalse(Benutzerkonto.objects.filter(pk=konto_id).exists())


# Fehlversuchsschwelle, feste Zeitfenster, Sperren und Rücksetzregeln nach QA-02 prüfen
class AnmeldeTests(TestCase):

    # Eine aktive Sperre muss auch das richtige Passwort abweisen und ihr Ende beibehalten
    def test_qa02_aktive_sperre_verhindert_anmeldung(self):

        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten


        # Eine bestehende aktive Sperre vorbereiten
        konto.gesperrt_bis = timezone.now() + timezone.timedelta(minutes=5)
        sperrende_vorher = konto.gesperrt_bis
        konto.save()  # Den vorbereiteten Kontozustand in der Testdatenbank speichern


        anfrage = HttpRequest()
        anfrage.session = self.client.session
        # Den Anmeldeversuch mit dem vorbereiteten Konto ausführen
        fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort)
        self.assertTrue(fehlerliste_anmeldung)  # Mindestens eine Fehlermeldung erwarten
        self.assertIn("Anmeldung fehlgeschlagen", fehlerliste_anmeldung[0])

        # Nach der Abweisung muss die Sitzung weiterhin unangemeldet sein
        self.assertFalse(get_user(anfrage).is_authenticated)

        # Die Prüfungen auf den tatsächlich gespeicherten Datenbankzustand beziehen
        konto.refresh_from_db()  # Kontoobjekt aus der Datenbank aktualisieren
        self.assertEqual(konto.gesperrt_bis, sperrende_vorher)

    # Genau am Sperrende muss der gespeicherte Fehlversuchs- und Sperrzustand zurückgesetzt werden
    def test_qa02_sperrende_setzt_sperrzustand_zurueck(self):

        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten

        # Prüfzeitpunkt und gespeicherten Ausgangszustand vorbereiten
        testzeitpunkt = timezone.now()
        konto.fehlversuche = 5
        konto.fehlversuchszeitraum_beginn = testzeitpunkt - timezone.timedelta(minutes=10)
        konto.gesperrt_bis = testzeitpunkt
        konto.save()  # Den vorbereiteten Kontozustand in der Testdatenbank speichern


        anfrage = HttpRequest()
        anfrage.session = self.client.session  # Sitzungsobjekt für den direkten Funktionsaufruf bereitstellen
        # Die Anmeldung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=testzeitpunkt):
            fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort)
        self.assertFalse(fehlerliste_anmeldung)  # Eine leere Fehlerliste erwarten

        # Die Prüfungen auf den tatsächlich gespeicherten Datenbankzustand beziehen
        konto.refresh_from_db()  # Kontoobjekt aus der Datenbank aktualisieren
        self.assertIsNone(konto.gesperrt_bis)
        self.assertEqual(konto.fehlversuche, 0)
        self.assertIsNone(konto.fehlversuchszeitraum_beginn)


    # Genau am Ende des 15-Minuten-Fensters muss die bisherige Zählung zurückgesetzt werden
    def test_qa02_fensterende_setzt_fehlversuche_zurueck(self):

        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten

        # Prüfzeitpunkt und gespeicherten Ausgangszustand vorbereiten
        testzeitpunkt = timezone.now()
        konto.fehlversuche = 3
        konto.fehlversuchszeitraum_beginn = testzeitpunkt - timezone.timedelta(minutes=15)
        konto.save()  # Den vorbereiteten Kontozustand in der Testdatenbank speichern


        anfrage = HttpRequest()
        anfrage.session = self.client.session  # Sitzungsobjekt für den direkten Funktionsaufruf bereitstellen
        # Die Anmeldung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=testzeitpunkt):
            fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort)
        self.assertFalse(fehlerliste_anmeldung)  # Eine leere Fehlerliste erwarten
        # Die Prüfungen auf den tatsächlich gespeicherten Datenbankzustand beziehen
        konto.refresh_from_db()  # Kontoobjekt aus der Datenbank aktualisieren
        self.assertEqual(konto.fehlversuche, 0)
        self.assertIsNone(konto.fehlversuchszeitraum_beginn)
        self.assertIsNone(konto.gesperrt_bis)

    # Der fünfte Fehlversuch innerhalb des Fensters muss eine fünfminütige Sperre auslösen
    def test_qa02_fuenfter_fehlversuch_sperrt_fuenf_minuten(self):

        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten

        # Prüfzeitpunkt und gespeicherten Ausgangszustand vorbereiten
        testzeitpunkt = timezone.now()
        fensterbeginn_vorher = testzeitpunkt - timezone.timedelta(minutes=1)

        konto.fehlversuche = 4
        konto.fehlversuchszeitraum_beginn = fensterbeginn_vorher
        konto.save()  # Den vorbereiteten Kontozustand in der Testdatenbank speichern

        anfrage = HttpRequest()
        # Die Anmeldung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=testzeitpunkt):
            fehlerliste_anmeldung = melde_an(anfrage, benutzername, 'falsches_passwort')
        self.assertTrue(fehlerliste_anmeldung)  # Mindestens eine Fehlermeldung erwarten
        # Die Prüfungen auf den tatsächlich gespeicherten Datenbankzustand beziehen
        konto.refresh_from_db()  # Kontoobjekt aus der Datenbank aktualisieren
        self.assertEqual(konto.fehlversuche,5)
        self.assertEqual(konto.fehlversuchszeitraum_beginn,fensterbeginn_vorher)
        self.assertEqual(testzeitpunkt + timezone.timedelta(minutes=5),konto.gesperrt_bis)


    # Der vierte Fehlversuch muss gezählt werden und darf noch keine Sperre auslösen
    def test_qa02_vierter_fehlversuch_sperrt_nicht(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)

        # Prüfzeitpunkt und gespeicherten Ausgangszustand vorbereiten
        testzeitpunkt = timezone.now()
        konto.fehlversuche = 3
        konto.fehlversuchszeitraum_beginn = testzeitpunkt - timezone.timedelta(minutes=1)
        konto.save()  # Den vorbereiteten Kontozustand in der Testdatenbank speichern

        anfrage = HttpRequest()
        anfrage.session = self.client.session
        # Die Anmeldung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=testzeitpunkt):
            fehlerliste = melde_an(anfrage, benutzername, passwort='falschesPW')
        self.assertTrue(fehlerliste)  # Mindestens eine Fehlermeldung erwarten

        # Nach der Abweisung muss die Sitzung weiterhin unangemeldet sein
        self.assertFalse(get_user(anfrage).is_authenticated)

        # Die Prüfungen auf den tatsächlich gespeicherten Datenbankzustand beziehen
        konto.refresh_from_db()  # Kontoobjekt aus der Datenbank aktualisieren
        self.assertEqual(konto.fehlversuche,4)
        self.assertEqual(konto.fehlversuchszeitraum_beginn, testzeitpunkt - timezone.timedelta(minutes=1))
        self.assertIsNone(konto.gesperrt_bis)


    # Ein weiterer Versuch während der Sperre darf Zähler, Fensterbeginn und Sperrende nicht ändern
    def test_qa02_sechster_Versuch_verlaengert_sperre_nicht(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)

        # Prüfzeitpunkt und gespeicherten Ausgangszustand vorbereiten
        testzeitpunkt = timezone.now()
        konto.fehlversuche = 5
        konto.fehlversuchszeitraum_beginn = testzeitpunkt - timezone.timedelta(minutes=2)
        sperrende_vorher = testzeitpunkt + timezone.timedelta(minutes=4)
        konto.gesperrt_bis = sperrende_vorher

        konto.save()  # Den vorbereiteten Kontozustand in der Testdatenbank speichern

        anfrage = HttpRequest()
        # Die Anmeldung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=testzeitpunkt):
            fehlerliste = melde_an(anfrage, benutzername, passwort='falschesPW')
        self.assertTrue(fehlerliste)  # Mindestens eine Fehlermeldung erwarten
        # Die Prüfungen auf den tatsächlich gespeicherten Datenbankzustand beziehen
        konto.refresh_from_db()  # Kontoobjekt aus der Datenbank aktualisieren
        self.assertEqual(konto.fehlversuche,5)
        self.assertEqual(konto.gesperrt_bis, sperrende_vorher)
        self.assertEqual(konto.fehlversuchszeitraum_beginn, testzeitpunkt - timezone.timedelta(minutes=2))


    # Ein falsches Passwort genau am Fensterende muss als erster Versuch eines neuen Fensters zählen
    def test_qa02_fehlversuch_am_fensterende_beginnt_neues_fenster(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 15
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten
        # Prüfzeitpunkt und gespeicherten Ausgangszustand vorbereiten
        testzeitpunkt = timezone.now()
        konto.fehlversuche = 4
        konto.fehlversuchszeitraum_beginn = (testzeitpunkt - timezone.timedelta(minutes=15))
        konto.gesperrt_bis = None
        konto.save()  # Den vorbereiteten Kontozustand in der Testdatenbank speichern

        anfrage = HttpRequest()
        # Die Anmeldung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=testzeitpunkt,):
            fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort='falschesPW')
        self.assertTrue(fehlerliste_anmeldung)  # Mindestens eine Fehlermeldung erwarten

        # Die Prüfungen auf den tatsächlich gespeicherten Datenbankzustand beziehen
        konto.refresh_from_db()  # Kontoobjekt aus der Datenbank aktualisieren
        self.assertEqual(konto.fehlversuche, 1)
        self.assertEqual(konto.fehlversuchszeitraum_beginn, testzeitpunkt)
        self.assertIsNone(konto.gesperrt_bis)


    # Eine Sekunde vor Fensterende müssen die vier bisherigen Fehlversuche noch zählen
    def test_qa02_fehlversuch_kurz_vor_fensterende_sperrt(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 15
        rolle = Benutzerkonto.LEHRPERSON

        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten

        # Prüfzeitpunkt und gespeicherten Ausgangszustand vorbereiten
        testzeitpunkt = timezone.now()
        fensterbeginn_vorher = testzeitpunkt - timezone.timedelta(minutes=14, seconds=59)

        konto.fehlversuche = 4
        konto.fehlversuchszeitraum_beginn = fensterbeginn_vorher
        konto.gesperrt_bis = None
        konto.save()  # Den vorbereiteten Kontozustand in der Testdatenbank speichern

        anfrage = HttpRequest()
        # Die Anmeldung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now',return_value=testzeitpunkt,):
            fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort= 'falschesPW')

        self.assertTrue(fehlerliste_anmeldung)  # Mindestens eine Fehlermeldung erwarten
        # Die Prüfungen auf den tatsächlich gespeicherten Datenbankzustand beziehen
        konto.refresh_from_db()  # Kontoobjekt aus der Datenbank aktualisieren
        self.assertEqual(konto.fehlversuche, 5)
        self.assertEqual(konto.fehlversuchszeitraum_beginn,fensterbeginn_vorher,)
        self.assertEqual(konto.gesperrt_bis,testzeitpunkt + timezone.timedelta(minutes=5))



    # Eine Sekunde nach Fensterende muss ein neues Fenster mit einem Fehlversuch beginnen
    def test_qa02_fehlversuch_nach_fensterende_beginnt_neues_fenster(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 15
        rolle = Benutzerkonto.LEHRPERSON

        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten

        # Prüfzeitpunkt und gespeicherten Ausgangszustand vorbereiten
        testzeitpunkt = timezone.now()
        konto.fehlversuche = 4
        konto.fehlversuchszeitraum_beginn = (testzeitpunkt - timezone.timedelta(minutes=15, seconds=1))
        konto.gesperrt_bis = None
        konto.save()  # Den vorbereiteten Kontozustand in der Testdatenbank speichern

        anfrage = HttpRequest()
        # Die Anmeldung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now',return_value=testzeitpunkt,):
            fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort='falschesPW')

        self.assertTrue(fehlerliste_anmeldung)  # Mindestens eine Fehlermeldung erwarten
        # Die Prüfungen auf den tatsächlich gespeicherten Datenbankzustand beziehen
        konto.refresh_from_db()  # Kontoobjekt aus der Datenbank aktualisieren
        self.assertEqual(konto.fehlversuche, 1)
        self.assertEqual(konto.fehlversuchszeitraum_beginn, testzeitpunkt)
        self.assertIsNone(konto.gesperrt_bis)

    # Eine Sekunde vor Sperrende muss das richtige Passwort weiterhin abgewiesen werden
    def test_qa02_kurz_vor_sperrende_bleibt_konto_gesperrt(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 15
        rolle = Benutzerkonto.LEHRPERSON

        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten

        # Prüfzeitpunkt und gespeicherten Ausgangszustand vorbereiten
        testzeitpunkt = timezone.now()
        fensterbeginn_vorher = testzeitpunkt - timezone.timedelta(minutes=10)
        sperrende_vorher = testzeitpunkt + timezone.timedelta(seconds=1)

        konto.fehlversuche = 5
        konto.fehlversuchszeitraum_beginn = fensterbeginn_vorher
        konto.gesperrt_bis = sperrende_vorher
        konto.save()  # Den vorbereiteten Kontozustand in der Testdatenbank speichern

        anfrage = HttpRequest()
        # Die Anmeldung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now',return_value=testzeitpunkt,):
            fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort)

        self.assertTrue(fehlerliste_anmeldung)  # Mindestens eine Fehlermeldung erwarten
        # Die Prüfungen auf den tatsächlich gespeicherten Datenbankzustand beziehen
        konto.refresh_from_db()  # Kontoobjekt aus der Datenbank aktualisieren
        self.assertEqual(konto.fehlversuche, 5)
        self.assertEqual(konto.fehlversuchszeitraum_beginn,fensterbeginn_vorher,)
        self.assertEqual(konto.gesperrt_bis, sperrende_vorher)

    # Nach Sperrende muss ein falsches Passwort eine neue Zählung beginnen
    def test_qa02_fehlversuch_nach_sperrende_beginnt_neues_fenster(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 15
        rolle = Benutzerkonto.LEHRPERSON

        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten

        # Prüfzeitpunkt und gespeicherten Ausgangszustand vorbereiten
        testzeitpunkt = timezone.now()
        konto.fehlversuche = 5
        konto.fehlversuchszeitraum_beginn = (testzeitpunkt - timezone.timedelta(minutes=10))
        konto.gesperrt_bis = testzeitpunkt - timezone.timedelta(seconds=1)
        konto.save()  # Den vorbereiteten Kontozustand in der Testdatenbank speichern

        anfrage = HttpRequest()
        # Die Anmeldung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now',return_value=testzeitpunkt,):
            fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort= 'falschesPW')

        self.assertTrue(fehlerliste_anmeldung)  # Mindestens eine Fehlermeldung erwarten
        # Die Prüfungen auf den tatsächlich gespeicherten Datenbankzustand beziehen
        konto.refresh_from_db()  # Kontoobjekt aus der Datenbank aktualisieren
        self.assertEqual(konto.fehlversuche, 1)
        self.assertEqual(konto.fehlversuchszeitraum_beginn, testzeitpunkt)
        self.assertIsNone(konto.gesperrt_bis)


    # Ein richtiges Passwort muss die Zählung auch innerhalb eines noch laufenden Fensters zurücksetzen
    def test_qa02_richtiges_passwort_setzt_fehlversuche_zurueck(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 15
        rolle = Benutzerkonto.LEHRPERSON

        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten

        # Prüfzeitpunkt und gespeicherten Ausgangszustand vorbereiten
        testzeitpunkt = timezone.now()
        konto.fehlversuche = 4
        konto.fehlversuchszeitraum_beginn = (testzeitpunkt - timezone.timedelta(minutes=1))
        konto.gesperrt_bis = None
        konto.save()  # Den vorbereiteten Kontozustand in der Testdatenbank speichern

        anfrage = HttpRequest()
        anfrage.session = self.client.session  # Sitzungsobjekt für den direkten Funktionsaufruf bereitstellen
        # Die Anmeldung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now',return_value=testzeitpunkt,):
            fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort)

        self.assertFalse(fehlerliste_anmeldung)  # Eine leere Fehlerliste erwarten

        # Wiedererkennung des angemeldeten Kontos nach FA-01 prüfen
        angemeldetes_konto = get_user(anfrage)
        self.assertTrue(angemeldetes_konto.is_authenticated)
        self.assertEqual(angemeldetes_konto.pk, konto.pk)

        anfrage.session.save()
        gespeicherte_sitzung = SessionStore(session_key=anfrage.session.session_key)

        self.assertEqual(gespeicherte_sitzung['sitzungsbeginn'], testzeitpunkt.timestamp())
        self.assertEqual(gespeicherte_sitzung['letzte_aktivitaet'], testzeitpunkt.timestamp())

        # Die Prüfungen auf den tatsächlich gespeicherten Datenbankzustand beziehen
        konto.refresh_from_db()  # Kontoobjekt aus der Datenbank aktualisieren
        self.assertEqual(konto.fehlversuche, 0)
        self.assertIsNone(konto.fehlversuchszeitraum_beginn)
        self.assertIsNone(konto.gesperrt_bis)


class AbmeldeTests(TestCase):
    def test_qa03_abmeldung_macht_sitzung_ungueltig(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)

        # Die Anmeldung ausführen und die Authentifizierung prüfen
        anfrage = HttpRequest()
        anfrage.session = self.client.session
        fehlerliste = melde_an(anfrage, benutzername, passwort=passwort)
        self.assertFalse(fehlerliste)
        self.assertTrue(get_user(anfrage).is_authenticated)

        # Die Sitzung speichern und die Sitzungskennung überprüfen
        anfrage.session.save()
        alte_sitzungskennung = anfrage.session.session_key
        self.assertTrue(anfrage.session.exists(alte_sitzungskennung))

        # Die Abmeldung ausführen und die Sitzung auf Ungültigkeit prüfen
        melde_ab(anfrage)
        self.assertFalse(get_user(anfrage).is_authenticated)
        self.assertFalse(anfrage.session.exists(alte_sitzungskennung))


class ZugriffsTests(TestCase):

    # Zugriff auf ein Konto muss ohne Anmeldung verweigert werden
    def test_qa04_ohne_anmeldung_wird_zugriff_verweigert(self):
        # Synthetische Testwerte vorbereiten
        anfrage = HttpRequest()
        anfrage.session = self.client.session

        # Die Zugriffsprüfung ausführen und die erwartete Fehlermeldung prüfen
        fehlerliste = pruefe_zugriff(anfrage, [Benutzerkonto.LEHRPERSON])
        self.assertTrue(fehlerliste)
        self.assertFalse(get_user(anfrage).is_authenticated)

    # Zugriff auf ein Konto mit der richtigen Rolle muss gewährt werden
    def test_qa04_erlaubte_rolle_erhaelt_zugriff(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.LEHRPERSON

        # Den Testzeitpunkt festlegen
        testzeitpunkt = timezone.now()
        zugriffszeitpunkt = testzeitpunkt + timezone.timedelta(minutes=5)

        # HttpRequest-Objekt mit der Testsession vorbereiten
        anfrage = HttpRequest()
        anfrage.session = self.client.session

        # Die Anmeldung ausführen und die Authentifizierung prüfen
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)

        # Die Anmeldung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=testzeitpunkt):
            fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort)
        self.assertFalse(fehlerliste_anmeldung)

        # Die Zugriffsprüfung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=zugriffszeitpunkt):
            fehlerliste = pruefe_zugriff(anfrage, [Benutzerkonto.LEHRPERSON])

        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten
        self.assertTrue(get_user(anfrage).is_authenticated)

        # Neue SessionStore Instanz laden, um die gespeicherte Sitzung zu prüfen
        anfrage.session.save()
        gespeicherte_sitzung = SessionStore(session_key=anfrage.session.session_key)
        self.assertEqual(gespeicherte_sitzung['sitzungsbeginn'], testzeitpunkt.timestamp())
        self.assertEqual(gespeicherte_sitzung['letzte_aktivitaet'], zugriffszeitpunkt.timestamp())

    # Zugriff auf ein Konto mit einer falschen Rolle muss verweigert werden
    def test_qa04_falsche_rolle_verweigert_zugriff(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.ADMINISTRATOR

        # Den Testzeitpunkt festlegen
        testzeitpunkt = timezone.now()
        zugriffszeitpunkt = testzeitpunkt + timezone.timedelta(minutes=5)

        # HttpRequest-Objekt mit der Testsession vorbereiten
        anfrage = HttpRequest()
        anfrage.session = self.client.session

        # Die Anmeldung ausführen und die Authentifizierung prüfen
        konto, fehlerliste_anmeldung = lege_konto_an(benutzername, passwort, rolle)

        # Die Anmeldung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=testzeitpunkt):
            fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort)
        self.assertFalse(fehlerliste_anmeldung)

        # Die Zugriffsprüfung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=zugriffszeitpunkt):
            fehlerliste = pruefe_zugriff(anfrage, [Benutzerkonto.LEHRPERSON])

        self.assertTrue(fehlerliste)  # Eine nicht leere Fehlerliste erwarten
        self.assertTrue(get_user(anfrage).is_authenticated)

        anfrage.session.save()
        gespeicherte_sitzung = SessionStore(
            session_key=anfrage.session.session_key
        )

        self.assertEqual(gespeicherte_sitzung['sitzungsbeginn'], testzeitpunkt.timestamp())
        self.assertEqual(gespeicherte_sitzung['letzte_aktivitaet'], testzeitpunkt.timestamp())


    def test_qa03_fehlender_sitzungsbeginn_beendet_sitzung(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.ADMINISTRATOR

        # Den Testzeitpunkt festlegen
        testzeitpunkt = timezone.now()
        zugriffszeitpunkt = testzeitpunkt + timezone.timedelta(minutes=5)

        # HttpRequest-Objekt mit der Testsession vorbereiten
        anfrage = HttpRequest()
        anfrage.session = self.client.session

        # Die Anmeldung ausführen und die Authentifizierung prüfen
        konto, fehlerliste_anmeldung = lege_konto_an(benutzername, passwort, rolle)

        # Die Anmeldung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=testzeitpunkt):
            fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort)
        self.assertFalse(fehlerliste_anmeldung)

        del anfrage.session['sitzungsbeginn']  # Sitzungsbeginn entfernen, um die Prüfung zu erzwingen
        anfrage.session.save()  # Änderungen an der Sitzung speichern

        alte_sitzungskennung = anfrage.session.session_key
        self.assertTrue(anfrage.session.exists(alte_sitzungskennung))

        # Die Zugriffsprüfung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=zugriffszeitpunkt):
            fehlerliste = pruefe_zugriff(anfrage, [Benutzerkonto.ADMINISTRATOR])

        self.assertTrue(fehlerliste)  # Eine nicht leere Fehlerliste erwarten
        self.assertFalse(get_user(anfrage).is_authenticated)
        self.assertFalse(anfrage.session.exists(alte_sitzungskennung))  # Die Sitzung muss ungültig sein


    def test_qa03_fehlende_letzte_aktivitaet_beendet_sitzung(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.ADMINISTRATOR

        # Den Testzeitpunkt festlegen
        testzeitpunkt = timezone.now()
        zugriffszeitpunkt = testzeitpunkt + timezone.timedelta(minutes=5)

        # HttpRequest-Objekt mit der Testsession vorbereiten
        anfrage = HttpRequest()
        anfrage.session = self.client.session

        # Die Anmeldung ausführen und die Authentifizierung prüfen
        konto, fehlerliste_anmeldung = lege_konto_an(benutzername, passwort, rolle)

        # Die Anmeldung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=testzeitpunkt):
            fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort)
        self.assertFalse(fehlerliste_anmeldung)

        del anfrage.session['letzte_aktivitaet']  # Sitzungsbeginn entfernen, um die Prüfung zu erzwingen
        anfrage.session.save()  # Änderungen an der Sitzung speichern

        alte_sitzungskennung = anfrage.session.session_key
        self.assertTrue(anfrage.session.exists(alte_sitzungskennung))

        # Die Zugriffsprüfung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=zugriffszeitpunkt):
            fehlerliste = pruefe_zugriff(anfrage, [Benutzerkonto.ADMINISTRATOR])

        self.assertTrue(fehlerliste)  # Eine nicht leere Fehlerliste erwarten
        self.assertFalse(get_user(anfrage).is_authenticated)
        self.assertFalse(anfrage.session.exists(alte_sitzungskennung))  # Die Sitzung muss ungültig sein

    # Genau 30 Minuten Inaktivität muss die Sitzung beendet werden
    def test_qa03_genau_30_minuten_inaktivitaet_beendet_sitzung(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.ADMINISTRATOR

        # Den Testzeitpunkt festlegen
        testzeitpunkt = timezone.now()
        zugriffszeitpunkt = testzeitpunkt + timezone.timedelta(minutes=30)

        # HttpRequest-Objekt mit der Testsession vorbereiten
        anfrage = HttpRequest()
        anfrage.session = self.client.session

        # Die Anmeldung ausführen und die Authentifizierung prüfen
        konto, fehlerliste_anmeldung = lege_konto_an(benutzername, passwort, rolle)

        # Die Anmeldung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=testzeitpunkt):
            fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort)
        self.assertFalse(fehlerliste_anmeldung)

        anfrage.session.save()
        alte_sitzungskennung = anfrage.session.session_key
        self.assertTrue(anfrage.session.exists(alte_sitzungskennung))

        # Die Zugriffsprüfung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=zugriffszeitpunkt):
            fehlerliste = pruefe_zugriff(anfrage, [Benutzerkonto.ADMINISTRATOR])

        self.assertTrue(fehlerliste)  # Eine nicht leere Fehlerliste erwarten
        self.assertFalse(get_user(anfrage).is_authenticated)
        self.assertFalse(anfrage.session.exists(alte_sitzungskennung))  # Die Sitzung muss ungültig sein

    # Genau 29 Minuten und 59 Sekunden Inaktivität muss die Sitzung weiterhin gültig sein
    def test_qa03_genau_29_minuten_59_sekunden_inaktivitaet_erlaubt_zugriff(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.ADMINISTRATOR

        # Den Testzeitpunkt festlegen
        testzeitpunkt = timezone.now()
        zugriffszeitpunkt = testzeitpunkt + timezone.timedelta(minutes=29, seconds=59)

        # HttpRequest-Objekt mit der Testsession vorbereiten
        anfrage = HttpRequest()
        anfrage.session = self.client.session

        # Die Anmeldung ausführen und die Authentifizierung prüfen
        konto, fehlerliste_anmeldung = lege_konto_an(benutzername, passwort, rolle)

        # Die Anmeldung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=testzeitpunkt):
            fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort)
        self.assertFalse(fehlerliste_anmeldung)

        anfrage.session.save()
        alte_sitzungskennung = anfrage.session.session_key
        self.assertTrue(anfrage.session.exists(alte_sitzungskennung))

        # Die Zugriffsprüfung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=zugriffszeitpunkt):
            fehlerliste = pruefe_zugriff(anfrage, [Benutzerkonto.ADMINISTRATOR])

        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten
        self.assertTrue(get_user(anfrage).is_authenticated) # Die Sitzung muss weiterhin gültig sein
        self.assertTrue(anfrage.session.exists(alte_sitzungskennung)) # Die Sitzung muss weiterhin gültig sein

        # Die gespeicherte Sitzung prüfen, um sicherzustellen, dass die letzte Aktivität aktualisiert wurde
        anfrage.session.save()
        gespeicherte_sitzung = SessionStore(
            session_key=anfrage.session.session_key
        )

        self.assertEqual(gespeicherte_sitzung['sitzungsbeginn'], testzeitpunkt.timestamp())
        self.assertEqual(gespeicherte_sitzung['letzte_aktivitaet'], zugriffszeitpunkt.timestamp())

    # Genau 30 Minuten und 1 Sekunde Inaktivität muss die Sitzung beendet werden
    def test_qa03_genau_30_minuten_1_sekunde_inaktivitaet_beendet_sitzung(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.ADMINISTRATOR

        # Den Testzeitpunkt festlegen
        testzeitpunkt = timezone.now()
        zugriffszeitpunkt = testzeitpunkt + timezone.timedelta(minutes=30, seconds=1)

        # HttpRequest-Objekt mit der Testsession vorbereiten
        anfrage = HttpRequest()
        anfrage.session = self.client.session

        # Die Anmeldung ausführen und die Authentifizierung prüfen
        konto, fehlerliste_anmeldung = lege_konto_an(benutzername, passwort, rolle)

        # Die Anmeldung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=testzeitpunkt):
            fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort)
        self.assertFalse(fehlerliste_anmeldung)

        anfrage.session.save()
        alte_sitzungskennung = anfrage.session.session_key
        self.assertTrue(anfrage.session.exists(alte_sitzungskennung))

        # Die Zugriffsprüfung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=zugriffszeitpunkt):
            fehlerliste = pruefe_zugriff(anfrage, [Benutzerkonto.ADMINISTRATOR])

        self.assertTrue(fehlerliste)  # Eine nicht leere Fehlerliste erwarten
        self.assertFalse(get_user(anfrage).is_authenticated)
        self.assertFalse(anfrage.session.exists(alte_sitzungskennung))  # Die Sitzung muss ungültig sein

    # Genau 3 Stunden, 59 Minuten und 59 Sekunden Sitzungsdauer muss die Sitzung weiterhin gültig sein
    def test_qa03_genau_3_stunden_59_minuten_59_sekunden_sitzungsdauer_erlaubt_zugriff(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.ADMINISTRATOR

        # Den Anmeldezeitpunkt und den späteren Zugriffszeitpunkt festlegen
        testzeitpunkt = timezone.now()
        zugriffszeitpunkt = testzeitpunkt + timezone.timedelta(hours=3, minutes=59, seconds=59)

        # HttpRequest-Objekt mit der Testsession vorbereiten
        anfrage = HttpRequest()
        anfrage.session = self.client.session

        # Das Benutzerkonto anlegen
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)

        # Die Anmeldung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=testzeitpunkt):
            fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort)
        self.assertFalse(fehlerliste_anmeldung)

        # Eine letzte Aktivität fünf Minuten vor dem Zugriff simulieren
        aktivitaetszeitpunkt = zugriffszeitpunkt - timezone.timedelta(minutes=5)
        anfrage.session['letzte_aktivitaet'] = aktivitaetszeitpunkt.timestamp()

        # Die Sitzung speichern und ihre Existenz vor dem Zugriff prüfen
        anfrage.session.save()
        alte_sitzungskennung = anfrage.session.session_key
        self.assertTrue(anfrage.session.exists(alte_sitzungskennung))

        # Die Zugriffsprüfung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=zugriffszeitpunkt):
            fehlerliste = pruefe_zugriff(anfrage, [Benutzerkonto.ADMINISTRATOR])

        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten
        self.assertTrue(get_user(anfrage).is_authenticated)
        self.assertTrue(anfrage.session.exists(alte_sitzungskennung))

        # Den festen Sitzungsbeginn und die aktualisierte letzte Aktivität prüfen
        anfrage.session.save()
        gespeicherte_sitzung = SessionStore(session_key=anfrage.session.session_key)
        self.assertEqual(gespeicherte_sitzung['sitzungsbeginn'],testzeitpunkt.timestamp())
        self.assertEqual(gespeicherte_sitzung['letzte_aktivitaet'],zugriffszeitpunkt.timestamp())

    def test_qa03_genau_4_stunden_sitzungsdauer_beendet_sitzung(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.ADMINISTRATOR

        # Den Anmeldezeitpunkt und den späteren Zugriffszeitpunkt festlegen
        testzeitpunkt = timezone.now()
        zugriffszeitpunkt = testzeitpunkt + timezone.timedelta(hours=4)

        # HttpRequest-Objekt mit der Testsession vorbereiten
        anfrage = HttpRequest()
        anfrage.session = self.client.session

        # Das Benutzerkonto anlegen
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)

        # Die Anmeldung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=testzeitpunkt):
            fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort)
        self.assertFalse(fehlerliste_anmeldung)

        # Eine letzte Aktivität fünf Minuten vor dem Zugriff simulieren
        aktivitaetszeitpunkt = zugriffszeitpunkt - timezone.timedelta(minutes=5)
        anfrage.session['letzte_aktivitaet'] = aktivitaetszeitpunkt.timestamp()

        # Die Sitzung speichern und ihre Existenz vor dem Zugriff prüfen
        anfrage.session.save()
        alte_sitzungskennung = anfrage.session.session_key
        self.assertTrue(anfrage.session.exists(alte_sitzungskennung))

        # Die Zugriffsprüfung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=zugriffszeitpunkt):
            fehlerliste = pruefe_zugriff(anfrage, [Benutzerkonto.ADMINISTRATOR])

        self.assertTrue(fehlerliste)  # Eine nicht leere Fehlerliste erwarten
        self.assertFalse(get_user(anfrage).is_authenticated)
        self.assertFalse(anfrage.session.exists(alte_sitzungskennung))  # Die Sitzung muss ungültig sein

    def test_qa03_genau_4_stunden_1_sekunde_sitzungsdauer_beendet_sitzung(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.ADMINISTRATOR

        # Den Anmeldezeitpunkt und den späteren Zugriffszeitpunkt festlegen
        testzeitpunkt = timezone.now()
        zugriffszeitpunkt = testzeitpunkt + timezone.timedelta(hours=4, seconds=1)

        # HttpRequest-Objekt mit der Testsession vorbereiten
        anfrage = HttpRequest()
        anfrage.session = self.client.session

        # Das Benutzerkonto anlegen
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)

        # Die Anmeldung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=testzeitpunkt):
            fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort)
        self.assertFalse(fehlerliste_anmeldung)

        # Eine letzte Aktivität fünf Minuten vor dem Zugriff simulieren
        aktivitaetszeitpunkt = zugriffszeitpunkt - timezone.timedelta(minutes=5)
        anfrage.session['letzte_aktivitaet'] = aktivitaetszeitpunkt.timestamp()

        # Die Sitzung speichern und ihre Existenz vor dem Zugriff prüfen
        anfrage.session.save()
        alte_sitzungskennung = anfrage.session.session_key
        self.assertTrue(anfrage.session.exists(alte_sitzungskennung))

        # Die Zugriffsprüfung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=zugriffszeitpunkt):
            fehlerliste = pruefe_zugriff(anfrage, [Benutzerkonto.ADMINISTRATOR])

        self.assertTrue(fehlerliste)  # Eine nicht leere Fehlerliste erwarten
        self.assertFalse(get_user(anfrage).is_authenticated)
        self.assertFalse(anfrage.session.exists(alte_sitzungskennung))  # Die Sitzung muss ungültig sein


class AnmeldeViewTests(TestCase):
    # Eine GET-Anfrage an die Anmelde-View muss abgewiesen werden
    def test_fa01_get_anfrage_wird_abgewiesen(self):
        # Eine GET-Anfrage über die URL-Zuordnung an die View senden
        antwort = self.client.get('/anmelden/')

        # Prüfen, dass die verwendete HTTP-Methode abgewiesen wurde
        self.assertEqual(antwort.status_code, 405)

        # Prüfen, dass POST als erlaubte Methode angegeben wird
        self.assertEqual(antwort['Allow'], 'POST')

        # Prüfen, dass die JSON-Antwort keinen Anmeldungserfolg meldet
        self.assertFalse(antwort.json()['erfolg'])

    # Eine POST-Anfrage ohne Anmeldedaten muss abgewiesen werden
    def test_fa01_post_ohne_anmeldedaten_wird_abgewiesen(self):
        # Die Anmeldefunktion vorübergehend durch ein Testobjekt ersetzen
        # patch als Ersatz für die tatsächliche Anmeldefunktion verwenden, um zu verhindern, dass sie aufgerufen wird, da keine Anmeldedaten übermittelt werden
        with patch('vp_stunden.views.melde_an') as anmeldefunktion:
            # Eine POST-Anfrage ohne Formularfelder senden
            antwort = self.client.post('/anmelden/', data={})

        self.assertEqual(antwort.status_code, 400)  # Prüfen, dass die Anfrage abgewiesen wurde
        self.assertFalse(antwort.json()['erfolg'])  # Prüfen, dass die JSON-Antwort keinen Erfolg meldet
        anmeldefunktion.assert_not_called()  # Prüfen, dass die Anmeldefunktion nicht aufgerufen wurde

    # Eine erfolgreiche Anmeldung muss die Sitzung korrekt setzen
    def test_fa01_erfolgreiche_anmeldung(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten

        # Die gültigen Anmeldedaten als Formularfelder übermitteln
        antwort = self.client.post(
            '/anmelden/',
            data={
                'benutzername': benutzername,
                'passwort': passwort
            }
        )

        self.assertEqual(antwort.status_code, 200)  # Prüfen, dass die Anfrage erfolgreich war
        self.assertTrue(antwort.json()['erfolg'])  # Prüfen, dass die JSON-Antwort einen Erfolg meldet
        # SESSION_KEY bezeichnet den Schlüssel, unter dem Django die ID des angemeldeten Benutzers in der Sitzung speichert.
        self.assertEqual(self.client.session[SESSION_KEY], str(konto.pk))  # Prüfen, dass die Sitzung den angemeldeten Benutzer enthält

    # Ein falsches Passwort muss die Anmeldung verhindern und die Fehlversuche korrekt zählen
    def test_fa01_falsches_passwort_verhindert_anmeldung(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten

        # Ein falsches Passwort übermitteln
        antwort = self.client.post(
            '/anmelden/',
            data={
                'benutzername': benutzername,
                'passwort': 'falsches_passwort'
            }
        )

        self.assertEqual(antwort.status_code, 400)  # Prüfen, dass die Anfrage abgewiesen wurde
        self.assertFalse(antwort.json()['erfolg'])  # Prüfen, dass die JSON-Antwort keinen Erfolg meldet
        self.assertNotIn(SESSION_KEY, self.client.session)  # Prüfen, dass die Sitzung nicht den angemeldeten Benutzer enthält

        #prüfen, dass die Fehlversuche korrekt gezählt werden
        konto.refresh_from_db()  # Kontoobjekt aus der Datenbank aktualisieren
        self.assertEqual(konto.fehlversuche, 1)


class AbmeldeViewTests(TestCase):

    # Eine POST-Anfrage an die Abmelde-View muss die Sitzung beenden
    def test_qa03_abmeldung_beendet_gespeicherte_sitzung(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten

        # Die Anmeldung durchführen
        antwort = self.client.post(
            '/anmelden/',
            data={
                'benutzername': benutzername,
                'passwort': passwort
            }
        )

        # Die angemeldete Sitzung und ihre Kennung festhalten
        sitzung_vorher = self.client.session
        alte_sitzungskennung = sitzung_vorher.session_key

        # Kontozuordnung und gespeicherte Sitzung vor der Abmeldung prüfen
        self.assertTrue(sitzung_vorher.exists(alte_sitzungskennung))  # Prüfen, dass die Sitzung existiert
        self.assertEqual(sitzung_vorher[SESSION_KEY], str(konto.pk))  # Prüfen, dass die Sitzung den angemeldeten Benutzer enthält

        # Die Abmeldung durchführen
        antwort = self.client.post(
            '/abmelden/',
        )

        self.assertEqual(antwort.status_code, 200)  # Prüfen, dass die Anfrage erfolgreich war
        self.assertTrue(antwort.json()['erfolg'])  # Prüfen, dass die JSON-Antwort einen Erfolg meldet
        self.assertNotIn(SESSION_KEY, self.client.session)  # Prüfen, dass die Sitzung nicht den angemeldeten Benutzer enthält

        # Die vorherige Sitzung muss serverseitig gelöscht sein
        self.assertFalse(sitzung_vorher.exists(alte_sitzungskennung))

    # Eine GET-Anfrage an die Abmelde-View darf die Sitzung nicht beenden
    def test_qa03_get_anfrage_beendet_sitzung_nicht(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten

        # Die Anmeldung durchführen
        antwort = self.client.post(
            '/anmelden/',
            data={
                'benutzername': benutzername,
                'passwort': passwort
            }
        )
        # Die angemeldete Sitzung und ihre Kennung festhalten
        sitzung_vorher = self.client.session
        alte_sitzungskennung = sitzung_vorher.session_key

        # Kontozuordnung und gespeicherte Sitzung vor der Abmeldung prüfen
        self.assertTrue(sitzung_vorher.exists(alte_sitzungskennung))  # Prüfen, dass die Sitzung existiert
        self.assertEqual(sitzung_vorher[SESSION_KEY], str(konto.pk))  # Prüfen, dass die Sitzung den angemeldeten Benutzer enthält

        # Die Abmeldung über eine GET-Anfrage durchführen
        antwort = self.client.get(
            '/abmelden/',
        )

        # Die GET-Anfrage darf die Sitzung nicht beenden, da nur POST-Anfragen die Abmeldung auslösen
        self.assertEqual(antwort.status_code, 405)  # Prüfen, dass die verwendete HTTP-Methode abgewiesen wurde
        self.assertEqual(antwort['Allow'], 'POST')  # Prüfen, dass POST als erlaubte Methode angegeben wird
        self.assertFalse(antwort.json()['erfolg'])  # Prüfen, dass die JSON-Antwort keinen Erfolg meldet

        # Die Anmeldung und der bisherige Sitzungszustand müssen weiterhin gültig sein
        self.assertTrue(sitzung_vorher.exists(alte_sitzungskennung))  # Prüfen, dass die Sitzung weiterhin existiert
        self.assertEqual(self.client.session[SESSION_KEY], str(konto.pk))  # Prüfen, dass die Sitzung den angemeldeten Benutzer weiterhin enthält


class PasswortAenderungTests(TestCase):

    # Eine erfolgreiche Passwortänderung muss das neue Passwort korrekt setzen und die Sitzung beibehalten
    def test_fa03_erfolgreiche_eigene_passwortaenderung(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        altes_passwort = 'a' * 64
        neues_passwort = 'b' * 64
        rolle = Benutzerkonto.LEHRPERSON

        konto, fehlerliste = lege_konto_an(benutzername, altes_passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten

        anfrage = HttpRequest()
        anfrage.session = self.client.session  # Sitzungsobjekt für den direkten Funktionsaufruf bereitstellen

        # Die Anmeldung mit dem alten Passwort ausführen
        fehlerliste_anmeldung = melde_an(anfrage, benutzername, altes_passwort)
        self.assertFalse(fehlerliste_anmeldung)  # Eine leere Fehlerliste erwarten

        # Die Sitzung speichern und den Sitzungsbeginn festhalten
        anfrage.session.save()
        sitzungsbeginn_vorher = anfrage.session['sitzungsbeginn']

        # Die Passwortänderung durchführen
        aenderungszeitpunkt = timezone.now() + timezone.timedelta(minutes=5)
        with patch('vp_stunden.sicherheit.timezone.now', return_value=aenderungszeitpunkt):
            fehlerliste = aendere_passwort(anfrage, altes_passwort, neues_passwort)

        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten
        konto.refresh_from_db()  # Kontoobjekt aus der Datenbank aktualisieren
        self.assertTrue(konto.check_password(neues_passwort))  # Prüfen, dass das Passwort erfolgreich geändert wurde
        self.assertFalse(konto.check_password(altes_passwort))  # Prüfen, dass das alte Passwort nicht mehr gültig ist

        # Die aktuelle Sitzung speichern und erneut aus der Datenbank laden
        anfrage.session.save()
        anfrage.session = SessionStore(
            session_key=anfrage.session.session_key
        )

        # Anmeldung, Kontozuordnung und ursprünglichen Sitzungsbeginn prüfen
        angemeldetes_konto = get_user(anfrage)
        self.assertTrue(angemeldetes_konto.is_authenticated)
        self.assertEqual(angemeldetes_konto.pk, konto.pk)
        self.assertEqual(
            anfrage.session['sitzungsbeginn'], sitzungsbeginn_vorher
        )



    def test_fa03_falsches_bisheriges_passwort_verhindert_aenderung(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        altes_passwort = 'a' * 64
        neues_passwort = 'b' * 64
        rolle = Benutzerkonto.LEHRPERSON

        konto, fehlerliste = lege_konto_an(benutzername, altes_passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten

        anfrage = HttpRequest()
        anfrage.session = self.client.session  # Sitzungsobjekt für den direkten Funktionsaufruf bereitstellen

        # Die Anmeldung mit dem alten Passwort ausführen
        fehlerliste_anmeldung = melde_an(anfrage, benutzername, altes_passwort)
        self.assertFalse(fehlerliste_anmeldung)  # Eine leere Fehlerliste erwarten

        # Die Sitzung speichern und den Sitzungsbeginn festhalten
        anfrage.session.save()
        sitzungsbeginn_vorher = anfrage.session['sitzungsbeginn']

        # Den gespeicherten Passwort-Hash zum späteren Vergleich festhalten
        passwort_hash_vorher = konto.password

        # Die Passwortänderung mit einem falschen bisherigen Passwort durchführen
        aenderungszeitpunkt = timezone.now() + timezone.timedelta(minutes=5)
        with patch('vp_stunden.sicherheit.timezone.now', return_value=aenderungszeitpunkt):
            fehlerliste = aendere_passwort(anfrage, 'falsches_passwort', neues_passwort)

        # Die Passwortänderung muss abgewiesen werden
        self.assertTrue(fehlerliste)

        # Das Kontoobjekt aus der Datenbank aktualisieren
        konto.refresh_from_db()

        # Das alte Passwort muss weiterhin gültig sein
        self.assertEqual(konto.password, passwort_hash_vorher)
        self.assertTrue(konto.check_password(altes_passwort))

        # Das abgewiesene neue Passwort darf nicht gültig sein
        self.assertFalse(konto.check_password(neues_passwort))

        # Die aktuelle Sitzung speichern und erneut aus der Datenbank laden
        anfrage.session.save()
        anfrage.session = SessionStore(
            session_key=anfrage.session.session_key
        )

        # Anmeldung, Kontozuordnung und ursprünglichen Sitzungsbeginn prüfen
        angemeldetes_konto = get_user(anfrage)
        self.assertTrue(angemeldetes_konto.is_authenticated)
        self.assertEqual(angemeldetes_konto.pk, konto.pk)
        self.assertEqual(
            anfrage.session['sitzungsbeginn'], sitzungsbeginn_vorher
        )

    # Eine Passwortänderung mit einem zu kurzen neuen Passwort muss abgewiesen werden
    def test_qa01_zu_kurzes_neues_passwort_verhindert_aenderung(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        altes_passwort = 'a' * 64
        # Ein neues Passwort unterhalb der Mindestlänge vorbereiten
        neues_passwort = 'b' * 14
        rolle = Benutzerkonto.LEHRPERSON

        konto, fehlerliste = lege_konto_an(benutzername, altes_passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten

        anfrage = HttpRequest()
        anfrage.session = self.client.session  # Sitzungsobjekt für den direkten Funktionsaufruf bereitstellen

        # Die Anmeldung mit dem alten Passwort ausführen
        fehlerliste_anmeldung = melde_an(anfrage, benutzername, altes_passwort)
        self.assertFalse(fehlerliste_anmeldung)  # Eine leere Fehlerliste erwarten

        # Die Sitzung speichern und den Sitzungsbeginn festhalten
        anfrage.session.save()
        sitzungsbeginn_vorher = anfrage.session['sitzungsbeginn']

        # Den gespeicherten Passwort-Hash zum späteren Vergleich festhalten
        passwort_hash_vorher = konto.password

        # Die Passwortänderung mit einem zu kurzen neuen Passwort durchführen
        aenderungszeitpunkt = timezone.now() + timezone.timedelta(minutes=5)
        with patch('vp_stunden.sicherheit.timezone.now', return_value=aenderungszeitpunkt):
            fehlerliste = aendere_passwort(anfrage, altes_passwort, neues_passwort)

        # Die Passwortänderung muss abgewiesen werden
        self.assertTrue(fehlerliste)

        # Das Kontoobjekt aus der Datenbank aktualisieren
        konto.refresh_from_db()

        # Das alte Passwort muss weiterhin gültig sein
        self.assertEqual(konto.password, passwort_hash_vorher)
        self.assertTrue(konto.check_password(altes_passwort))

        # Das abgewiesene neue Passwort darf nicht gültig sein
        self.assertFalse(konto.check_password(neues_passwort))

        # Die aktuelle Sitzung speichern und erneut aus der Datenbank laden
        anfrage.session.save()
        anfrage.session = SessionStore(
            session_key=anfrage.session.session_key
        )

        # Anmeldung, Kontozuordnung und ursprünglichen Sitzungsbeginn prüfen
        angemeldetes_konto = get_user(anfrage)
        self.assertTrue(angemeldetes_konto.is_authenticated)
        self.assertEqual(angemeldetes_konto.pk, konto.pk)
        self.assertEqual(
            anfrage.session['sitzungsbeginn'], sitzungsbeginn_vorher
        )

    # Eine Passwortänderung ohne vorherige Anmeldung muss abgewiesen werden
    def test_fa03_ohne_anmeldung_wird_passwortaenderung_verweigert(self):
        # Gültige synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        altes_passwort = 'a' * 64
        neues_passwort = 'b' * 64
        rolle = Benutzerkonto.LEHRPERSON

        # Ein Konto mit dem bisherigen Passwort anlegen
        konto, fehlerliste = lege_konto_an(
            benutzername, altes_passwort, rolle
        )
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)

        # Den gespeicherten Passwort-Hash zum späteren Vergleich festhalten
        passwort_hash_vorher = konto.password

        # Eine Anfrage mit Sitzung, aber ohne Anmeldung vorbereiten
        anfrage = HttpRequest()
        anfrage.session = self.client.session
        self.assertFalse(get_user(anfrage).is_authenticated)

        # Die Passwortänderung ohne vorherige Anmeldung versuchen
        fehlerliste = aendere_passwort(
            anfrage, altes_passwort, neues_passwort
        )

        # Die Passwortänderung muss abgewiesen werden
        self.assertTrue(fehlerliste)

        # Den tatsächlich gespeicherten Kontozustand erneut laden
        konto.refresh_from_db()

        # Der Passwort-Hash muss unverändert bleiben
        self.assertEqual(konto.password, passwort_hash_vorher)

        # Das alte Passwort muss weiterhin gültig sein
        self.assertTrue(konto.check_password(altes_passwort))

        # Das abgewiesene neue Passwort darf nicht gültig sein
        self.assertFalse(konto.check_password(neues_passwort))

        # Die abgewiesene Änderung darf keine Anmeldung herstellen
        self.assertFalse(get_user(anfrage).is_authenticated)


class PasswortAenderungViewTests(TestCase):

    # Eine POST-Anfrage an die Passwortänderung-View muss die Passwortänderung korrekt durchführen
    def test_fa03_post_anfrage_aendert_passwort(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        altes_passwort = 'a' * 64
        neues_passwort = 'b' * 64
        rolle = Benutzerkonto.LEHRPERSON

        konto, fehlerliste = lege_konto_an(benutzername, altes_passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten

        # Die Anmeldung durchführen
        antwort = self.client.post(
            '/anmelden/',
            data={
                'benutzername': benutzername,
                'passwort': altes_passwort
            }
        )
        self.assertEqual(antwort.status_code, 200)
        self.assertTrue(antwort.json()['erfolg'])

        # Die Passwortänderung mit allen drei erforderlichen Formularfeldern anfragen
        antwort = self.client.post(
            '/passwort_aendern/',
            data={
                'bisheriges_passwort': altes_passwort,
                'neues_passwort': neues_passwort,
                'wiederholung_neues_passwort': neues_passwort
            }
        )

        self.assertEqual(antwort.status_code, 200)  # Prüfen, dass die Anfrage erfolgreich war
        self.assertTrue(antwort.json()['erfolg'])  # Prüfen, dass die JSON-Antwort einen Erfolg meldet

        # Das Kontoobjekt aus der Datenbank aktualisieren und das neue Passwort prüfen
        konto.refresh_from_db()
        self.assertTrue(konto.check_password(neues_passwort))  # Prüfen, dass das Passwort erfolgreich geändert wurde


    def test_fa03_abweichende_passwortwiederholung_verhindert_aenderung(self):
        # Gültige synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        altes_passwort = 'a' * 64
        neues_passwort = 'b' * 64
        rolle = Benutzerkonto.LEHRPERSON

        # Ein Konto mit dem bisherigen Passwort anlegen
        konto, fehlerliste = lege_konto_an(
            benutzername, altes_passwort, rolle
        )
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)

        # Die Anmeldung über die Anmelde-View durchführen
        antwort = self.client.post(
            '/anmelden/',
            data={
                'benutzername': benutzername,
                'passwort': altes_passwort
            }
        )
        self.assertEqual(antwort.status_code, 200)
        self.assertTrue(antwort.json()['erfolg'])

        # Den bisherigen Passwort-Hash zum späteren Vergleich sichern
        passwort_hash_vorher = konto.password

        # Die Passwortänderung mit einer abweichenden Wiederholung versuchen
        antwort = self.client.post(
            '/passwort_aendern/',
            data={
                'bisheriges_passwort': altes_passwort,
                'neues_passwort': neues_passwort,
                'wiederholung_neues_passwort': neues_passwort + 'x'
            }
        )

        # Die unterschiedlichen neuen Passwörter müssen abgewiesen werden
        self.assertEqual(antwort.status_code, 400)
        self.assertFalse(antwort.json()['erfolg'])

        # Den tatsächlich gespeicherten Kontozustand erneut laden
        konto.refresh_from_db()

        # Der gespeicherte Passwort-Hash muss unverändert bleiben
        self.assertEqual(konto.password, passwort_hash_vorher)

        # Das alte Passwort muss weiterhin gültig sein
        self.assertTrue(konto.check_password(altes_passwort))

        # Das abgewiesene neue Passwort darf nicht gültig sein
        self.assertFalse(konto.check_password(neues_passwort))

    # Eine POST-Anfrage an die Passwortänderung-View ohne vorherige Anmeldung muss abgewiesen werden
    def test_fa03_post_ohne_anmeldung_wird_abgewiesen(self):
        # Gültige synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        altes_passwort = 'a' * 64
        neues_passwort = 'b' * 64
        rolle = Benutzerkonto.LEHRPERSON

        # Ein Konto anlegen, ohne sich anschließend anzumelden
        konto, fehlerliste = lege_konto_an(
            benutzername, altes_passwort, rolle
        )
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)

        # Den bisherigen Passwort-Hash zum späteren Vergleich sichern
        passwort_hash_vorher = konto.password

        # Ohne Anmeldung eine vollständige Passwortänderungsanfrage senden
        antwort = self.client.post(
            '/passwort_aendern/',
            data={
                'bisheriges_passwort': altes_passwort,
                'neues_passwort': neues_passwort,
                'wiederholung_neues_passwort': neues_passwort
            }
        )

        # Den Zugriff wegen der fehlenden Anmeldung verweigern
        self.assertEqual(antwort.status_code, 403)
        self.assertFalse(antwort.json()['erfolg'])

        # Den tatsächlich gespeicherten Kontozustand erneut laden
        konto.refresh_from_db()

        # Der gespeicherte Passwort-Hash muss unverändert bleiben
        self.assertEqual(konto.password, passwort_hash_vorher)

        # Das alte Passwort muss weiterhin gültig sein
        self.assertTrue(konto.check_password(altes_passwort))

        # Das abgewiesene neue Passwort darf nicht gültig sein
        self.assertFalse(konto.check_password(neues_passwort))

    # Eine GET-Anfrage an die Passwortänderung-View muss abgewiesen werden
    def test_fa03_get_anfrage_wird_abgewiesen(self):
        # Eine GET-Anfrage über die URL-Zuordnung an die View senden
        antwort = self.client.get('/passwort_aendern/')

        # Die nicht erlaubte HTTP-Methode muss abgewiesen werden
        self.assertEqual(antwort.status_code, 405)

        # Der Allow-Header muss POST als erlaubte Methode nennen
        self.assertEqual(antwort['Allow'], 'POST')

        # Die JSON-Antwort darf keinen Erfolg melden
        self.assertFalse(antwort.json()['erfolg'])


class KontoErstellungViewTests(TestCase):

    def test_fa02_administrator_kann_konto_anlegen(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.LEHRPERSON

        # Ein Administrator-Konto anlegen und sich anmelden
        admin_konto, fehlerliste = lege_konto_an('admin', 'adminpasswort12', Benutzerkonto.ADMINISTRATOR)
        self.assertIsNotNone(admin_konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten

        # Die Anmeldung über die Anmelde-View durchführen
        antwort_anmeldung = self.client.post(
            '/anmelden/',
            data={
                'benutzername': 'admin',
                'passwort': 'adminpasswort12'
            }
        )

        # Prüfen, dass die Anmeldung erfolgreich war
        self.assertEqual(antwort_anmeldung.status_code, 200)
        self.assertTrue(antwort_anmeldung.json()['erfolg'])

        #Prüfen, dass der neue Benutzername noch nicht existiert
        self.assertFalse(Benutzerkonto.objects.filter(username=benutzername).exists())

        # Die Kontoerstellung mit allen erforderlichen Formularfeldern anfragen
        antwort = self.client.post(
            '/konto_anlegen/',
            data={
                'benutzername': benutzername,
                'passwort': passwort,
                'rolle': rolle
            }
        )

        # Prüfen, dass die Kontoerstellung erfolgreich war
        self.assertEqual(antwort.status_code, 200)
        self.assertTrue(antwort.json()['erfolg'])  # Prüfen, dass die JSON-Antwort einen Erfolg meldet

        # Das angelegte Konto erneut aus der Datenbank laden
        neues_konto = Benutzerkonto.objects.get(username=benutzername)

        # Die gespeicherten Kontodaten prüfen
        self.assertEqual(neues_konto.username, benutzername)
        self.assertEqual(neues_konto.rolle, rolle)
        self.assertTrue(neues_konto.check_password(passwort))


    def test_qa04_lehrperson_kann_kein_konto_anlegen(self):
        # Synthetische Testwerte vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.ADMINISTRATOR

        # Ein Lehrperson-Konto anlegen und sich anmelden
        lehrperson_konto, fehlerliste = lege_konto_an('lehrperson', 'lehrpersonpasswort12', Benutzerkonto.LEHRPERSON)
        self.assertIsNotNone(lehrperson_konto)
        self.assertFalse(fehlerliste)  # Eine leere Fehlerliste erwarten

        # Die Anmeldung über die Anmelde-View durchführen
        antwort_anmeldung = self.client.post(
            '/anmelden/',
            data={
                'benutzername': 'lehrperson',
                'passwort': 'lehrpersonpasswort12'
            }
        )

        # Prüfen, dass die Anmeldung erfolgreich war
        self.assertEqual(antwort_anmeldung.status_code, 200)
        self.assertTrue(antwort_anmeldung.json()['erfolg'])

        # Prüfen, dass der neue Benutzername noch nicht existiert
        self.assertFalse(Benutzerkonto.objects.filter(username=benutzername).exists())

        # Die aktuelle Anzahl der Benutzerkonten vor der Kontoerstellung festhalten
        kontozahl_vorher = Benutzerkonto.objects.count()

        # Die Kontoerstellung mit allen erforderlichen Formularfeldern anfragen
        antwort = self.client.post(
            '/konto_anlegen/',
            data={
                'benutzername': benutzername,
                'passwort': passwort,
                'rolle': rolle
            }
        )

        # Die Kontenanlage durch eine Lehrperson verweigern
        self.assertEqual(antwort.status_code, 403)
        self.assertFalse(antwort.json()['erfolg'])

        # Es darf kein neues Konto angelegt worden sein
        self.assertFalse(
            Benutzerkonto.objects.filter(username=benutzername).exists()
        )
        self.assertEqual(
            Benutzerkonto.objects.count(), kontozahl_vorher
        )


    def test_qa04_kontoanlage_ohne_anmeldung_wird_abgewiesen(self):
        # Gültige synthetische Daten für das angefragte Konto vorbereiten
        benutzername = 'testnutzer'
        passwort = 'a' * 64
        rolle = Benutzerkonto.ADMINISTRATOR

        # Prüfen, dass der angefragte Benutzername noch nicht existiert
        self.assertFalse(
            Benutzerkonto.objects.filter(username=benutzername).exists()
        )

        # Die aktuelle Kontenzahl zum späteren Vergleich festhalten
        kontozahl_vorher = Benutzerkonto.objects.count()

        # Ohne vorherige Anmeldung eine vollständige Kontenanlage anfragen
        antwort = self.client.post(
            '/konto_anlegen/',
            data={
                'benutzername': benutzername,
                'passwort': passwort,
                'rolle': rolle
            }
        )

        # Den Zugriff wegen der fehlenden Anmeldung verweigern
        self.assertEqual(antwort.status_code, 403)
        self.assertFalse(antwort.json()['erfolg'])

        # Der angefragte Benutzername darf weiterhin nicht existieren
        self.assertFalse(
            Benutzerkonto.objects.filter(username=benutzername).exists()
        )

        # Die Kontenzahl muss unverändert bleiben
        self.assertEqual(
            Benutzerkonto.objects.count(), kontozahl_vorher
        )

    def test_fa02_get_anfrage_wird_abgewiesen(self):
        # Eine GET-Anfrage über die URL-Zuordnung an die View senden
        antwort = self.client.get('/konto_anlegen/')

        # Die nicht erlaubte HTTP-Methode muss abgewiesen werden
        self.assertEqual(antwort.status_code, 405)

        # POST muss als erlaubte Methode angegeben werden
        self.assertEqual(antwort['Allow'], 'POST')

        # Die JSON-Antwort darf keinen Erfolg melden
        self.assertFalse(antwort.json()['erfolg'])


class PasswortZuruecksetzenViewTests(TestCase):

    def test_fa02_administrator_kann_passwort_zuruecksetzen(self):
        # Ein Administratorkonto vorbereiten
        admin_benutzername = 'testadmin'
        admin_passwort = 'a' * 64
        admin_konto, fehlerliste = lege_konto_an(
            admin_benutzername, admin_passwort, Benutzerkonto.ADMINISTRATOR
        )
        self.assertIsNotNone(admin_konto)
        self.assertFalse(fehlerliste)

        # Ein separates Lehrpersonenkonto als Ziel vorbereiten
        passwort = 'b' * 64
        neues_passwort = 'c' * 64
        konto, fehlerliste = lege_konto_an(
            'testnutzer', passwort, Benutzerkonto.LEHRPERSON
        )
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)

        # Mit dem Administratorkonto anmelden
        antwort_anmeldung = self.client.post(
            '/anmelden/',
            data={
                'benutzername': admin_benutzername,
                'passwort': admin_passwort
            }
        )
        self.assertEqual(antwort_anmeldung.status_code, 200)
        self.assertTrue(antwort_anmeldung.json()['erfolg'])

        # Das Passwort des Zielkontos über dessen tatsächliche ID zurücksetzen
        antwort = self.client.post(
            '/passwort_zuruecksetzen/',
            data={
                'konto_id': str(konto.pk),
                'neues_passwort': neues_passwort
            }
        )
        self.assertEqual(antwort.status_code, 200)
        self.assertTrue(antwort.json()['erfolg'])

        # Den gespeicherten Zustand des Zielkontos prüfen
        konto.refresh_from_db()
        self.assertTrue(konto.check_password(neues_passwort))
        self.assertFalse(konto.check_password(passwort))

    def test_qa04_lehrperson_kann_kein_passwort_zuruecksetzen(self):
        # Ein Lehrpersonenkonto für die Anmeldung vorbereiten
        benutzername = 'testlehrperson'
        passwort = 'a' * 64
        lehrperson_konto, fehlerliste = lege_konto_an(
            benutzername, passwort, Benutzerkonto.LEHRPERSON
        )
        self.assertIsNotNone(lehrperson_konto)
        self.assertFalse(fehlerliste)

        # Ein Administratorkonto als Ziel der unberechtigten Anfrage vorbereiten
        zielpasswort = 'b' * 64
        neues_passwort = 'c' * 64
        konto, fehlerliste = lege_konto_an(
            'testadmin', zielpasswort, Benutzerkonto.ADMINISTRATOR
        )
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)
        passwort_hash_vorher = konto.password

        # Mit dem Lehrpersonenkonto regulär anmelden
        antwort_anmeldung = self.client.post(
            '/anmelden/',
            data={
                'benutzername': benutzername,
                'passwort': passwort
            }
        )
        self.assertEqual(antwort_anmeldung.status_code, 200)
        self.assertTrue(antwort_anmeldung.json()['erfolg'])

        # Die Rücksetzung für das fremde Administratorkonto versuchen
        antwort = self.client.post(
            '/passwort_zuruecksetzen/',
            data={
                'konto_id': str(konto.pk),
                'neues_passwort': neues_passwort
            }
        )
        self.assertEqual(antwort.status_code, 403)
        self.assertFalse(antwort.json()['erfolg'])

        # Das Zielkonto muss unverändert bleiben
        konto.refresh_from_db()
        self.assertEqual(konto.password, passwort_hash_vorher)
        self.assertTrue(konto.check_password(zielpasswort))
        self.assertFalse(konto.check_password(neues_passwort))

    def test_qa04_ruecksetzung_ohne_anmeldung_wird_abgewiesen(self):
        # Ein Zielkonto vorbereiten, ohne sich anzumelden
        passwort = 'a' * 64
        neues_passwort = 'b' * 64
        konto, fehlerliste = lege_konto_an(
            'testnutzer', passwort, Benutzerkonto.LEHRPERSON
        )
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)
        passwort_hash_vorher = konto.password

        # Ohne Anmeldung eine vollständige Rücksetzungsanfrage senden
        antwort = self.client.post(
            '/passwort_zuruecksetzen/',
            data={
                'konto_id': str(konto.pk),
                'neues_passwort': neues_passwort
            }
        )
        self.assertEqual(antwort.status_code, 403)
        self.assertFalse(antwort.json()['erfolg'])

        # Die abgewiesene Anfrage darf das Passwort nicht verändern
        konto.refresh_from_db()
        self.assertEqual(konto.password, passwort_hash_vorher)
        self.assertTrue(konto.check_password(passwort))
        self.assertFalse(konto.check_password(neues_passwort))

    def test_fa02_get_anfrage_wird_abgewiesen(self):
        # Eine GET-Anfrage an die Rücksetzungs-View senden
        antwort = self.client.get('/passwort_zuruecksetzen/')

        # Die View darf ausschließlich POST zulassen
        self.assertEqual(antwort.status_code, 405)
        self.assertEqual(antwort['Allow'], 'POST')
        self.assertFalse(antwort.json()['erfolg'])

    def test_fa02_ungueltige_konto_id_wird_abgewiesen(self):
        # Ein Administratorkonto vorbereiten
        benutzername = 'testadmin'
        passwort = 'a' * 64
        admin_konto, fehlerliste = lege_konto_an(
            benutzername, passwort, Benutzerkonto.ADMINISTRATOR
        )
        self.assertIsNotNone(admin_konto)
        self.assertFalse(fehlerliste)

        # Mit dem Administratorkonto regulär anmelden
        antwort_anmeldung = self.client.post(
            '/anmelden/',
            data={
                'benutzername': benutzername,
                'passwort': passwort
            }
        )
        self.assertEqual(antwort_anmeldung.status_code, 200)
        self.assertTrue(antwort_anmeldung.json()['erfolg'])

        # Die Rücksetzfunktion durch ein Testobjekt ersetzen, das Aufrufe erfasst
        with patch('vp_stunden.views.setze_passwort_zurueck') as ruecksetzfunktion:
            # Eine Konto-ID senden, die keine Ganzzahl darstellt
            antwort = self.client.post(
                '/passwort_zuruecksetzen/',
                data={
                    'konto_id': 'keine_zahl',
                    'neues_passwort': 'b' * 64
                }
            )

        self.assertEqual(antwort.status_code, 400)
        self.assertFalse(antwort.json()['erfolg'])

        # Die ungültige ID muss bereits in der View abgefangen werden
        ruecksetzfunktion.assert_not_called()

    def test_qa01_zu_kurzes_passwort_verhindert_ruecksetzung(self):
        # Ein Administratorkonto vorbereiten
        admin_benutzername = 'testadmin'
        admin_passwort = 'a' * 64
        admin_konto, fehlerliste = lege_konto_an(
            admin_benutzername, admin_passwort, Benutzerkonto.ADMINISTRATOR
        )
        self.assertIsNotNone(admin_konto)
        self.assertFalse(fehlerliste)

        # Ein Zielkonto mit gültigem bisherigem Passwort vorbereiten
        passwort = 'b' * 64
        neues_passwort = 'c' * 14
        konto, fehlerliste = lege_konto_an(
            'testnutzer', passwort, Benutzerkonto.LEHRPERSON
        )
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)
        passwort_hash_vorher = konto.password

        # Mit dem Administratorkonto regulär anmelden
        antwort_anmeldung = self.client.post(
            '/anmelden/',
            data={
                'benutzername': admin_benutzername,
                'passwort': admin_passwort
            }
        )
        self.assertEqual(antwort_anmeldung.status_code, 200)
        self.assertTrue(antwort_anmeldung.json()['erfolg'])

        # Die Rücksetzung mit einem Passwort unterhalb der Mindestlänge versuchen
        antwort = self.client.post(
            '/passwort_zuruecksetzen/',
            data={
                'konto_id': str(konto.pk),
                'neues_passwort': neues_passwort
            }
        )
        self.assertEqual(antwort.status_code, 400)
        self.assertFalse(antwort.json()['erfolg'])

        # Der gespeicherte Hash und das bisherige Passwort müssen erhalten bleiben
        konto.refresh_from_db()
        self.assertEqual(konto.password, passwort_hash_vorher)
        self.assertTrue(konto.check_password(passwort))
        self.assertFalse(konto.check_password(neues_passwort))


class VPDatenmodellTests(TestCase):

    def test_fa08_vergleichswert_ist_eindeutig(self):
        # Zwei verschiedene Untersuchungen mit demselben Vergleichswert anlegen
        anzeigename1 = 'Teststudie A'
        vergleichswert1 = 'teststudie a'

        # Die erste Untersuchung erfolgreich anlegen
        studie1 = Untersuchung.objects.create(
            studienname=anzeigename1,
            studienname_vergleich=vergleichswert1,
            stundenwert=1.0,
            einordnung=Untersuchung.PRAESENZ,
            lehrperson='testdozentA'
        )

        anzeigename2 = 'TESTSTUDIE A '
        vergleichswert2 = 'teststudie a'  # Derselbe Vergleichswert wie bei studieA

        # Der Versuch, eine zweite Untersuchung mit demselben Vergleichswert anzulegen, muss eine Integritätsverletzung auslösen
        # Den fehlgeschlagenen Schreibversuch zuerst zum Sicherungspunkt zurückrollen
        # und danach den erwarteten Integritätsfehler abfangen, damit anschließende
        # Datenbankabfragen im Test möglich bleiben.
        with self.assertRaises(IntegrityError): # Die Integritätsverletzung wird erwartet, da der Vergleichswert eindeutig sein muss
            with transaction.atomic(): #
                Untersuchung.objects.create(
                    studienname=anzeigename2,
                    studienname_vergleich=vergleichswert2,
                    stundenwert=1.5,
                    einordnung=Untersuchung.PRAESENZ,
                    lehrperson='testdozentB',
                )

        # Prüfen, dass nur die erste Untersuchung erfolgreich in der Datenbank gespeichert wurde
        self.assertEqual(Untersuchung.objects.count(), 1)


    def test_fa12_teilnahmezuordnung_ist_eindeutig(self):
        # Erste Untersuchung anlegen
        studie1 = Untersuchung.objects.create(
            studienname='Studie 1',
            studienname_vergleich='studie 1',
            stundenwert=1.0,
            einordnung=Untersuchung.PRAESENZ,
            lehrperson='dozent1',
        )

        # Zweite Untersuchung anlegen
        studie2 = Untersuchung.objects.create(
            studienname='Studie 2',
            studienname_vergleich='studie 2',
            stundenwert=2.0,
            einordnung=Untersuchung.PRAESENZ,
            lehrperson='dozent2',
        )

        #Teilnahmezuordnungen anlegen
        teilnahme1 = Teilnahme.objects.create(
            untersuchung=studie1,
            matrikelnummer='1234567',
        )

        teilnahme2 = Teilnahme.objects.create(
            untersuchung=studie2,
            matrikelnummer='1234567',
        )

        teilnahme3 = Teilnahme.objects.create(
            untersuchung=studie1,
            matrikelnummer='7654321',
        )

        # Erste Zuordnung erneut anlegen, was eine Integritätsverletzung auslösen muss
        # Den fehlgeschlagenen Schreibversuch zuerst zum Sicherungspunkt zurückrollen
        # und danach den erwarteten Integritätsfehler abfangen, damit anschließende
        # Datenbankabfragen im Test möglich bleiben.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Teilnahme.objects.create(
                    untersuchung=studie1,
                    matrikelnummer='1234567',
                )

        # Prüfen, dass nur die drei eindeutigen Zuordnungen in der Datenbank gespeichert wurden
        self.assertEqual(Teilnahme.objects.count(), 3)

# SimpleTestCase wird verwendet, da keine Datenbankzugriffe in den EinordnungTests durchgeführt werden
class EinordnungTests(SimpleTestCase):

    def test_fa07_gueltige_einordnung_bleibt_unveraendert(self):
        # Der Aufruf mit 'P' muss 'P' zurückgeben
        self.assertEqual(pruefe_einordnung('P'), 'P')

        # Der Aufruf mit 'O' muss 'O' zurückgeben
        self.assertEqual(pruefe_einordnung('O'), 'O')

    def test_fa07_ungueltige_einordnung_wird_abgewiesen(self):
        for ungueltige_einordnung in ['p', 'o', ' P ', 'P ', '', 'X', None, 1, True]:
            with self.subTest(wert=ungueltige_einordnung):
                with self.assertRaises(ValidationError):
                    pruefe_einordnung(ungueltige_einordnung)


class MatrikelnummerTests(SimpleTestCase):

    def test_fa07_gueltige_matrikelnummer_wird_als_text_zurueckgegeben(self):
        # Der Aufruf mit einer gültigen Matrikelnummer muss die Matrikelnummer als Text zurückgeben
        self.assertEqual(pruefe_matrikelnummer(1000000), '1000000')
        self.assertEqual(pruefe_matrikelnummer(1234567), '1234567')
        self.assertEqual(pruefe_matrikelnummer(9999999), '9999999')

    def test_fa07_ungueltige_matrikelnummer_wird_abgewiesen(self):
        for ungueltige_matrikelnummer in [999_999, 10_000_000, 0, -1234567, '1234567', 1234567.0, 1234567.5, None, True, False]:
            with self.subTest(wert=ungueltige_matrikelnummer):
                with self.assertRaises(ValidationError):
                    pruefe_matrikelnummer(ungueltige_matrikelnummer)


class LehrpersonTests(SimpleTestCase):

    def test_fa07_gueltiger_lehrpersonenname_wird_bereinigt(self):
        # Äußere Leerzeichen entfernen.
        self.assertEqual(
            pruefe_lehrperson('  Dr. Müller  '),
            'Dr. Müller'
        )

        # Innere Leerzeichen unverändert erhalten.
        self.assertEqual(
            pruefe_lehrperson('Herr  Müller'),
            'Herr  Müller'
        )

        # Ein einzelnes Zeichen erfüllt die Mindestlänge.
        self.assertEqual(pruefe_lehrperson('A'), 'A')

        # Genau 100 Zeichen nach Entfernung äußerer Leerzeichen zulassen.
        self.assertEqual(
            pruefe_lehrperson('  ' + 'A' * 100 + '  '),
            'A' * 100
        )

    def test_fa07_ungueltiger_lehrpersonenname_wird_abgewiesen(self):
        # Leere Texte, überlange Namen und falsche Datentypen abweisen.
        for ungueltiger_name in ['', '   ', 'A' * 101, None, 123, True]:
            with self.subTest(wert=ungueltiger_name):
                with self.assertRaises(ValidationError):
                    pruefe_lehrperson(ungueltiger_name)


class StudiennameTests(SimpleTestCase):

    def test_fa07_gueltiger_studienname_liefert_anzeigename_und_vergleichswert(self):
        # Äußere Leerzeichen entfernen und beide Werte zurückgeben.
        self.assertEqual(
            pruefe_studienname('  Teststudie A  '),
            ('Teststudie A', 'teststudie a')
        )

        # Andere Großschreibung ergibt denselben Vergleichswert.
        # Die Schreibweise des Anzeigenamens bleibt erhalten.
        self.assertEqual(
            pruefe_studienname('TESTSTUDIE A'),
            ('TESTSTUDIE A', 'teststudie a')
        )

        # Innere Leerzeichen in beiden Werten erhalten.
        self.assertEqual(
            pruefe_studienname('Test  Studie'),
            ('Test  Studie', 'test  studie')
        )

        # Ein einzelnes Zeichen erfüllt die Mindestlänge.
        self.assertEqual(
            pruefe_studienname('A'),
            ('A', 'a')
        )

        # Genau 100 Zeichen nach der Bereinigung zulassen.
        # Der Vergleichswert darf durch casefold länger werden: ß wird zu ss.
        self.assertEqual(
            pruefe_studienname('  ' + 'ß' * 100 + '  '),
            ('ß' * 100, 'ss' * 100)
        )

    def test_fa07_ungueltiger_studienname_wird_abgewiesen(self):
        # Leere Texte, überlange Namen und falsche Datentypen abweisen.
        for ungueltiger_name in ['', '   ', 'A' * 101, None, 123, True]:
            with self.subTest(wert=ungueltiger_name):
                with self.assertRaises(ValidationError):
                    pruefe_studienname(ungueltiger_name)


class StundenwertTests(SimpleTestCase):

    def test_fa07_gueltiger_stundenwert_wird_als_float_zurueckgegeben(self):
        # Jeweils Eingabewert und erwarteten Rückgabewert festlegen.
        testfaelle = [
            (0.5, 0.5),
            (1, 1.0),
            (1.5, 1.5),
            (2.0, 2.0),
            (1000, 1000.0),
        ]

        for eingabe, erwartet in testfaelle:
            # subTest verwenden, um jeden Testfall separat zu prüfen und die Fehlermeldung zu isolieren.
            with self.subTest(wert=eingabe):
                ergebnis = pruefe_stundenwert(eingabe)

                # Den Zahlenwert und den Rückgabetyp prüfen.
                self.assertEqual(ergebnis, erwartet)
                self.assertIsInstance(ergebnis, float)

    def test_fa07_ungueltiger_stundenwert_wird_abgewiesen(self):
        # Null, negative Werte, falsche Schritte und Datentypen abweisen.
        for ungueltiger_wert in [
            0, -0.5, 0.25, 1.25, '1.5', '', None, True, False
        ]:
            # subTest verwenden, um jeden ungültigen Wert separat zu prüfen und die Fehlermeldung zu isolieren.
            with self.subTest(wert=ungueltiger_wert):
                with self.assertRaises(ValidationError):
                    pruefe_stundenwert(ungueltiger_wert)


class StundenberechnungTests(SimpleTestCase):

    def test_fa16_leere_liste_liefert_nullsummen(self):
        ergebnis = berechne_stunden([])

        self.assertEqual(ergebnis, {
            "praesenzstunden": 0.0,
            "onlinestunden": 0.0,
            "gesamtstunden": 0.0,
            "erfuellt": False,
        })

        # Auch bei leerer Liste müssen die Summen Fließkommazahlen sein.
        for feldname in ["praesenzstunden", "onlinestunden", "gesamtstunden"]:
            self.assertIsInstance(ergebnis[feldname], float)

    def test_fa16_stunden_werden_nach_einordnung_addiert(self):
        # Mehrere Teilnahmen je Einordnung prüfen das Aufsummieren.
        testfaelle = [
            (Untersuchung.PRAESENZ, 1.5),
            (Untersuchung.PRAESENZ, 2.5),
            (Untersuchung.ONLINE, 0.5),
            (Untersuchung.ONLINE, 1.0),
        ]

        teilnahmen = []

        for einordnung, stundenwert in testfaelle:
            # Die Modellobjekte bleiben ausschließlich im Arbeitsspeicher.
            untersuchung = Untersuchung(
                einordnung=einordnung,
                stundenwert=stundenwert,
            )
            teilnahmen.append(Teilnahme(untersuchung=untersuchung))

        ergebnis = berechne_stunden(teilnahmen)

        self.assertEqual(ergebnis, {
            "praesenzstunden": 4.0,
            "onlinestunden": 1.5,
            "gesamtstunden": 5.5,
            "erfuellt": False,
        })

    def test_fa16_erfuellungsgrenzen_werden_beachtet(self):
        # Präsenzstunden, Onlinestunden, erwartete Gesamtstunden und Status.
        testfaelle = [
            (15.0, 15.0, 30.0, True),    # Beide Mindestwerte genau erreicht.
            (15.0, 14.5, 29.5, False),   # Zu wenige Gesamtstunden.
            (14.5, 15.5, 30.0, False),   # Zu wenige Präsenzstunden.
            (30.0, 0.0, 30.0, True),     # Onlinestunden sind nicht erforderlich.
        ]

        for praesenzstunden, onlinestunden, gesamtstunden, erfuellt in testfaelle:
            # subTest verwenden, um jeden Testfall separat zu prüfen und die Fehlermeldung zu isolieren.
            with self.subTest(
                praesenzstunden=praesenzstunden,
                onlinestunden=onlinestunden,
            ):
                # Untersuchungen anlegen, die ausschließlich im Arbeitsspeicher existieren.
                praesenzuntersuchung = Untersuchung(
                    einordnung=Untersuchung.PRAESENZ,
                    stundenwert=praesenzstunden,
                )

                # Die Präsenz-Teilnahme wird der Liste hinzugefügt.
                teilnahmen = [
                    Teilnahme(untersuchung=praesenzuntersuchung),
                ]

                # Bei null Onlinestunden gibt es keine Online-Teilnahme.
                if onlinestunden > 0:
                    onlineuntersuchung = Untersuchung(
                        einordnung=Untersuchung.ONLINE,
                        stundenwert=onlinestunden,
                    )
                    # Die Online-Teilnahme wird der Liste hinzugefügt.
                    teilnahmen.append(
                        Teilnahme(untersuchung=onlineuntersuchung)
                    )

                # Die Stundenberechnung durchführen.
                ergebnis = berechne_stunden(teilnahmen)

                # Die erwarteten Summen und den Status prüfen.
                self.assertEqual(ergebnis, {
                    "praesenzstunden": praesenzstunden,
                    "onlinestunden": onlinestunden,
                    "gesamtstunden": gesamtstunden,
                    "erfuellt": erfuellt,
                })

                # Der Status muss tatsächlich True beziehungsweise False sein.
                self.assertIs(ergebnis["erfuellt"], erfuellt)


class TeilnahmesucheTests(TestCase):

    def setUp(self):
        # Untersuchungen bewusst entgegen der erwarteten Sortierung anlegen.
        untersuchung_beta = Untersuchung.objects.create(
            studienname="Beta",
            studienname_vergleich="beta",
            stundenwert=1.5,
            einordnung=Untersuchung.ONLINE,
            lehrperson="Testlehrperson Beta",
        )

        untersuchung_alpha = Untersuchung.objects.create(
            studienname="alpha",
            studienname_vergleich="alpha",
            stundenwert=2.5,
            einordnung=Untersuchung.PRAESENZ,
            lehrperson="Testlehrperson Alpha",
        )

        # Zwei Teilnahmen der gesuchten Matrikelnummer speichern.
        self.teilnahme_beta = Teilnahme.objects.create(
            untersuchung=untersuchung_beta,
            matrikelnummer="1234567",
        )

        self.teilnahme_alpha = Teilnahme.objects.create(
            untersuchung=untersuchung_alpha,
            matrikelnummer="1234567",
        )

        # Diese Teilnahme darf bei der Suche nicht erscheinen.
        Teilnahme.objects.create(
            untersuchung=untersuchung_beta,
            matrikelnummer="7654321",
        )

    def test_fa14_passende_teilnahmen_werden_sortiert_geladen(self):
        teilnahmen = suche_teilnahmen("1234567")

        # Eine Liste mit ausschließlich den passenden Teilnahmen erwarten.
        # Die Reihenfolge richtet sich nach dem Studiennamenvergleich.
        self.assertIsInstance(teilnahmen, list)
        self.assertEqual(
            teilnahmen,
            [self.teilnahme_alpha, self.teilnahme_beta],
        )

        # Die Untersuchungen müssen bereits vollständig mitgeladen sein.
        # Ihre Angaben erstmals innerhalb dieses Prüfblocks lesen.
        with self.assertNumQueries(0):
            self.assertEqual(
                teilnahmen[0].untersuchung.studienname,
                "alpha",
            )
            self.assertEqual(
                teilnahmen[0].untersuchung.lehrperson,
                "Testlehrperson Alpha",
            )
            self.assertEqual(
                teilnahmen[1].untersuchung.studienname,
                "Beta",
            )
            self.assertEqual(
                teilnahmen[1].untersuchung.lehrperson,
                "Testlehrperson Beta",
            )

            berechnung = berechne_stunden(teilnahmen)

        # Die Berechnung verwendet Stundenwerte und Einordnungen
        # der mitgeladenen Untersuchungen.
        self.assertEqual(berechnung, {
            "praesenzstunden": 2.5,
            "onlinestunden": 1.5,
            "gesamtstunden": 4.0,
            "erfuellt": False,
        })

    def test_fa14_fehlende_matrikelnummer_liefert_leere_liste(self):
        # Trotz vorhandener anderer Teilnahmen gibt es keinen Treffer.
        ergebnis = suche_teilnahmen("9999999")

        self.assertEqual(ergebnis, [])


# TestCase unterstützt Tests mit Datenbankzugriff und stellt Prüfmethoden
# wie assertEqual bereit. Der Testrunner verwendet eine eigene Testdatenbank.
# TestCase setzt die Datenbankänderungen nach jedem einzelnen Test zurück.
class UntersuchungskorrekturTests(TestCase):

    def setUp(self):
        # setUp wird automatisch vor jeder Testmethode aufgerufen.
        # Dadurch beginnen die Tests mit demselben vorbereiteten Bestand.
        #
        # self bezeichnet die aktuelle Testinstanz. Über self gespeicherte
        # Objekte sind auch in deren anderen Methoden verfügbar.
        #
        # objects.create erzeugt ein Modellobjekt, speichert es sofort
        # in der Testdatenbank und gibt das gespeicherte Objekt zurück.
        self.untersuchung = Untersuchung.objects.create(
            studienname="Ausgangsstudie",
            studienname_vergleich="ausgangsstudie",
            stundenwert=1.0,
            einordnung=Untersuchung.PRAESENZ,
            lehrperson="Alte Lehrperson",
        )

        # Eine zweite Untersuchung ermöglicht die Prüfung von Namenskonflikten.
        # Außerdem wird geprüft, dass die Korrektur keine zusätzlichen Untersuchungen anlegt.
        self.andere_untersuchung = Untersuchung.objects.create(
            studienname="Andere Studie",
            studienname_vergleich="andere studie",
            stundenwert=2.0,
            einordnung=Untersuchung.ONLINE,
            lehrperson="Andere Lehrperson",
        )

        # Zwei verschiedene Matrikelnummern derselben Untersuchung zuordnen.
        # Die Übergabe des Untersuchungsobjekts stellt die Fremdschlüsselverbindung zwischen Teilnahme und Untersuchung her.
        for matrikelnummer in ["1234567", "7654321"]:
            Teilnahme.objects.create(
                untersuchung=self.untersuchung,
                matrikelnummer=matrikelnummer,
            )

        # Den ursprünglichen Uploadzeitpunkt für einen späteren Vergleich merken.
        self.uploadzeitpunkt = self.untersuchung.uploadzeitpunkt

        # Den vollständigen Ausgangsbestand als Feldwerte festhalten:
        # - order_by("pk") sortiert aufsteigend nach dem Primärschlüssel.
        # - values() liefert je Datensatz ein Dictionary mit seinen Feldwerten.
        # - list() führt die Abfrage sofort aus und hält den jetzigen Stand fest.
        #
        # Dadurch werden spätere Datenbankwerte mit einem bereits bereits gelesenen Ausgangsstand verglichen.
        self.untersuchungsbestand = list(
            Untersuchung.objects.order_by("pk").values()
        )

        # Bei Teilnahmen enthalten die Feldwerte auch untersuchung_id.
        # Der Vergleich erfasst damit IDs, Matrikelnummern und Zuordnungen.
        self.teilnahmebestand = list(
            Teilnahme.objects.order_by("pk").values()
        )

    def test_fa15_gueltige_korrektur_wird_gespeichert(self):
        ergebnis, fehlerliste = korrigiere_untersuchung(
            untersuchung_id=self.untersuchung.pk,
            studienname="  Neue Studie ",
            stundenwert=2.5,
            einordnung=Untersuchung.ONLINE,
            lehrperson="  Neue Lehrperson  ",
        )

        # Die Korrektur muss erfolgreich sein und keine Fehler zurückgeben.
        self.assertEqual(fehlerliste, [])

        # Die Rückgabe muss ein Untersuchung-Objekt sein.
        self.assertIsInstance(ergebnis, Untersuchung)

        # Die Rückgabe muss dieselbe Untersuchung wie die Ausgangsuntersuchung sein.
        self.assertEqual(ergebnis.pk, self.untersuchung.pk)

        # Die Rückgabe muss die neuen Werte enthalten.
        self.assertEqual(ergebnis.studienname, "Neue Studie")

        # Die Korrekturfunktion hat eine eigene Instanz aus der Datenbank geladen.
        # Das Objekt aus setUp enthält deshalb zunächst noch die alten Werte.
        # refresh_from_db aktualisiert dieses Objekt mit den Datenbankwerten.
        # So wird geprüft , was tatsächlich gespeichert wurde.
        self.untersuchung.refresh_from_db()

        # Anzeigenamen und zugehörigen Vergleichswert prüfen.
        self.assertEqual(self.untersuchung.studienname, "Neue Studie")
        self.assertEqual(
            self.untersuchung.studienname_vergleich,
            "neue studie",
        )

        # Gespeicherten Stundenwert, Einordnung und bereinigten Lehrnamen prüfen.
        self.assertEqual(self.untersuchung.stundenwert, 2.5)
        self.assertEqual(self.untersuchung.einordnung, Untersuchung.ONLINE)
        self.assertEqual(self.untersuchung.lehrperson, "Neue Lehrperson")

        # Der erstmalige Uploadzeitpunkt muss bei einer Korrektur erhalten bleiben.
        self.assertEqual(
            self.untersuchung.uploadzeitpunkt,
            self.uploadzeitpunkt,
        )

        # Den aktuellen Teilnahmebestand mit dem Ausgangsbestand vergleichen.
        # Alle bisherigen Teilnahmen müssen weiterhin unverändert auf dieselbe Untersuchung verweisen.
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            self.teilnahmebestand,
        )

        # count() zählt die gespeicherten Untersuchungen.
        # Eine Korrektur darf keine zusätzliche Untersuchung anlegen.
        self.assertEqual(Untersuchung.objects.count(), 2)

        # Im Ausgangsbestand wurde die andere Untersuchung als zweite angelegt und besitzt die größere ID. Sie muss unverändert bleiben.
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values())[1],
            self.untersuchungsbestand[1],
        )

    def test_fa15_eigener_studienname_bleibt_erlaubt(self):
        # Der neue Anzeigename verwendet eine andere Großschreibung.
        # Sein Vergleichswert bleibt jedoch "ausgangsstudie".
        # Die bearbeitete Untersuchung muss beim Namensvergleich ausgeschlossen
        # werden, damit ihr eigener Name keinen Konflikt auslöst.
        ergebnis, fehlerliste = korrigiere_untersuchung(
            untersuchung_id=self.untersuchung.pk,
            studienname="  AUSGANGSSTUDIE  ",
            stundenwert=1.5,
            einordnung=Untersuchung.PRAESENZ,
            lehrperson="Neue Lehrperson",
        )

        # Erfolgreiche Rückgabe und unveränderte Identität prüfen.
        self.assertEqual(fehlerliste, [])
        self.assertIsInstance(ergebnis, Untersuchung)
        self.assertEqual(ergebnis.pk, self.untersuchung.pk)

        # Die gespeicherten Werte erneut in die Testinstanz laden.
        self.untersuchung.refresh_from_db()

        # Die neue Schreibweise muss gespeichert sein.
        # Der interne Vergleichswert bleibt trotz anderer Großschreibung gleich.
        self.assertEqual(self.untersuchung.studienname, "AUSGANGSSTUDIE")
        self.assertEqual(
            self.untersuchung.studienname_vergleich,
            "ausgangsstudie",
        )
        self.assertEqual(self.untersuchung.stundenwert, 1.5)

    def test_fa15_ungueltige_angaben_werden_gemeinsam_abgewiesen(self):
        # Alle vier bearbeitbaren Angaben sind gleichzeitig ungültig.
        ergebnis, fehlerliste = korrigiere_untersuchung(
            untersuchung_id=self.untersuchung.pk,
            studienname="",
            stundenwert=0,
            einordnung="X",
            lehrperson="   ",
        )

        # Die Korrektur muss fehlschlagen und Fehlermeldungen zurückgeben.
        self.assertIsNone(ergebnis)

        # Es müssen vier Fehlermeldungen zurückgegeben werden.
        self.assertEqual(len(fehlerliste), 4)

        # join() verbindet die Meldungen zu einem Text.
        # Das Leerzeichen vor .join dient als Trennzeichen zwischen den Meldungen.
        meldungen = " ".join(fehlerliste)

        for feldname in ["Studienname", "Stundenwert", "Einordnung", "Lehrperson"]:
            # subTest kennzeichnet jede Einzelprüfung mit dem aktuellen Feldnamen.
            # Nach einer fehlgeschlagenen Einzelprüfung können die übrigen
            # Feldnamen weiterhin geprüft werden.
            with self.subTest(feldname=feldname):
                self.assertIn(f"{feldname}:", meldungen)

        # Alle Untersuchungen und Teilnahmen müssen dem Ausgangsstand entsprechen.
        # Die Dictionaries enthalten auch IDs und den Uploadzeitpunkt.
        self.assertEqual(
            # list() führt die Abfrage sofort aus und hält den jetzigen Stand fest.
            list(Untersuchung.objects.order_by("pk").values()),
            self.untersuchungsbestand,
        )
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            self.teilnahmebestand,
        )

    def test_fa15_name_einer_anderen_untersuchung_wird_abgewiesen(self):
        # Der Name gehört bereits zur zweiten Untersuchung.
        # Großschreibung und äußere Leerzeichen müssen beim Vergleich
        # entsprechend der bestehenden Studiennamenprüfung behandelt werden.
        ergebnis, fehlerliste = korrigiere_untersuchung(
            untersuchung_id=self.untersuchung.pk,
            studienname="  ANDERE STUDIE  ",
            stundenwert=3.0,
            einordnung=Untersuchung.ONLINE,
            lehrperson="Neue Lehrperson",
        )

        self.assertIsNone(ergebnis)
        self.assertEqual(len(fehlerliste), 1)

        # Die Fehlermeldung muss den Konflikt mit dem Studiennamen deutlich machen.
        self.assertTrue(fehlerliste[0].startswith("Studienname:"))

        # Die Untersuchung darf nicht verändert werden.
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            self.untersuchungsbestand,
        )
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            self.teilnahmebestand,
        )

    def test_fa15_fehlende_untersuchung_wird_abgewiesen(self):
        # Eine mögliche freie ID bilden und ihre Abwesenheit ausdrücklich prüfen.
        fehlende_id = self.andere_untersuchung.pk + 1

        # Die gewählte ID darf nicht in der Datenbank existieren.
        self.assertFalse(
            Untersuchung.objects.filter(pk=fehlende_id).exists()
        )

        # Die Funktion muss eine Fehlermeldung zurückgeben, wenn die Untersuchung nicht existiert, trotz gültiger Eingaben. Die Meldung muss die fehlende Untersuchung eindeutig benennen.
        ergebnis, fehlerliste = korrigiere_untersuchung(
            untersuchung_id=fehlende_id,
            studienname="Neue Studie",
            stundenwert=2.5,
            einordnung=Untersuchung.ONLINE,
            lehrperson="Neue Lehrperson",
        )

        # Eine kontrollierte Fehlerrückgabe mit Bezug zur Untersuchung erwarten.
        self.assertIsNone(ergebnis)
        self.assertEqual(len(fehlerliste), 1)
        self.assertTrue(fehlerliste[0].startswith("Untersuchung:"))

        # Eine fehlende Untersuchung darf weder neue Daten anlegen noch vorhandene Untersuchungen oder Teilnahmen verändern.
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            self.untersuchungsbestand,
        )
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            self.teilnahmebestand,
        )

    def test_fa15_speicherfehler_wird_kontrolliert_behandelt(self):
        # Untersuchung.save wird innerhalb des with-Blocks vorübergehend ersetzt.
        # side_effect löst bei jedem Aufruf den angegebenen DatabaseError aus.
        # So lässt sich die Fehlerbehandlung prüfen, ohne die echte Speichermethode auszuführen.
        # Beim Verlassen des Blocks wird die ursprüngliche Methode wiederhergestellt.
        with patch.object(
            Untersuchung,
            "save",
            side_effect=DatabaseError("Synthetischer Speicherfehler"),
        ) as speichern:
            ergebnis, fehlerliste = korrigiere_untersuchung(
                untersuchung_id=self.untersuchung.pk,
                studienname="Neue Studie",
                stundenwert=2.5,
                einordnung=Untersuchung.ONLINE,
                lehrperson="Neue Lehrperson",
            )

        # Sicherstellen, dass die Funktion tatsächlich zu speichern versucht hat.
        speichern.assert_called_once()

        # Die Funktion muss den Fehler abfangen und kontrolliert zurückgeben.
        self.assertIsNone(ergebnis)
        self.assertEqual(fehlerliste, [
            "Untersuchung: Die Änderungen konnten nicht gespeichert werden."
        ])

        # Der gespeicherte Untersuchungs- und Teilnahmebestand bleibt erhalten.
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            self.untersuchungsbestand,
        )
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            self.teilnahmebestand,
        )


class TeilnahmedatenLoeschungTests(TestCase):

    def setUp(self):
        # Vor jeder Testmethode denselben synthetischen Bestand anlegen.
        self.matrikelnummer = "1234567"

        self.praesenzuntersuchung = Untersuchung.objects.create(
            studienname="Präsenzstudie",
            studienname_vergleich="präsenzstudie",
            stundenwert=15.0,
            einordnung=Untersuchung.PRAESENZ,
            lehrperson="Testlehrperson Präsenz",
        )

        self.onlineuntersuchung = Untersuchung.objects.create(
            studienname="Onlinestudie",
            studienname_vergleich="onlinestudie",
            stundenwert=15.0,
            einordnung=Untersuchung.ONLINE,
            lehrperson="Testlehrperson Online",
        )

        # Beide Teilnahmen zusammen erfüllen die Mindestvorgaben.
        for untersuchung in [
            self.praesenzuntersuchung,
            self.onlineuntersuchung,
        ]:
            Teilnahme.objects.create(
                untersuchung=untersuchung,
                matrikelnummer=self.matrikelnummer,
            )

        # Die vollständigen gespeicherten Feldwerte festhalten.
        # Damit können spätere unbeabsichtigte Änderungen erkannt werden.
        self.untersuchungsbestand = list(
            Untersuchung.objects.order_by("pk").values()
        )
        self.teilnahmebestand = list(
            Teilnahme.objects.order_by("pk").values()
        )

    def test_fa18_erfuellte_teilnahmen_werden_geloescht(self):
        fehlerliste = loesche_teilnahmedaten(
            matrikelnummer=self.matrikelnummer,
            ablage_bestaetigt=True,
        )

        self.assertEqual(fehlerliste, [])

        # Beide Teilnahmen und beide dadurch leeren Untersuchungen fehlen.
        self.assertEqual(Teilnahme.objects.count(), 0)
        self.assertEqual(Untersuchung.objects.count(), 0)

    def test_fa18_ohne_ablagebestaetigung_bleibt_bestand_erhalten(self):
        # Die Mindestvorgaben sind erfüllt.
        # Ausschließlich die Bestätigung der externen Reportablage fehlt.
        fehlerliste = loesche_teilnahmedaten(
            matrikelnummer=self.matrikelnummer,
            ablage_bestaetigt=False,
        )

        self.assertTrue(fehlerliste)

        # Sämtliche gespeicherten Angaben müssen unverändert bleiben.
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            self.untersuchungsbestand,
        )
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            self.teilnahmebestand,
        )

    def test_fa18_aktuell_zu_wenige_gesamtstunden_verhindern_loeschung(self):
        # Den zunächst erfüllten Bestand nachträglich verändern.
        # Danach liegen 29,5 Gesamtstunden und weiterhin 15 Präsenzstunden vor.
        self.onlineuntersuchung.stundenwert = 14.5
        self.onlineuntersuchung.save(update_fields=["stundenwert"])

        # Der bewusst veränderte Bestand ist der neue Vergleichsstand.
        untersuchungsbestand = list(
            Untersuchung.objects.order_by("pk").values()
        )

        fehlerliste = loesche_teilnahmedaten(
            matrikelnummer=self.matrikelnummer,
            ablage_bestaetigt=True,
        )

        # Die Löschung muss abgelehnt werden, da die Mindestvorgaben nicht erfüllt sind.
        self.assertTrue(fehlerliste)

        # Alle gespeicherten Angaben müssen unverändert bleiben.
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            untersuchungsbestand,
        )

        # Alle Teilnahmen müssen weiterhin unverändert vorhanden sein.
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            self.teilnahmebestand,
        )

    def test_fa18_aktuell_zu_wenige_praesenzstunden_verhindern_loeschung(self):
        # Die bisherige Präsenzuntersuchung nachträglich als online einordnen.
        # Die Gesamtstunden bleiben bei 30, die Präsenzstunden sinken auf 0.
        self.praesenzuntersuchung.einordnung = Untersuchung.ONLINE
        self.praesenzuntersuchung.save(update_fields=["einordnung"])

        untersuchungsbestand = list(
            Untersuchung.objects.order_by("pk").values()
        )

        fehlerliste = loesche_teilnahmedaten(
            matrikelnummer=self.matrikelnummer,
            ablage_bestaetigt=True,
        )

        # Die Löschung muss abgelehnt werden, da die Mindestvorgaben nicht erfüllt sind.
        self.assertTrue(fehlerliste)

        # Alle gespeicherten Angaben müssen unverändert bleiben.
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            untersuchungsbestand,
        )

        # Alle Teilnahmen müssen weiterhin unverändert vorhanden sein.
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            self.teilnahmebestand,
        )

    def test_fa18_fehlende_matrikelnummer_veraendert_keine_daten(self):
        fehlende_matrikelnummer = "9999999"

        # Die Abwesenheit der gewählten Matrikelnummer ausdrücklich prüfen.
        self.assertFalse(
            Teilnahme.objects.filter(
                matrikelnummer=fehlende_matrikelnummer,
            ).exists()
        )

        fehlerliste = loesche_teilnahmedaten(
            matrikelnummer=fehlende_matrikelnummer,
            ablage_bestaetigt=True,
        )

        # Die Löschung muss abgelehnt werden, da keine Teilnahmen gefunden wurden.
        self.assertTrue(fehlerliste)

        # Alle gespeicherten Angaben müssen unverändert bleiben.
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            self.untersuchungsbestand,
        )

        # Alle Teilnahmen müssen weiterhin unverändert vorhanden sein.
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            self.teilnahmebestand,
        )

    def test_fa18_untersuchung_mit_fremder_teilnahme_bleibt_erhalten(self):
        # Eine andere Matrikelnummer derselben Onlineuntersuchung zuordnen.
        fremde_teilnahme = Teilnahme.objects.create(
            untersuchung=self.onlineuntersuchung,
            matrikelnummer="7654321",
        )

        # Genau diese Untersuchung und diese Teilnahme müssen erhalten bleiben.
        verbleibender_untersuchungsbestand = list(
            Untersuchung.objects.filter(
                pk=self.onlineuntersuchung.pk,
            ).values()
        )
        verbleibender_teilnahmebestand = list(
            Teilnahme.objects.filter(
                pk=fremde_teilnahme.pk,
            ).values()
        )

        fehlerliste = loesche_teilnahmedaten(
            matrikelnummer=self.matrikelnummer,
            ablage_bestaetigt=True,
        )

        self.assertEqual(fehlerliste, [])

        # Der vollständige Restbestand muss den erwarteten Feldwerten entsprechen.
        # Damit fehlen zugleich beide Teilnahmen der gelöschten Matrikelnummer
        # und die dadurch leer gewordene Präsenzuntersuchung.
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            verbleibender_untersuchungsbestand,
        )
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            verbleibender_teilnahmebestand,
        )


    def test_fa18_datenbankfehler_setzt_teilnahmeloeschung_zurueck(self):
        # Der Untersuchungszugriff erfolgt im aktuellen Code erst,
        # nachdem die Teilnahmen gelöscht wurden.
        # An dieser Stelle einen synthetischen Datenbankfehler auslösen.
        with patch.object(
            Untersuchung.objects,
            "filter",
            side_effect=DatabaseError("Synthetischer Löschfehler"),
        ) as untersuchungsabfrage:
            fehlerliste = loesche_teilnahmedaten(
                matrikelnummer=self.matrikelnummer,
                ablage_bestaetigt=True,
            )

        # Der vorgesehene Fehlerpunkt muss tatsächlich erreicht worden sein.
        untersuchungsabfrage.assert_called_once()

        self.assertEqual(fehlerliste, [
            "Die Teilnahmedaten konnten nicht gelöscht werden."
        ])

        # Die bereits gelöschten Teilnahmen müssen zurückgesetzt worden sein.
        # Der vollständige Bestand entspricht wieder dem Ausgangszustand.
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            self.untersuchungsbestand,
        )
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            self.teilnahmebestand,
        )


class TeilnahmedatenLoeschungViewTests(TestCase):

    def setUp(self):
        # Vor jedem Test einen erfüllten synthetischen Datenbestand anlegen.
        self.matrikelnummer = "1234567"

        self.untersuchung = Untersuchung.objects.create(
            studienname="Teststudie Löschview",
            studienname_vergleich="teststudie löschview",
            stundenwert=30.0,
            einordnung=Untersuchung.PRAESENZ,
            lehrperson="Testlehrperson",
        )

        Teilnahme.objects.create(
            untersuchung=self.untersuchung,
            matrikelnummer=self.matrikelnummer,
        )

        # Die gespeicherten Feldwerte für spätere Vergleiche festhalten.
        self.untersuchungsbestand = list(
            Untersuchung.objects.order_by("pk").values()
        )
        self.teilnahmebestand = list(
            Teilnahme.objects.order_by("pk").values()
        )

    def melde_testkonto_an(self, rolle):
        # Ein synthetisches Konto mit der übergebenen Rolle anlegen.
        benutzername = "testkonto"
        passwort = "a" * 64

        konto, fehlerliste = lege_konto_an(
            benutzername,
            passwort,
            rolle,
        )
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)

        # Die reguläre Anmeldung richtet auch die Sitzungszeitwerte ein.
        antwort = self.client.post(
            "/anmelden/",
            data={
                "benutzername": benutzername,
                "passwort": passwort,
            },
        )
        self.assertEqual(antwort.status_code, 200)
        self.assertTrue(antwort.json()["erfolg"])

    def pruefe_unveraenderten_bestand(self):
        # Alle Untersuchungs- und Teilnahmeangaben müssen erhalten bleiben.
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            self.untersuchungsbestand,
        )
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            self.teilnahmebestand,
        )

    def test_fa18_administrator_kann_teilnahmedaten_loeschen(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)

        antwort = self.client.post(
            "/teilnahmedaten_loeschen/",
            data={
                "matrikelnummer": self.matrikelnummer,
                "ablage_bestaetigt": "true",
            },
        )

        self.assertEqual(antwort.status_code, 200)
        self.assertTrue(antwort.json()["erfolg"])

        # Die Teilnahme und die dadurch leere Untersuchung müssen fehlen.
        self.assertEqual(Teilnahme.objects.count(), 0)
        self.assertEqual(Untersuchung.objects.count(), 0)

    def test_qa04_lehrperson_kann_keine_teilnahmedaten_loeschen(self):
        self.melde_testkonto_an(Benutzerkonto.LEHRPERSON)

        # Alle Löschvoraussetzungen außer der berechtigten Rolle liegen vor.
        antwort = self.client.post(
            "/teilnahmedaten_loeschen/",
            data={
                "matrikelnummer": self.matrikelnummer,
                "ablage_bestaetigt": "true",
            },
        )

        self.assertEqual(antwort.status_code, 403)
        self.assertFalse(antwort.json()["erfolg"])
        self.pruefe_unveraenderten_bestand()

    def test_qa04_loeschung_ohne_anmeldung_wird_abgewiesen(self):
        # Der Testclient wurde in diesem Test nicht angemeldet.
        antwort = self.client.post(
            "/teilnahmedaten_loeschen/",
            data={
                "matrikelnummer": self.matrikelnummer,
                "ablage_bestaetigt": "true",
            },
        )

        self.assertEqual(antwort.status_code, 403)
        self.assertFalse(antwort.json()["erfolg"])
        self.pruefe_unveraenderten_bestand()

    def test_fa18_get_anfrage_wird_abgewiesen(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)

        antwort = self.client.get("/teilnahmedaten_loeschen/")

        self.assertEqual(antwort.status_code, 405)
        self.assertFalse(antwort.json()["erfolg"])

        # Der Antwortheader nennt ausschließlich POST als erlaubte Methode.
        self.assertEqual(antwort.headers["Allow"], "POST")
        self.pruefe_unveraenderten_bestand()

    def test_fa18_fehlende_matrikelnummer_wird_abgewiesen(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)

        # Die in der View verwendete Löschfunktion vorübergehend ersetzen,
        # um einen möglichen Aufruf zu erfassen.
        with patch(
            "vp_stunden.views.loesche_teilnahmedaten"
        ) as loeschfunktion:
            antwort = self.client.post(
                "/teilnahmedaten_loeschen/",
                data={
                    "ablage_bestaetigt": "true",
                },
            )

        self.assertEqual(antwort.status_code, 400)
        self.assertFalse(antwort.json()["erfolg"])

        # Die fehlende Angabe muss bereits in der View abgefangen werden.
        loeschfunktion.assert_not_called()
        self.pruefe_unveraenderten_bestand()

    def test_fa18_ohne_ablagebestaetigung_wird_loeschung_abgewiesen(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)

        # Sowohl ein fehlendes Feld als auch den Formulartext "false" prüfen.
        testfaelle = [
            {
                "matrikelnummer": self.matrikelnummer,
            },
            {
                "matrikelnummer": self.matrikelnummer,
                "ablage_bestaetigt": "false",
            },
        ]

        for daten in testfaelle:
            with self.subTest(daten=daten):
                antwort = self.client.post(
                    "/teilnahmedaten_loeschen/",
                    data=daten,
                )

                self.assertEqual(antwort.status_code, 400)
                self.assertFalse(antwort.json()["erfolg"])
                self.assertTrue(antwort.json()["fehlerliste"])
                self.pruefe_unveraenderten_bestand()

    def test_fa18_nicht_erfuellte_mindestvorgaben_verhindern_loeschung(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)

        # Den gespeicherten Stundenwert unter die Gesamtstundengrenze senken.
        self.untersuchung.stundenwert = 29.5
        self.untersuchung.save(update_fields=["stundenwert"])

        # Der bewusst veränderte Bestand ist der neue Vergleichsstand.
        self.untersuchungsbestand = list(
            Untersuchung.objects.order_by("pk").values()
        )

        antwort = self.client.post(
            "/teilnahmedaten_loeschen/",
            data={
                "matrikelnummer": self.matrikelnummer,
                "ablage_bestaetigt": "true",
            },
        )

        self.assertEqual(antwort.status_code, 400)
        self.assertFalse(antwort.json()["erfolg"])
        self.assertTrue(antwort.json()["fehlerliste"])
        self.pruefe_unveraenderten_bestand()


class TeilnahmesucheViewTests(TestCase):

    def setUp(self):
        self.matrikelnummer = "1234567"

        # Untersuchungen bewusst entgegen der erwarteten A–Z-Reihenfolge anlegen.
        self.untersuchung_beta = Untersuchung.objects.create(
            studienname="Beta-Studie",
            studienname_vergleich="beta-studie",
            stundenwert=15.0,
            einordnung=Untersuchung.PRAESENZ,
            lehrperson="Testlehrperson Beta",
        )

        self.untersuchung_alpha = Untersuchung.objects.create(
            studienname="Alpha-Studie",
            studienname_vergleich="alpha-studie",
            stundenwert=15.0,
            einordnung=Untersuchung.ONLINE,
            lehrperson="Testlehrperson Alpha",
        )

        # Einen bekannten Testzeitpunkt ohne Mikrosekunden verwenden.
        # Dadurch lässt sich der Zeitpunkt nach der JSON-Ausgabe einfach vergleichen.
        self.uploadzeitpunkt = timezone.now().replace(microsecond=0)
        Untersuchung.objects.update(
            uploadzeitpunkt=self.uploadzeitpunkt,
        )

        # Beide Untersuchungen der gesuchten Matrikelnummer zuordnen.
        for untersuchung in [
            self.untersuchung_beta,
            self.untersuchung_alpha,
        ]:
            Teilnahme.objects.create(
                untersuchung=untersuchung,
                matrikelnummer=self.matrikelnummer,
            )

        # Diese fremde Teilnahme darf nicht im Suchergebnis erscheinen.
        Teilnahme.objects.create(
            untersuchung=self.untersuchung_beta,
            matrikelnummer="7654321",
        )

        self.untersuchungsbestand = list(
            Untersuchung.objects.order_by("pk").values()
        )
        self.teilnahmebestand = list(
            Teilnahme.objects.order_by("pk").values()
        )

    def melde_testkonto_an(self, rolle):
        benutzername = "testkonto"
        passwort = "a" * 64

        konto, fehlerliste = lege_konto_an(
            benutzername,
            passwort,
            rolle,
        )
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)

        # Die reguläre Anmeldung richtet auch die Sitzungszeitwerte ein.
        antwort = self.client.post(
            "/anmelden/",
            data={
                "benutzername": benutzername,
                "passwort": passwort,
            },
        )

        self.assertEqual(antwort.status_code, 200)
        self.assertTrue(antwort.json()["erfolg"])

    def pruefe_unveraenderten_bestand(self):
        # Eine Suche darf die gespeicherten VP-Daten nicht verändern.
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            self.untersuchungsbestand,
        )
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            self.teilnahmebestand,
        )

    def test_fa14_administrator_erhaelt_sortierte_teilnahmen(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)

        antwort = self.client.post(
            "/teilnahmen_suchen/",
            data={
                "matrikelnummer": self.matrikelnummer,
            },
        )

        self.assertEqual(antwort.status_code, 200)
        ergebnis = antwort.json()
        self.assertTrue(ergebnis["erfolg"])

        # Genau die beiden Teilnahmen der gesuchten Matrikelnummer erwarten.
        self.assertEqual(len(ergebnis["teilnahmen"]), 2)

        erwartete_untersuchungen = [
            self.untersuchung_alpha,
            self.untersuchung_beta,
        ]

        # Jede Antwortzeile mit der Untersuchung an der erwarteten Position verbinden.
        # Damit werden zugleich Reihenfolge und Feldzuordnung geprüft.
        for zeile, untersuchung in zip(
            ergebnis["teilnahmen"],
            erwartete_untersuchungen,
        ):
            with self.subTest(studienname=untersuchung.studienname):
                self.assertEqual(
                    zeile["matrikelnummer"],
                    self.matrikelnummer,
                )
                self.assertEqual(
                    zeile["studienname"],
                    untersuchung.studienname,
                )
                self.assertEqual(
                    zeile["stundenwert"],
                    untersuchung.stundenwert,
                )
                self.assertEqual(
                    zeile["einordnung"],
                    untersuchung.einordnung,
                )
                self.assertEqual(
                    zeile["lehrperson"],
                    untersuchung.lehrperson,
                )

                # datetime.fromisoformat(...) wandelt den Uploadzeitpunkt aus der JSON-Antwort von einer Zeichenfolge in einen Zeitpunkt um.
                self.assertEqual(
                    datetime.fromisoformat(zeile["uploadzeitpunkt"]),
                    self.uploadzeitpunkt,
                )

        # Die fremde Teilnahme darf auch die Berechnung nicht beeinflussen.
        self.assertEqual(ergebnis["berechnung"], {
            "praesenzstunden": 15.0,
            "onlinestunden": 15.0,
            "gesamtstunden": 30.0,
            "erfuellt": True,
        })

        self.pruefe_unveraenderten_bestand()

    def test_fa16_nicht_erfuellter_status_wird_angezeigt(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)

        # Die Gesamtstunden auf 29,5 senken.
        self.untersuchung_alpha.stundenwert = 14.5
        self.untersuchung_alpha.save(update_fields=["stundenwert"])

        # Der bewusst veränderte Bestand ist der neue Vergleichsstand.
        self.untersuchungsbestand = list(
            Untersuchung.objects.order_by("pk").values()
        )

        antwort = self.client.post(
            "/teilnahmen_suchen/",
            data={
                "matrikelnummer": self.matrikelnummer,
            },
        )

        # Die Suche bleibt auch bei nicht erfüllten Mindestvorgaben erfolgreich.
        self.assertEqual(antwort.status_code, 200)
        ergebnis = antwort.json()
        self.assertTrue(ergebnis["erfolg"])
        self.assertEqual(len(ergebnis["teilnahmen"]), 2)

        self.assertEqual(ergebnis["berechnung"], {
            "praesenzstunden": 15.0,
            "onlinestunden": 14.5,
            "gesamtstunden": 29.5,
            "erfuellt": False,
        })

        self.pruefe_unveraenderten_bestand()

    def test_qa04_lehrperson_kann_keine_teilnahmen_suchen(self):
        self.melde_testkonto_an(Benutzerkonto.LEHRPERSON)

        antwort = self.client.post(
            "/teilnahmen_suchen/",
            data={
                "matrikelnummer": self.matrikelnummer,
            },
        )

        self.assertEqual(antwort.status_code, 403)
        ergebnis = antwort.json()
        self.assertFalse(ergebnis["erfolg"])

        # Bei verweigertem Zugriff dürfen keine Ergebnisdaten enthalten sein.
        self.assertNotIn("teilnahmen", ergebnis)
        self.assertNotIn("berechnung", ergebnis)
        self.pruefe_unveraenderten_bestand()

    def test_qa04_suche_ohne_anmeldung_wird_abgewiesen(self):
        antwort = self.client.post(
            "/teilnahmen_suchen/",
            data={
                "matrikelnummer": self.matrikelnummer,
            },
        )

        self.assertEqual(antwort.status_code, 403)
        ergebnis = antwort.json()
        self.assertFalse(ergebnis["erfolg"])
        self.assertNotIn("teilnahmen", ergebnis)
        self.assertNotIn("berechnung", ergebnis)
        self.pruefe_unveraenderten_bestand()

    def test_fa14_get_anfrage_wird_abgewiesen(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)

        antwort = self.client.get(
            "/teilnahmen_suchen/",
            data={
                "matrikelnummer": self.matrikelnummer,
            },
        )

        self.assertEqual(antwort.status_code, 405)
        self.assertFalse(antwort.json()["erfolg"])
        self.assertEqual(antwort.headers["Allow"], "POST")
        self.pruefe_unveraenderten_bestand()

    def test_fa14_fehlende_matrikelnummer_wird_abgewiesen(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)

        # Den in der View verwendeten Funktionsnamen vorübergehend ersetzen.
        with patch(
            "vp_stunden.views.suche_teilnahmen"
        ) as suchfunktion:
            antwort = self.client.post(
                "/teilnahmen_suchen/",
                data={},
            )

        self.assertEqual(antwort.status_code, 400)
        self.assertFalse(antwort.json()["erfolg"])

        # Die unvollständige Anfrage muss vor dem Suchaufruf abgewiesen werden.
        suchfunktion.assert_not_called()
        self.pruefe_unveraenderten_bestand()

    def test_fa14_fehlende_treffer_werden_gemeldet(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)
        fehlende_matrikelnummer = "9999999"

        self.assertFalse(
            Teilnahme.objects.filter(
                matrikelnummer=fehlende_matrikelnummer,
            ).exists()
        )

        antwort = self.client.post(
            "/teilnahmen_suchen/",
            data={
                "matrikelnummer": fehlende_matrikelnummer,
            },
        )

        self.assertEqual(antwort.status_code, 404)
        ergebnis = antwort.json()
        self.assertFalse(ergebnis["erfolg"])

        # Ohne Treffer werden weder Teilnahmeangaben noch Summen ausgegeben.
        self.assertNotIn("teilnahmen", ergebnis)
        self.assertNotIn("berechnung", ergebnis)
        self.pruefe_unveraenderten_bestand()


class UntersuchungssucheViewTests(TestCase):

    def setUp(self):
        # Untersuchungen entgegen der erwarteten A–Z-Reihenfolge anlegen.
        self.beta = Untersuchung.objects.create(
            studienname="Beta-Studie",
            studienname_vergleich="beta-studie",
            stundenwert=1.5,
            einordnung=Untersuchung.ONLINE,
            lehrperson="Testlehrperson Beta",
        )
        self.alpha = Untersuchung.objects.create(
            studienname="Alpha-Studie",
            studienname_vergleich="alpha-studie",
            stundenwert=2.5,
            einordnung=Untersuchung.PRAESENZ,
            lehrperson="Testlehrperson Alpha",
        )
        self.gamma = Untersuchung.objects.create(
            studienname="Gamma-Projekt",
            studienname_vergleich="gamma-projekt",
            stundenwert=1.0,
            einordnung=Untersuchung.PRAESENZ,
            lehrperson="Testlehrperson Gamma",
        )

    def melde_testkonto_an(self, rolle):
        testpasswort = "a" * 64
        konto, fehlerliste = lege_konto_an(
            "testkonto",
            testpasswort,
            rolle,
        )
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)

        # Die reguläre Anmeldung richtet die Sitzungsdaten ein.
        anmeldung = self.client.post(
            "/anmelden/",
            data={
                "benutzername": "testkonto",
                "passwort": testpasswort,
            },
        )
        self.assertEqual(anmeldung.status_code, 200)
        self.assertTrue(anmeldung.json()["erfolg"])

    def test_fa14_administrator_erhaelt_passende_sortierte_untersuchungen(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)

        # Teilnamensuche und ignorierte Groß-/Kleinschreibung prüfen.
        antwort = self.client.post(
            "/untersuchungen_suchen/",
            data={"suchtext": "sTuDiE"},
        )
        self.assertEqual(antwort.status_code, 200)

        ergebnis = antwort.json()
        self.assertTrue(ergebnis["erfolg"])
        self.assertEqual(len(ergebnis["untersuchungen"]), 2)

        # Genau Alpha und Beta in dieser Reihenfolge erwarten.
        for zeile, untersuchung in zip(
            ergebnis["untersuchungen"],
            [self.alpha, self.beta],
        ):
            self.assertEqual(zeile["untersuchung_id"], untersuchung.pk)
            self.assertEqual(zeile["studienname"], untersuchung.studienname)
            self.assertEqual(zeile["stundenwert"], untersuchung.stundenwert)
            self.assertEqual(zeile["einordnung"], untersuchung.einordnung)
            self.assertEqual(zeile["lehrperson"], untersuchung.lehrperson)

            # Den Antworttext für den Vergleich in einen Zeitpunkt umwandeln.
            self.assertEqual(
                datetime.fromisoformat(zeile["uploadzeitpunkt"]),
                untersuchung.uploadzeitpunkt,
            )

    def test_qa04_suche_ohne_anmeldung_wird_abgewiesen(self):
        antwort = self.client.post(
            "/untersuchungen_suchen/",
            data={"suchtext": "Studie"},
        )

        self.assertEqual(antwort.status_code, 403)
        ergebnis = antwort.json()
        self.assertFalse(ergebnis["erfolg"])
        self.assertNotIn("untersuchungen", ergebnis)

    def test_qa04_lehrperson_kann_keine_untersuchungen_suchen(self):
        self.melde_testkonto_an(Benutzerkonto.LEHRPERSON)

        antwort = self.client.post(
            "/untersuchungen_suchen/",
            data={"suchtext": "Studie"},
        )

        self.assertEqual(antwort.status_code, 403)
        ergebnis = antwort.json()
        self.assertFalse(ergebnis["erfolg"])
        self.assertNotIn("untersuchungen", ergebnis)

    def test_fa14_get_anfrage_wird_abgewiesen(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)

        antwort = self.client.get(
            "/untersuchungen_suchen/",
            data={"suchtext": "Studie"},
        )

        self.assertEqual(antwort.status_code, 405)
        self.assertEqual(antwort.headers["Allow"], "POST")
        self.assertFalse(antwort.json()["erfolg"])

    def test_fa14_fehlender_suchtext_wird_abgewiesen(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)

        # Prüfen, dass die unvollständige Anfrage vor der Suche abbricht.
        with patch(
            "vp_stunden.views.suche_untersuchungen"
        ) as suchfunktion:
            antwort = self.client.post(
                "/untersuchungen_suchen/",
                data={},
            )

        self.assertEqual(antwort.status_code, 400)
        ergebnis = antwort.json()
        self.assertFalse(ergebnis["erfolg"])
        self.assertNotIn("untersuchungen", ergebnis)
        suchfunktion.assert_not_called()

    def test_fa14_fehlende_treffer_werden_gemeldet(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)

        antwort = self.client.post(
            "/untersuchungen_suchen/",
            data={"suchtext": "Unbekannte Untersuchung"},
        )

        self.assertEqual(antwort.status_code, 404)
        ergebnis = antwort.json()
        self.assertFalse(ergebnis["erfolg"])
        self.assertNotIn("untersuchungen", ergebnis)

    def test_fa14_leerer_suchtext_liefert_alle_untersuchungen(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)

        # Ein ausdrücklich leerer Suchtext öffnet die Gesamtübersicht.
        antwort = self.client.post(
            "/untersuchungen_suchen/",
            data={"suchtext": ""},
        )
        self.assertEqual(antwort.status_code, 200)

        ergebnis = antwort.json()
        self.assertTrue(ergebnis["erfolg"])

        gefundene_ids = []
        for zeile in ergebnis["untersuchungen"]:
            gefundene_ids.append(zeile["untersuchung_id"])

        # Vollständigkeit und feste A–Z-Reihenfolge gemeinsam prüfen.
        self.assertEqual(
            gefundene_ids,
            [self.alpha.pk, self.beta.pk, self.gamma.pk],
        )


class UntersuchungskorrekturViewTests(TestCase):

    def setUp(self):
        # Vor jedem Test einen Ausgangsbestand an Untersuchungen anlegen.
        self.untersuchung = Untersuchung.objects.create(
            studienname="Ausgangsstudie",
            studienname_vergleich="ausgangsstudie",
            stundenwert=1.5,
            einordnung=Untersuchung.PRAESENZ,
            lehrperson="Alte Lehrperson",
        )

        # Die ID und den Upload-Zeitpunkt der Untersuchung speichern.
        self.untersuchung_id = self.untersuchung.pk
        self.uploadzeitpunkt = self.untersuchung.uploadzeitpunkt

        # Alle Angaben senden, ausschließlich den Stundenwert ändern.
        self.daten = {
            "untersuchung_id": str(self.untersuchung_id),
            "studienname": "Ausgangsstudie",
            "stundenwert": "2.5",
            "einordnung": Untersuchung.PRAESENZ,
            "lehrperson": "Alte Lehrperson",
        }

        # Den gespeicherten Ausgangsbestand für Fehlerfälle festhalten.
        self.untersuchungsbestand = list(
            Untersuchung.objects.order_by("pk").values()
        )

    def melde_testkonto_an(self, rolle):
        testpasswort = "a" * 64
        konto, fehlerliste = lege_konto_an(
            "testkonto",
            testpasswort,
            rolle,
        )
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)

        anmeldung = self.client.post(
            "/anmelden/",
            data={
                "benutzername": "testkonto",
                "passwort": testpasswort,
            },
        )
        self.assertEqual(anmeldung.status_code, 200)
        self.assertTrue(anmeldung.json()["erfolg"])

    def pruefe_unveraenderten_bestand(self):
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            self.untersuchungsbestand,
        )

    def test_fa15_einzelner_stundenwert_wird_korrigiert(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)

        # Die Korrektur muss erfolgreich sein, da alle Angaben vollständig und korrekt sind.
        antwort = self.client.post(
            "/untersuchung_korrigieren/",
            data=self.daten,
        )
        self.assertEqual(antwort.status_code, 200)

        ergebnis = antwort.json()
        self.assertTrue(ergebnis["erfolg"])
        zeile = ergebnis["untersuchung"]

        # Die Antwort enthält den neuen Stundenwert und die übrigen Angaben.
        self.assertEqual(zeile["untersuchung_id"], self.untersuchung_id)
        self.assertEqual(zeile["studienname"], "Ausgangsstudie")
        self.assertEqual(zeile["stundenwert"], 2.5)
        self.assertEqual(zeile["einordnung"], Untersuchung.PRAESENZ)
        self.assertEqual(zeile["lehrperson"], "Alte Lehrperson")
        self.assertEqual(
            datetime.fromisoformat(zeile["uploadzeitpunkt"]),
            self.uploadzeitpunkt,
        )

        # Den tatsächlichen Datenbankstand prüfen.
        self.untersuchung.refresh_from_db()
        self.assertEqual(self.untersuchung.pk, self.untersuchung_id)
        self.assertEqual(self.untersuchung.studienname, "Ausgangsstudie")
        self.assertEqual(
            self.untersuchung.studienname_vergleich,
            "ausgangsstudie",
        )
        self.assertEqual(self.untersuchung.stundenwert, 2.5)
        self.assertEqual(
            self.untersuchung.einordnung,
            Untersuchung.PRAESENZ,
        )
        self.assertEqual(self.untersuchung.lehrperson, "Alte Lehrperson")
        self.assertEqual(
            self.untersuchung.uploadzeitpunkt,
            self.uploadzeitpunkt,
        )

    def test_qa04_korrektur_ohne_anmeldung_wird_abgewiesen(self):
        antwort = self.client.post(
            "/untersuchung_korrigieren/",
            data=self.daten,
        )

        self.assertEqual(antwort.status_code, 403)
        ergebnis = antwort.json()
        self.assertFalse(ergebnis["erfolg"])
        self.assertNotIn("untersuchung", ergebnis)
        self.pruefe_unveraenderten_bestand()

    def test_qa04_lehrperson_kann_keine_untersuchung_korrigieren(self):
        self.melde_testkonto_an(Benutzerkonto.LEHRPERSON)

        antwort = self.client.post(
            "/untersuchung_korrigieren/",
            data=self.daten,
        )

        self.assertEqual(antwort.status_code, 403)
        ergebnis = antwort.json()
        self.assertFalse(ergebnis["erfolg"])
        self.assertNotIn("untersuchung", ergebnis)
        self.pruefe_unveraenderten_bestand()

    def test_fa15_get_anfrage_wird_abgewiesen(self):
        antwort = self.client.get(
            "/untersuchung_korrigieren/",
            data=self.daten,
        )

        self.assertEqual(antwort.status_code, 405)
        self.assertEqual(antwort.headers["Allow"], "POST")
        self.assertFalse(antwort.json()["erfolg"])
        self.pruefe_unveraenderten_bestand()

    def test_fa15_fehlende_parameter_werden_abgewiesen(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)

        for schluessel, feldname in [
            ("untersuchung_id", "Untersuchung"),
            ("studienname", "Studienname"),
            ("stundenwert", "Stundenwert"),
            ("einordnung", "Einordnung"),
            ("lehrperson", "Lehrperson"),
        ]:
            with self.subTest(parameter=schluessel):
                daten = self.daten.copy()
                daten.pop(schluessel)

                # Die Verarbeitung darf bei fehlenden Angaben nicht beginnen.
                with patch(
                    "vp_stunden.views.korrigiere_untersuchung"
                ) as korrekturfunktion:
                    antwort = self.client.post(
                        "/untersuchung_korrigieren/",
                        data=daten,
                    )

                self.assertEqual(antwort.status_code, 400)
                ergebnis = antwort.json()
                self.assertFalse(ergebnis["erfolg"])
                self.assertTrue(ergebnis["fehlerliste"])
                self.assertIn(
                    feldname,
                    " ".join(ergebnis["fehlerliste"]),
                )
                korrekturfunktion.assert_not_called()
                self.pruefe_unveraenderten_bestand()

    def test_fa15_ungueltige_zahlen_werden_abgewiesen(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)

        for schluessel, feldname in [
            ("untersuchung_id", "Untersuchung"),
            ("stundenwert", "Stundenwert"),
        ]:
            with self.subTest(parameter=schluessel):
                daten = self.daten.copy()
                daten[schluessel] = "keine Zahl"

                with patch(
                    "vp_stunden.views.korrigiere_untersuchung"
                ) as korrekturfunktion:
                    antwort = self.client.post(
                        "/untersuchung_korrigieren/",
                        data=daten,
                    )

                self.assertEqual(antwort.status_code, 400)
                ergebnis = antwort.json()
                self.assertFalse(ergebnis["erfolg"])
                self.assertTrue(ergebnis["fehlerliste"])
                self.assertIn(
                    feldname,
                    " ".join(ergebnis["fehlerliste"]),
                )
                korrekturfunktion.assert_not_called()
                self.pruefe_unveraenderten_bestand()

    def test_fa15_inhaltliche_fehler_werden_zurueckgegeben(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)

        # Diese Angaben erreichen die vorhandenen Feldprüfungen.
        for schluessel, wert, feldname in [
            ("studienname", "", "Studienname"),
            ("stundenwert", "1.25", "Stundenwert"),
        ]:
            with self.subTest(parameter=schluessel):
                daten = self.daten.copy()
                daten[schluessel] = wert

                antwort = self.client.post(
                    "/untersuchung_korrigieren/",
                    data=daten,
                )

                self.assertEqual(antwort.status_code, 400)
                ergebnis = antwort.json()
                self.assertFalse(ergebnis["erfolg"])
                self.assertTrue(ergebnis["fehlerliste"])
                self.assertIn(
                    feldname,
                    " ".join(ergebnis["fehlerliste"]),
                )
                self.assertNotIn("untersuchung", ergebnis)
                self.pruefe_unveraenderten_bestand()


class ReporterzeugungViewTests(TestCase):

    def setUp(self):
        self.matrikelnummer = "1234567"
        self.daten = {"matrikelnummer": self.matrikelnummer}

        # Untersuchungen zuerst in alphabetischer Reihenfolge anlegen.
        self.untersuchung_alpha = Untersuchung.objects.create(
            studienname="Alpha-Studie",
            studienname_vergleich="alpha-studie",
            stundenwert=15.0,
            einordnung=Untersuchung.ONLINE,
            lehrperson="Testlehrperson Alpha",
        )
        self.untersuchung_beta = Untersuchung.objects.create(
            studienname="Beta-Studie",
            studienname_vergleich="beta-studie",
            stundenwert=15.0,
            einordnung=Untersuchung.PRAESENZ,
            lehrperson="Testlehrperson Beta",
        )

        # Die Teilnahmezuordnungen in der erwarteten Reportreihenfolge anlegen.
        self.teilnahme_beta = Teilnahme.objects.create(
            untersuchung=self.untersuchung_beta,
            matrikelnummer=self.matrikelnummer,
        )
        self.teilnahme_alpha = Teilnahme.objects.create(
            untersuchung=self.untersuchung_alpha,
            matrikelnummer=self.matrikelnummer,
        )

        # Diese fremde Teilnahme darf im Report nicht berücksichtigt werden.
        Teilnahme.objects.create(
            untersuchung=self.untersuchung_alpha,
            matrikelnummer="7654321",
        )

        self.untersuchungsbestand = list(
            Untersuchung.objects.order_by("pk").values()
        )
        self.teilnahmebestand = list(
            Teilnahme.objects.order_by("pk").values()
        )

    def melde_testkonto_an(self, rolle):
        testpasswort = "a" * 64
        konto, fehlerliste = lege_konto_an(
            "testkonto",
            testpasswort,
            rolle,
        )
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)

        # Die reguläre Anmeldung richtet die erforderlichen Sitzungsdaten ein.
        anmeldung = self.client.post(
            "/anmelden/",
            data={
                "benutzername": "testkonto",
                "passwort": testpasswort,
            },
        )
        self.assertEqual(anmeldung.status_code, 200)
        self.assertTrue(anmeldung.json()["erfolg"])

    def pruefe_unveraenderten_bestand(self):
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            self.untersuchungsbestand,
        )
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            self.teilnahmebestand,
        )

    def pruefe_abweisung(self, daten, status):
        # Bei einer abgewiesenen Anfrage darf keine PDF-Erzeugung stattfinden.
        with patch(
            "vp_stunden.views.erzeuge_report"
        ) as reportfunktion:
            antwort = self.client.post(
                "/report_erzeugen/",
                data=daten,
            )

        self.assertEqual(antwort.status_code, status)
        self.assertFalse(antwort.json()["erfolg"])
        reportfunktion.assert_not_called()
        self.pruefe_unveraenderten_bestand()

    def test_fa17_administrator_erhaelt_pdf_in_importreihenfolge(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)

        # wraps führt die echte Funktion aus und hält ihre Aufrufargumente fest.
        with patch(
            "vp_stunden.views.erzeuge_report",
            wraps=erzeuge_report,
        ) as reportfunktion:
            antwort = self.client.post(
                "/report_erzeugen/",
                data=self.daten,
            )

        self.assertEqual(antwort.status_code, 200)
        self.assertEqual(
            antwort.headers["Content-Type"],
            "application/pdf",
        )
        self.assertEqual(
            antwort.headers["Content-Disposition"],
            'attachment; filename="vp_stunden_1234567.pdf"',
        )

        # Anfangs- und Endmarkierung der erzeugten PDF-Daten prüfen.
        self.assertTrue(antwort.content.startswith(b"%PDF-"))
        self.assertTrue(antwort.content.rstrip().endswith(b"%%EOF"))

        reportfunktion.assert_called_once()
        matrikelnummer, teilnahmen, berechnung = (
            reportfunktion.call_args.args
        )

        self.assertEqual(matrikelnummer, self.matrikelnummer)

        # Genau die passenden Teilnahmen in ihrer Anlagereihenfolge erwarten.
        teilnahme_ids = [teilnahme.pk for teilnahme in teilnahmen]
        self.assertEqual(
            teilnahme_ids,
            [self.teilnahme_beta.pk, self.teilnahme_alpha.pk],
        )

        self.assertEqual(
            berechnung,
            {
                "praesenzstunden": 15.0,
                "onlinestunden": 15.0,
                "gesamtstunden": 30.0,
                "erfuellt": True,
            },
        )
        self.pruefe_unveraenderten_bestand()

    def test_qa04_report_ohne_anmeldung_wird_abgewiesen(self):
        self.pruefe_abweisung(self.daten, 403)

    def test_qa04_lehrperson_kann_keinen_report_erzeugen(self):
        self.melde_testkonto_an(Benutzerkonto.LEHRPERSON)
        self.pruefe_abweisung(self.daten, 403)

    def test_fa17_get_anfrage_wird_abgewiesen(self):
        with patch(
            "vp_stunden.views.erzeuge_report"
        ) as reportfunktion:
            antwort = self.client.get(
                "/report_erzeugen/",
                data=self.daten,
            )

        self.assertEqual(antwort.status_code, 405)
        self.assertEqual(antwort.headers["Allow"], "POST")
        self.assertFalse(antwort.json()["erfolg"])
        reportfunktion.assert_not_called()
        self.pruefe_unveraenderten_bestand()

    def test_fa17_fehlende_matrikelnummer_wird_abgewiesen(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)

        # Einen fehlenden Schlüssel und einen ausdrücklich leeren Wert prüfen.
        for daten in [{}, {"matrikelnummer": ""}]:
            with self.subTest(daten=daten):
                self.pruefe_abweisung(daten, 400)

    def test_fa17_fehlende_teilnahmen_werden_gemeldet(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)

        self.pruefe_abweisung(
            {"matrikelnummer": "9999999"},
            404,
        )

    def test_fa17_nicht_erfuellter_status_verhindert_report(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)

        # Fall 1: 29,5 Gesamtstunden bei 15 Präsenzstunden.
        # Fall 2: 30 Gesamtstunden bei nur 14,5 Präsenzstunden.
        for online, praesenz in [(14.5, 15.0), (15.5, 14.5)]:
            with self.subTest(online=online, praesenz=praesenz):
                self.untersuchung_alpha.stundenwert = online
                self.untersuchung_alpha.save(
                    update_fields=["stundenwert"]
                )
                self.untersuchung_beta.stundenwert = praesenz
                self.untersuchung_beta.save(
                    update_fields=["stundenwert"]
                )

                # Die bewusst geänderten Werte sind der neue Vergleichsstand.
                self.untersuchungsbestand = list(
                    Untersuchung.objects.order_by("pk").values()
                )

                self.pruefe_abweisung(self.daten, 400)

    def test_fa17_erzeugungsfehler_wird_kontrolliert_beantwortet(self):
        self.melde_testkonto_an(Benutzerkonto.ADMINISTRATOR)
        interner_fehler = "INTERNER_TESTFEHLER"

        # Einen technischen Fehler ausschließlich für diesen Aufruf auslösen.
        with patch(
            "vp_stunden.views.erzeuge_report",
            side_effect=RuntimeError(interner_fehler),
        ) as reportfunktion:
            antwort = self.client.post(
                "/report_erzeugen/",
                data=self.daten,
            )

        self.assertEqual(antwort.status_code, 500)
        self.assertFalse(antwort.json()["erfolg"])
        self.assertNotIn(
            interner_fehler,
            antwort.content.decode("utf-8"),
        )
        reportfunktion.assert_called_once()
        self.pruefe_unveraenderten_bestand()


class UebergangsimportZuordnungTests(TestCase):
    """Prüft Zuordnung, Datenübernahme und vollständige Abweisung."""

    def setUp(self):
        # Django ruft setUp vor jeder Testmethode neu auf.
        # Alle Daten entstehen ausschließlich in der gesonderten Testdatenbank.
        self.untersuchung = Untersuchung.objects.create(
            studienname="Bestandsstudie",
            studienname_vergleich="bestandsstudie",
            stundenwert=1.5,
            einordnung=Untersuchung.PRAESENZ,
            lehrperson="Testlehrperson Alt",
        )
        Teilnahme.objects.create(
            untersuchung=self.untersuchung,
            matrikelnummer="7654321",
        )

        # values() erfasst sämtliche gespeicherten Felder einschließlich IDs
        # und Uploadzeitpunkt. list() hält den jetzigen Stand sofort fest.
        # Dadurch reichen später gleich gebliebene Anzahlen allein nicht aus.
        self.untersuchungsbestand = list(
            Untersuchung.objects.order_by("pk").values()
        )
        self.teilnahmebestand = list(
            Teilnahme.objects.order_by("pk").values()
        )

        # Die Testdatei wird in der Testdatenbank erzeugt, nicht auf der Festplatte.
        self.arbeitsmappe = Workbook()
        self.addCleanup(self.arbeitsmappe.close)
        self.blatt = self.arbeitsmappe.active
        self.blatt.title = "Übergangsimport"
        self.blatt.append([
            "Matrikelnummer",
            "Studienname",
            "Stundenwert (VP-Stunden)",
            "Einordnung (P/O)",
            "Verantwortliche Lehrperson",
        ])

        # Zeile 2 ergänzt die vorhandene Untersuchung. Andere Großschreibung
        # und äußere Leerzeichen dürfen die Zuordnung nicht verhindern.
        self.blatt.append([
            1234567,
            "  BESTANDSSTUDIE  ",
            1.5,
            Untersuchung.PRAESENZ,
            "  TESTLEHRPERSON ALT  ",
        ])

        # Die Leerzeile darf die Prüfung der folgenden Zeile nicht beenden.
        self.blatt.append([None, None, None, None, None])
        self.blatt.append([
            1234567,
            "  Neue Studie  ",
            2.5,
            Untersuchung.ONLINE,
            "  Testlehrperson Neu  ",
        ])

    def test_fa11_neue_und_vorhandene_untersuchung_werden_importiert(self):
        # BytesIO ersetzt eine Datei auf der Festplatte.
        # SimpleUploadedFile stellt die erzeugten XLSX-Bytes als Upload bereit.
        with BytesIO() as puffer:
            self.arbeitsmappe.save(puffer)
            datei = SimpleUploadedFile("uebergang.xlsx", puffer.getvalue())

        beginn = timezone.now()
        fehlerliste = importiere_uebergangsdatei(datei)
        ende = timezone.now()

        self.assertEqual(fehlerliste, [])

        neue_untersuchung = Untersuchung.objects.get(
            studienname_vergleich="neue studie"
        )
        self.assertEqual(
            (
                neue_untersuchung.studienname,
                neue_untersuchung.stundenwert,
                neue_untersuchung.einordnung,
                neue_untersuchung.lehrperson,
            ),
            ("Neue Studie", 2.5, Untersuchung.ONLINE, "Testlehrperson Neu"),
        )
        self.assertGreaterEqual(neue_untersuchung.uploadzeitpunkt, beginn)
        self.assertLessEqual(neue_untersuchung.uploadzeitpunkt, ende)

        # Außer der einen neuen Untersuchung muss der vollständige alte
        # Untersuchungsbestand erhalten sein, auch Schreibweise und Zeitpunkt.
        self.assertEqual(
            list(
                Untersuchung.objects.exclude(
                    pk=neue_untersuchung.pk
                ).order_by("pk").values()
            ),
            self.untersuchungsbestand,
        )

        # Beide neuen Teilnahmen gehören zur importierten Matrikelnummer.
        # Die IDs zeigen zugleich die Zuordnung und die Anlage in Zeilenfolge.
        self.assertEqual(
            list(
                Teilnahme.objects.filter(
                    matrikelnummer="1234567"
                ).order_by("pk").values_list("untersuchung_id", flat=True)
            ),
            [self.untersuchung.pk, neue_untersuchung.pk],
        )
        self.assertEqual(
            list(
                Teilnahme.objects.exclude(
                    matrikelnummer="1234567"
                ).order_by("pk").values()
            ),
            self.teilnahmebestand,
        )

    def test_fa11_unterschiedliche_matrikelnummern_werden_abgewiesen(self):
        self.blatt["A4"] = 2345678

        with BytesIO() as puffer:
            self.arbeitsmappe.save(puffer)
            datei = SimpleUploadedFile("uebergang.xlsx", puffer.getvalue())

        fehlerliste = importiere_uebergangsdatei(datei)

        # Die Zellfundstelle prüfen, ohne den gesamten Meldungstext festzulegen.
        # any() verlangt mindestens eine passende Meldung.
        self.assertTrue(
            any(meldung.startswith("A4:") for meldung in fehlerliste),
            fehlerliste,
        )
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            self.untersuchungsbestand,
        )
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            self.teilnahmebestand,
        )

    def test_fa12_doppelte_untersuchung_in_datei_wird_abgewiesen(self):
        # Zeile 5 wiederholt die neue Untersuchung mit anderer Schreibweise.
        # Auch die gültige Ergänzung aus Zeile 2 darf dann nicht gespeichert werden.
        self.blatt.append([
            1234567,
            "  NEUE STUDIE  ",
            2.5,
            Untersuchung.ONLINE,
            "Testlehrperson Neu",
        ])

        with BytesIO() as puffer:
            self.arbeitsmappe.save(puffer)
            datei = SimpleUploadedFile("uebergang.xlsx", puffer.getvalue())

        fehlerliste = importiere_uebergangsdatei(datei)

        self.assertTrue(
            any(meldung.startswith("B5:") for meldung in fehlerliste),
            fehlerliste,
        )
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            self.untersuchungsbestand,
        )
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            self.teilnahmebestand,
        )

    def test_fa12_bereits_gespeicherte_teilnahme_wird_abgewiesen(self):
        Teilnahme.objects.create(
            untersuchung=self.untersuchung,
            matrikelnummer="1234567",
        )

        # Diese zusätzliche Teilnahme gehört jetzt zum vorbereiteten Bestand.
        teilnahmebestand_vor_import = list(
            Teilnahme.objects.order_by("pk").values()
        )

        with BytesIO() as puffer:
            self.arbeitsmappe.save(puffer)
            datei = SimpleUploadedFile("uebergang.xlsx", puffer.getvalue())

        fehlerliste = importiere_uebergangsdatei(datei)

        self.assertTrue(
            any(meldung.startswith("Zeile 2:") for meldung in fehlerliste),
            fehlerliste,
        )
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            self.untersuchungsbestand,
        )
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            teilnahmebestand_vor_import,
        )

    def test_fa12_abweichende_bestandsangaben_werden_abgewiesen(self):
        # Jeder Wert ist für sich zulässig, widerspricht aber dem Bestand.
        # Einzeln prüfen, damit kein anderer Fehler eine fehlende Prüfung verdeckt.
        for adresse, abweichender_wert in [
            ("C2", 2.0),
            ("D2", Untersuchung.ONLINE),
            ("E2", "Andere Testlehrperson"),
        ]:
            with self.subTest(zelle=adresse):
                urspruenglicher_wert = self.blatt[adresse].value
                self.blatt[adresse] = abweichender_wert

                # Jeder Teilfall braucht einen neuen Upload, weil die
                # Importfunktion den vorherigen Upload bereits geschlossen hat.
                with BytesIO() as puffer:
                    self.arbeitsmappe.save(puffer)
                    datei = SimpleUploadedFile("uebergang.xlsx", puffer.getvalue())

                fehlerliste = importiere_uebergangsdatei(datei)

                # Das gemeinsame Workbook für den nächsten Teilfall zurücksetzen.
                self.blatt[adresse] = urspruenglicher_wert

                self.assertTrue(
                    any(
                        meldung.startswith(f"{adresse}:")
                        for meldung in fehlerliste
                    ),
                    fehlerliste,
                )
                self.assertEqual(
                    list(Untersuchung.objects.order_by("pk").values()),
                    self.untersuchungsbestand,
                )
                self.assertEqual(
                    list(Teilnahme.objects.order_by("pk").values()),
                    self.teilnahmebestand,
                )

    def test_fa11_zellfehler_werden_gesammelt_und_datei_abgewiesen(self):
        # Zeile 4 ist teilweise gefüllt und muss vollständig geprüft werden.
        # Der ungültige Stundenwert darf die Prüfung der fehlenden Lehrperson
        # nicht verhindern. Auch Zeile 2 darf nicht übernommen werden.
        self.blatt["C4"] = 0.25
        self.blatt["E4"] = None

        with BytesIO() as puffer:
            self.arbeitsmappe.save(puffer)
            datei = SimpleUploadedFile("uebergang.xlsx", puffer.getvalue())

        fehlerliste = importiere_uebergangsdatei(datei)

        for fundstelle in ["C4:", "E4:"]:
            self.assertTrue(
                any(meldung.startswith(fundstelle) for meldung in fehlerliste),
                fehlerliste,
            )
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            self.untersuchungsbestand,
        )
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            self.teilnahmebestand,
        )

    def test_fa11_speicherfehler_nimmt_alle_aenderungen_zurueck(self):
        with BytesIO() as puffer:
            self.arbeitsmappe.save(puffer)
            datei = SimpleUploadedFile("uebergang.xlsx", puffer.getvalue())

        # wraps hält die echte Speichermethode fest. DEFAULT lässt den ersten
        # Aufruf normal speichern: die Ergänzung zur vorhandenen Untersuchung.
        # Beim zweiten Teilnahmeaufruf ist auch die neue Untersuchung angelegt.
        # Erst dann löst der Test einen Fehler aus. So wird eine tatsächliche
        # Rücknahme beider Änderungsarten geprüft.
        with patch(
            "vp_stunden.importe.Teilnahme.objects.create",
            wraps=Teilnahme.objects.create,
            side_effect=[DEFAULT, DatabaseError("INTERNER_TESTFEHLER")],
        ) as teilnahmespeicherung:
            fehlerliste = importiere_uebergangsdatei(datei)

        self.assertEqual(teilnahmespeicherung.call_count, 2)
        self.assertEqual(
            fehlerliste,
            ["Datei: Der Übergangsimport konnte nicht übernommen werden."],
        )
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            self.untersuchungsbestand,
        )
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            self.teilnahmebestand,
        )


class RegulaererImportTests(TestCase):
    """Prüft Datenübernahme und vollständige Abweisung beim regulären Import."""

    def setUp(self):
        # Jeder Test beginnt mit demselben synthetischen Altbestand.
        # Untersuchung und Teilnahme liegen in der gesonderten Testdatenbank.
        self.untersuchung = Untersuchung.objects.create(
            studienname="Bestandsstudie",
            studienname_vergleich="bestandsstudie",
            stundenwert=1.5,
            einordnung=Untersuchung.PRAESENZ,
            lehrperson="Testlehrperson Alt",
        )
        Teilnahme.objects.create(
            untersuchung=self.untersuchung,
            matrikelnummer="9876543",
        )

        # Vollständige Feldwerte sofort festhalten. So werden später auch
        # unbeabsichtigte Änderungen erkannt, bei denen die Anzahl gleich bleibt.
        self.untersuchungsbestand = list(
            Untersuchung.objects.order_by("pk").values()
        )
        self.teilnahmebestand = list(
            Teilnahme.objects.order_by("pk").values()
        )

        # Die Arbeitsmappe entsteht im Arbeitsspeicher.
        # addCleanup sorgt nach dem Test für das Schließen der Arbeitsmappe.
        self.arbeitsmappe = Workbook()
        self.addCleanup(self.arbeitsmappe.close)
        self.blatt = self.arbeitsmappe.active
        self.blatt.title = "Untersuchung"

        self.blatt["A1"] = "Studienname"
        self.blatt["A2"] = "Stundenwert (VP-Stunden)"
        self.blatt["A3"] = "Einordnung (P/O)"
        self.blatt["A4"] = "Verantwortliche Lehrperson"
        self.blatt["A6"] = "Matrikelnummer"

        self.blatt["B1"] = "  Neue Studie  "
        self.blatt["B2"] = 2.5
        self.blatt["B3"] = Untersuchung.ONLINE
        self.blatt["B4"] = "  Testlehrperson Neu  "

        # Zahlen in Excel eintragen. Erst der Import wandelt sie für
        # die Speicherung in Zeichenfolgen um. Die Lücke darf ihn nicht stoppen.
        self.blatt["A7"] = 1234567
        self.blatt["A106"] = 7654321

    def test_fa10_untersuchung_und_teilnahmen_werden_gespeichert(self):
        # Die Arbeitsmappe als XLSX-Bytes schreiben und als Speicherupload
        # bereitstellen. Es wird keine Datei auf der Festplatte angelegt.
        with BytesIO() as puffer:
            self.arbeitsmappe.save(puffer)
            datei = SimpleUploadedFile("untersuchung.xlsx", puffer.getvalue())

        beginn = timezone.now()
        fehlerliste = importiere_untersuchung(datei)
        ende = timezone.now()

        self.assertEqual(fehlerliste, [])

        neue_untersuchung = Untersuchung.objects.get(
            studienname_vergleich="neue studie"
        )
        self.assertEqual(
            (
                neue_untersuchung.studienname,
                neue_untersuchung.stundenwert,
                neue_untersuchung.einordnung,
                neue_untersuchung.lehrperson,
            ),
            ("Neue Studie", 2.5, Untersuchung.ONLINE, "Testlehrperson Neu"),
        )
        self.assertGreaterEqual(neue_untersuchung.uploadzeitpunkt, beginn)
        self.assertLessEqual(neue_untersuchung.uploadzeitpunkt, ende)

        # Außer der neuen Untersuchung muss der alte Bestand vollständig
        # unverändert bleiben, einschließlich seines Uploadzeitpunkts.
        self.assertEqual(
            list(
                Untersuchung.objects.exclude(
                    pk=neue_untersuchung.pk
                ).order_by("pk").values()
            ),
            self.untersuchungsbestand,
        )

        # Genau die beiden Nummern müssen derselben neuen Untersuchung
        # zugeordnet sein. A106 muss trotz der vorherigen Lücke übernommen werden.
        self.assertEqual(
            list(
                Teilnahme.objects.filter(
                    untersuchung=neue_untersuchung
                ).order_by("pk").values_list("matrikelnummer", flat=True)
            ),
            ["1234567", "7654321"],
        )
        self.assertEqual(
            list(
                Teilnahme.objects.exclude(
                    untersuchung=neue_untersuchung
                ).order_by("pk").values()
            ),
            self.teilnahmebestand,
        )

    def test_fa08_doppelte_matrikelnummer_wird_abgewiesen(self):
        self.blatt["A106"] = 1234567

        with BytesIO() as puffer:
            self.arbeitsmappe.save(puffer)
            datei = SimpleUploadedFile("untersuchung.xlsx", puffer.getvalue())

        fehlerliste = importiere_untersuchung(datei)

        # Mindestens eine Meldung muss die verursachende Zelle nennen.
        self.assertTrue(
            any(meldung.startswith("A106:") for meldung in fehlerliste),
            fehlerliste,
        )
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            self.untersuchungsbestand,
        )
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            self.teilnahmebestand,
        )

    def test_fa08_bereits_gespeicherte_untersuchung_wird_abgewiesen(self):
        # Äußere Leerzeichen und andere Großschreibung dürfen den
        # Bestandskonflikt nicht verdecken. Regulär wird nichts ergänzt.
        self.blatt["B1"] = "  BESTANDSSTUDIE  "

        with BytesIO() as puffer:
            self.arbeitsmappe.save(puffer)
            datei = SimpleUploadedFile("untersuchung.xlsx", puffer.getvalue())

        fehlerliste = importiere_untersuchung(datei)

        self.assertTrue(
            any(meldung.startswith("B1:") for meldung in fehlerliste),
            fehlerliste,
        )
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            self.untersuchungsbestand,
        )
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            self.teilnahmebestand,
        )

    def test_fa09_unabhaengige_zellfehler_werden_gesammelt(self):
        # Die einzelnen Feldprüfungen haben bereits eigene Tests.
        # Hier wird geprüft, ob der Import sie einbindet und ihre Fehler
        # unabhängig sammelt, auch wenn schon der Studienname ungültig ist.
        self.blatt["B1"] = "   "
        self.blatt["B2"] = 0.25
        self.blatt["B3"] = "p"
        self.blatt["B4"] = None
        self.blatt["A106"] = "7654321"

        with BytesIO() as puffer:
            self.arbeitsmappe.save(puffer)
            datei = SimpleUploadedFile("untersuchung.xlsx", puffer.getvalue())

        fehlerliste = importiere_untersuchung(datei)

        for fundstelle in ["B1:", "B2:", "B3:", "B4:", "A106:"]:
            self.assertTrue(
                any(meldung.startswith(fundstelle) for meldung in fehlerliste),
                fehlerliste,
            )

        # Auch die weiterhin gültige Nummer in A7 darf nicht gespeichert werden.
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            self.untersuchungsbestand,
        )
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            self.teilnahmebestand,
        )

    def test_fa06_ohne_matrikelnummer_wird_datei_abgewiesen(self):
        self.blatt["A7"] = None
        self.blatt["A106"] = None

        with BytesIO() as puffer:
            self.arbeitsmappe.save(puffer)
            datei = SimpleUploadedFile("untersuchung.xlsx", puffer.getvalue())

        fehlerliste = importiere_untersuchung(datei)

        self.assertTrue(
            any(meldung.startswith("A7:A106:") for meldung in fehlerliste),
            fehlerliste,
        )
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            self.untersuchungsbestand,
        )
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            self.teilnahmebestand,
        )

    def test_fa09_speicherfehler_nimmt_alle_aenderungen_zurueck(self):
        with BytesIO() as puffer:
            self.arbeitsmappe.save(puffer)
            datei = SimpleUploadedFile("untersuchung.xlsx", puffer.getvalue())

        # wraps hält die echte Speichermethode fest. DEFAULT lässt den ersten
        # Teilnahmeaufruf tatsächlich speichern. Erst der zweite scheitert.
        # Dann müssen sowohl die Untersuchung als auch die erste Teilnahme
        # durch die gemeinsame Transaktion zurückgenommen werden.
        with patch(
            "vp_stunden.importe.Teilnahme.objects.create",
            wraps=Teilnahme.objects.create,
            side_effect=[DEFAULT, DatabaseError("INTERNER_TESTFEHLER")],
        ) as teilnahmespeicherung:
            fehlerliste = importiere_untersuchung(datei)

        self.assertEqual(teilnahmespeicherung.call_count, 2)
        self.assertEqual(
            fehlerliste,
            ["Datei: Der Import konnte nicht übernommen werden."],
        )
        self.assertEqual(
            list(Untersuchung.objects.order_by("pk").values()),
            self.untersuchungsbestand,
        )
        self.assertEqual(
            list(Teilnahme.objects.order_by("pk").values()),
            self.teilnahmebestand,
        )