# Anforderungsbezogene Tests für Passwörter, Benutzerkonten und Anmeldebegrenzung

from unittest.mock import patch  # Funktionen während eines Tests gezielt ersetzen

from django.contrib.auth.password_validation import validate_password  # Die konfigurierten Django-Passwortregeln prüfen
from django.core.exceptions import ValidationError  # Ausnahme bei verletzten Validierungsregeln
from django.http import HttpRequest  # HTTP-Anfrageobjekte für direkte Funktionstests erzeugen
from django.test import SimpleTestCase  # Django-Testklasse ohne Datenbankzugriff
from django.utils import timezone  # Zeitzonenbewusste Zeitpunkte und Zeitabstände verwenden
from vp_stunden.models import Benutzerkonto  # Das benutzerdefinierte Kontenmodell verwenden
from django.contrib.auth.hashers import get_hasher  # Den konfigurierten Passwort-Hasher abrufen
from django.test import TestCase  # Django-Testklasse für Tests mit Datenbankzugriff
from django.contrib.auth import get_user  # Konto anhand der Sitzungsdaten ermitteln
from vp_stunden.sicherheit import lege_konto_an, melde_an, melde_ab, pruefe_zugriff, setze_passwort_zurueck, aendere_passwort  # Zu prüfende Funktionen für Kontenanlage, Anmeldung, Abmeldung und Zugriffskontrolle
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.auth import SESSION_KEY, get_user

from vp_stunden.views import melde_an_view

# Passwortlängen und erlaubte Zeichenfolgen nach QA-01 prüfen
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