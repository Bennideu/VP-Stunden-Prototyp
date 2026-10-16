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

from vp_stunden.sicherheit import lege_konto_an, melde_an  # Zu prüfende Funktionen zur Kontenanlage und Anmeldung
from vp_stunden.sicherheit import setze_passwort_zurueck  # Zu prüfende Funktion zum Passwortzurücksetzen


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
        # Den Anmeldeversuch mit dem vorbereiteten Konto ausführen
        fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort)
        self.assertTrue(fehlerliste_anmeldung)  # Mindestens eine Fehlermeldung erwarten
        self.assertIn("Anmeldung fehlgeschlagen", fehlerliste_anmeldung[0])


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
        # Die Anmeldung mit einem festgelegten Prüfzeitpunkt ausführen
        with patch('vp_stunden.sicherheit.timezone.now', return_value=testzeitpunkt):
            fehlerliste = melde_an(anfrage, benutzername, passwort='falschesPW')
        self.assertTrue(fehlerliste)  # Mindestens eine Fehlermeldung erwarten

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
        # Die Prüfungen auf den tatsächlich gespeicherten Datenbankzustand beziehen
        konto.refresh_from_db()  # Kontoobjekt aus der Datenbank aktualisieren
        self.assertEqual(konto.fehlversuche, 0)
        self.assertIsNone(konto.fehlversuchszeitraum_beginn)
        self.assertIsNone(konto.gesperrt_bis)