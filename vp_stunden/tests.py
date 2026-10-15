from unittest.mock import patch # Bibliothek für das Mocking von Funktionen und Methoden

from django.contrib.auth.password_validation import validate_password # Bibliothek für Passwortvalidierung
from django.core.exceptions import ValidationError # Bibliothek für Fehlerbehandlung
from django.http import HttpRequest
from django.test import SimpleTestCase
from django.utils import timezone # Bibliothek für Unit-Tests ohne Datenbankzugriff
from vp_stunden.models import Benutzerkonto # Import des benutzerdefinierten Benutzerkontos-Modells
from django.contrib.auth.hashers import get_hasher # Import der Passwort-Hashing-Funktion
from django.test import TestCase

from vp_stunden.sicherheit import lege_konto_an, melde_an  # Bibliothek für Unit-Tests mit Datenbankzugriff
from vp_stunden.sicherheit import setze_passwort_zurueck  # Bibliothek für Unit-Tests mit Datenbankzugriff

# Testklasse für die Passwortvalidierung
class PasswortregelnTests(SimpleTestCase):

    # Test für die Passwortlänge: 14 Zeichen sollten abgewiesen werden
    def test_qa01_14_zeichen_werden_abgewiesen(self):
        with self.assertRaises(ValidationError):
            validate_password('a' * 14)

    # Test für die Passwortlänge: 15 Zeichen sollten akzeptiert werden
    def test_qa01_15_zeichen_werden_akzeptiert(self):
        self.assertIsNone(validate_password('a' * 15))

    # Test für die Passwortlänge: 64 Zeichen sollten akzeptiert werden
    def test_qa01_64_zeichen_werden_akzeptiert(self):
        self.assertIsNone(validate_password('a' * 64))

    # Test für die Passwortlänge: 65 Zeichen sollten akzeptiert werden
    def test_qa01_65_zeichen_werden_akzeptiert(self):
        self.assertIsNone(validate_password('a' * 65))

    # Test für die Passwortzeichen: Reines Zahlenpasswort sollte akzeptiert werden
    def test_qa01_reines_zahlenpasswort_wird_akzeptiert(self):
        self.assertIsNone(validate_password('123456789012345'))  # Reines Zahlenpasswort, sollte akzeptiert werden


# Testklasse für das Passwort-Hashing und die Passwortüberprüfung
class PasswortHashingTests(SimpleTestCase):

    # Test für das Passwort-Hashing und die Passwortüberprüfung
    def test_qa01_passwortvergleich(self):
        testpasswort = 'a' * 64
        konto = Benutzerkonto(username='testuser', rolle=Benutzerkonto.LEHRPERSON)
        konto.set_password(testpasswort)  # Passwort wird gehasht und im Benutzerkonto gespeichert
        self.assertNotEqual(konto.password, testpasswort)  # Das gespeicherte Passwort sollte nicht dem Klartext-Passwort entsprechen
        self.assertTrue(konto.check_password(testpasswort))  # Überprüfung, ob das gehashte Passwort mit dem Klartext-Passwort übereinstimmt

        # Testen eines falschen Passworts
        testpasswort_falsch = 'a' * 63 + 'b'
        self.assertFalse(konto.check_password(testpasswort_falsch))  # Überprüfung,

        # Testen des Passwort-Hashing-Algorithmus und der Parameter
        hasher = get_hasher()  # Abrufen des Passwort-Hashers
        hasher_decoded = hasher.decode(konto.password)  # Hashbestandteile auslesen
        self.assertEqual(hasher_decoded['algorithm'], 'argon2')  # Überprüfung, ob der verwendete Algorithmus Argon2 ist
        self.assertEqual(hasher_decoded['time_cost'], 2)  # Überprüfung der Anzahl der Iterationen
        self.assertEqual(hasher_decoded['memory_cost'], 102400)  # Überprüfung der Speichergröße
        self.assertEqual(hasher_decoded['parallelism'], 8)  # Überprüfung der Parallelität
        self.assertEqual(hasher_decoded['variety'], 'argon2id')  # Überprüfung der Varietät des Hashing-Algorithmus

        # Vergleich der Salts, bei zweimaligem Hashing sollten unterschiedliche Salts verwendet werden
        konto.set_password(testpasswort)  # Passwort wird erneut gehasht
        hasher_decoded_neu = hasher.decode(konto.password)  # Hashbestandteile auslesen des neuen gehashten Passworts
        self.assertNotEqual(hasher_decoded['salt'], hasher_decoded_neu['salt'])  # Überprüfung, ob die Salts


# Testklasse für die Speicherung des Passwort-Hashes in der Datenbank
class PasswortspeicherungTests(TestCase):

    # Test für die Speicherung des Passwort-Hashes in der Datenbank
    def test_qa01_hash_wird_gespeichert(self):
        testpasswort = 'a' * 64
        konto = Benutzerkonto(username='testuser', rolle=Benutzerkonto.LEHRPERSON)
        konto.set_password(testpasswort)  # Passwort wird gehasht und im Benutzerkonto gespeichert
        passwort_hash = konto.password  # Abrufen des gespeicherten Passwort-Hashes
        konto.save()  # Speichern des Benutzerkontos in der Datenbank
        konto_aus_db = Benutzerkonto.objects.get(username='testuser')  # Abrufen des Benutzerkontos aus der Datenbank
        self.assertEqual(konto_aus_db.password, passwort_hash)  # Überprüfung, ob der gespeicherte Passwort-Hash mit dem aus der Datenbank übereinstimmt
        self.assertFalse(konto_aus_db.password == testpasswort)  # Überprüfung, dass der gespeicherte Passwort-Hash nicht dem Klartext-Passwort entspricht
        self.assertTrue(konto_aus_db.check_password(testpasswort))  # Überprüfung, ob das gehashte Passwort mit dem Klartext-Passwort übereinstimmt


# Testklasse für die Erstellung eines Benutzerkontos
class KontoErstellungTests(TestCase):

    # Test für die Erstellung eines Benutzerkontos mit einem zu kurzen Passwort
    def test_qa01_kurzes_passwort_verhindert_kontoerstellung(self):
        benutzername = 'testnutzer'
        passwort = 'a' * 14  # Kurzes Passwort, das die Mindestanforderungen nicht erfüllt
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)  # Versuch, ein Konto mit einem kurzen Passwort zu erstellen
        self.assertIsNone(konto)  # Überprüfung, dass kein Konto erstellt wurde
        self.assertTrue(fehlerliste)  # Überprüfung, dass eine Fehlerliste zurückgegeben wurde
        self.assertFalse(Benutzerkonto.objects.filter(username=benutzername).exists())  # Überprüfung, dass kein Konto in der Datenbank existiert

    # Test für die erfolgreiche Erstellung eines Benutzerkontos mit einem gültigen Passwort
    def test_fa02_erfolgreiche_kontoerstellung(self):
        benutzername = 'testnutzer'
        passwort = 'a' * 64  # Gültiges Passwort, das die Mindestanforderungen erfüllt
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)  # Versuch, ein Konto mit einem gültigen Passwort zu erstellen
        self.assertIsNotNone(konto)  # Überprüfung, dass ein Konto erstellt wurde
        self.assertFalse(fehlerliste)  # Überprüfung, dass keine Fehlerliste zurückgegeben wurde
        self.assertTrue(Benutzerkonto.objects.filter(username=benutzername).exists())  # Überprüfung, dass das Konto in der Datenbank existiert

        benutzerkonto_aus_db = Benutzerkonto.objects.get(username=benutzername)  # Abrufen des Benutzerkontos aus der Datenbank
        self.assertTrue(benutzerkonto_aus_db.check_password(passwort))  # Überprüfung, ob das gehashte Passwort mit dem Klartext-Passwort übereinstimmt
        self.assertEqual(benutzerkonto_aus_db.rolle, rolle)  # Überprüfung, ob die Rolle des Benutzerkontos korrekt gespeichert wurde
        self.assertNotEqual(benutzerkonto_aus_db.password, passwort)  # Überprüfung, dass der gespeicherte Passwort-Hash nicht dem Klartext-Passwort entspricht
        self.assertEqual(benutzerkonto_aus_db.username, benutzername)  # Überprüfung, dass der Benutzername korrekt gespeichert wurde


    # Test für die Erstellung eines Benutzerkontos mit einer ungültigen Rolle
    def test_fa02_ungueltige_rolle_verhindert_kontoerstellung(self):
        benutzername = 'testnutzer'
        passwort = 'a' * 64  # Gültiges Passwort, das die Mindestanforderungen erfüllt
        rolle = 'ungültig'  # Ungültige Rolle
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)  # Versuch, ein Konto mit einer ungültigen Rolle zu erstellen
        self.assertIsNone(konto)  # Überprüfung, dass kein Konto erstellt wurde
        self.assertTrue(fehlerliste)  # Überprüfung, dass eine Fehlerliste zurückgegeben wurde
        self.assertFalse(Benutzerkonto.objects.filter(username=benutzername).exists())  # Überprüfung, dass kein Konto in der Datenbank existiert

    def test_fa02_doppelte_benutzername_verhindert_kontoerstellung(self):
        benutzername = 'testnutzer'
        passwort = 'a' * 64  # Gültiges Passwort, das die Mindestanforderungen erfüllt
        rolle = Benutzerkonto.LEHRPERSON
        # Erstelle das erste Konto
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)

        # Versuche, ein zweites Konto mit demselben Benutzernamen zu erstellen
        konto2, fehlerliste2 = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNone(konto2)
        self.assertTrue(fehlerliste2)
        self.assertTrue(Benutzerkonto.objects.filter(username=benutzername).count() == 1)


class PasswortZuruecksetzenTests(TestCase):

    # Test für das Zurücksetzen des Passworts eines bestehenden Benutzerkontos
    def test_fa02_passwort_zuruecksetzen(self):
        # Erstelle ein Benutzerkonto
        benutzername = 'testnutzer'
        passwort = 'a' * 64  # Gültiges Passwort, das die Mindestanforderungen erfüllt
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)

        # Setze das Passwort zurück
        neues_passwort = 'b' * 64  # Neues gültiges Passwort
        fehlerliste_zuruecksetzen = setze_passwort_zurueck(konto.pk, neues_passwort)
        self.assertFalse(fehlerliste_zuruecksetzen)  # Überprüfung, dass keine Fehlerliste zurückgegeben wurde
        konto.refresh_from_db()  # Aktualisiere das Konto aus der Datenbank
        self.assertTrue(konto.check_password(neues_passwort))  # Überprüfung, ob das gehashte Passwort mit dem neuen Klartext-Passwort übereinstimmt
        self.assertFalse(konto.check_password(passwort))  # Überprüfung, dass das alte Passwort nicht mehr gültig ist

    # Test für das Zurücksetzen des Passworts mit einem zu kurzen Passwort
    def test_qa01_zu_kurzes_passwort_laesst_altes_passwort_unveraendert(self):
        # Erstelle ein Benutzerkonto
        benutzername = 'testnutzer'
        passwort = 'a' * 64  # Gültiges Passwort, das die Mindestanforderungen erfüllt
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)

        # Versuche, das Passwort mit einem zu kurzen Passwort zurückzusetzen
        zu_kurzes_passwort = 'c' * 14  # Zu kurzes Passwort
        passwort_hash_vorher = konto.password  # Speichere den Passwort-Hash vor dem Zurücksetzen
        fehlerliste_zuruecksetzen = setze_passwort_zurueck(konto.pk, zu_kurzes_passwort)
        self.assertTrue(fehlerliste_zuruecksetzen)  # Überprüfung, dass eine Fehlerliste zurückgegeben wurde
        konto.refresh_from_db()  # Aktualisiere das Konto aus der Datenbank
        self.assertEqual(konto.password, passwort_hash_vorher)  # Überprüfung, dass der Passwort-Hash unverändert geblieben ist
        self.assertTrue(konto.check_password(passwort))  # Überprüfung, dass das alte Passwort weiterhin gültig ist
        self.assertFalse(konto.check_password(zu_kurzes_passwort))  # Überprüfung, dass das zu kurze Passwort nicht gültig ist


    def test_fa02_nicht_vorhandenes_konto_wird_abgewiesen(self):
        # Versuche, das Passwort für ein nicht vorhandenes Konto zurückzusetzen
        konto_id = 1  # ID eines nicht vorhandenen Kontos
        self.assertFalse(Benutzerkonto.objects.filter(pk=konto_id).exists())  # Überprüfung, dass das Konto nicht existiert
        neues_passwort = 'b' * 64  # Neues gültiges Passwort
        fehlerliste_zuruecksetzen = setze_passwort_zurueck(konto_id, neues_passwort)
        self.assertTrue(fehlerliste_zuruecksetzen)  # Überprüfung, dass eine Fehlerliste zurückgegeben wurde
        self.assertFalse(Benutzerkonto.objects.filter(pk=konto_id).exists())  # Überprüfung, dass das Konto weiterhin nicht existiert


class AnmeldeTests(TestCase):

    def test_qa02_aktive_sperre_verhindert_anmeldung(self):
        # Erstelle ein Benutzerkonto
        benutzername = 'testnutzer'
        passwort = 'a' * 64  # Gültiges Passwort, das die Mindestanforderungen erfüllt
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)

        # Sperre das Konto für 5 Minuten
        konto.gesperrt_bis = timezone.now() + timezone.timedelta(minutes=5)  # Sperre das Konto für 5 Minuten
        sperrende_vorher = konto.gesperrt_bis  # Speichere den Zeitpunkt, bis zu dem das Konto gesperrt ist
        konto.save()

        # Versuche, sich während der Sperrzeit anzumelden
        anfrage = HttpRequest()
        fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort)
        self.assertTrue(fehlerliste_anmeldung)  # Überprüfung, dass eine Fehlerliste zurückgegeben wurde
        self.assertIn("Anmeldung fehlgeschlagen", fehlerliste_anmeldung[0])  # Überprüfung, dass die Fehlermeldung "Anmeldung fehlgeschlagen" enthalten ist

        # Überprüfung, dass der Zeitpunkt, bis zu dem das Konto gesperrt ist, unverändert geblieben ist
        konto.refresh_from_db()  # Aktualisiere das Konto aus der Datenbank
        self.assertEqual(konto.gesperrt_bis, sperrende_vorher)

    def test_qa02_sperrende_setzt_sperrzustand_zurueck(self):
        # Erstelle ein Benutzerkonto
        benutzername = 'testnutzer'
        passwort = 'a' * 64  # Gültiges Passwort, das die Mindestanforderungen erfüllt
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)

        testzeitpunkt = timezone.now()
        konto.fehlversuche = 5  # Setze die Anzahl der fehlgeschlagenen Anmeldeversuche auf 5
        konto.fehlversuchszeitraum_beginn = testzeitpunkt - timezone.timedelta(minutes=10)  # Setze den Beginn des Zeitraums der fehlgeschlagenen Anmeldeversuche auf 10 Minuten vor dem aktuellen Zeitpunkt
        konto.gesperrt_bis = testzeitpunkt # Setze den Zeitpunkt, bis zu dem das Konto gesperrt ist, auf den aktuellen Zeitpunkt
        konto.save()

        # Versuche, sich nach Ablauf der Sperrzeit anzumelden
        anfrage = HttpRequest()
        with patch('vp_stunden.sicherheit.timezone.now', return_value=testzeitpunkt):
            fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort)
        self.assertFalse(fehlerliste_anmeldung)  # Überprüfung, dass keine Fehlerliste zurückgegeben wurde
        konto.refresh_from_db()  # Aktualisiere das Konto aus der Datenbank
        self.assertIsNone(konto.gesperrt_bis)  # Überprüfung, dass der Zeitpunkt, bis zu dem das Konto gesperrt ist, auf None zurückgesetzt wurde
        self.assertEqual(konto.fehlversuche, 0)  # Überprüfung, dass die Anzahl der fehlgeschlagenen Anmeldeversuche auf 0 zurückgesetzt wurde
        self.assertIsNone(konto.fehlversuchszeitraum_beginn)  # Überprüfung, dass der Beginn des Zeitraums der fehlgeschlagenen Anmeldeversuche auf None zurückgesetzt wurde


    def test_qa02_fensterende_setzt_fehlversuche_zurueck(self):
        # Erstelle ein Benutzerkonto
        benutzername = 'testnutzer'
        passwort = 'a' * 64  # Gültiges Passwort, das die Mindestanforderungen erfüllt
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)

        testzeitpunkt = timezone.now()
        konto.fehlversuche = 3  # Setze die Anzahl der fehlgeschlagenen Anmeldeversuche auf 3
        konto.fehlversuchszeitraum_beginn = testzeitpunkt - timezone.timedelta(minutes=15)  # Setze den Beginn des Zeitraums der fehlgeschlagenen Anmeldeversuche auf 10 Minuten vor dem aktuellen Zeitpunkt
        konto.save()

        # Versuche, sich nach Ablauf des Zeitraums der fehlgeschlagenen Anmeldeversuche anzumelden
        anfrage = HttpRequest()
        with patch('vp_stunden.sicherheit.timezone.now', return_value=testzeitpunkt):
            fehlerliste_anmeldung = melde_an(anfrage, benutzername, passwort)
        self.assertFalse(fehlerliste_anmeldung)  # Überprüfung, dass keine Fehlerliste zurückgegeben wurde
        konto.refresh_from_db()  # Aktualisiere das Konto aus der Datenbank
        self.assertEqual(konto.fehlversuche, 0)  # Überprüfung, dass die Anzahl der fehlgeschlagenen Anmeldeversuche auf 0 zurückgesetzt wurde
        self.assertIsNone(konto.fehlversuchszeitraum_beginn)
        self.assertIsNone(konto.gesperrt_bis)  # Überprüfung, dass der Zeitpunkt, bis zu dem das Konto gesperrt ist, auf None zurückgesetzt wurde

    def test_qa02_fuenfter_fehlversuch_sperrt_fuenf_minuten(self):
        # Erstelle ein Benutzerkonto
        benutzername = 'testnutzer'
        passwort = 'a' * 64  # Gültiges Passwort, das die Mindestanforderungen erfüllt
        rolle = Benutzerkonto.LEHRPERSON
        konto, fehlerliste = lege_konto_an(benutzername, passwort, rolle)
        self.assertIsNotNone(konto)
        self.assertFalse(fehlerliste)

        testzeitpunkt = timezone.now()
        fensterbeginn_vorher = testzeitpunkt - timezone.timedelta(minutes=1)

        konto.fehlversuche = 4  # Setze die Anzahl der fehlgeschlagenen Anmeldeversuche auf 4
        konto.fehlversuchszeitraum_beginn = fensterbeginn_vorher  # Setze den Beginn des Zeitraums der fehlgeschlagenen Anmeldeversuche auf den aktuellen Zeitpunkt
        konto.save()

        anfrage = HttpRequest()
        with patch('vp_stunden.sicherheit.timezone.now', return_value=testzeitpunkt):
            fehlerliste_anmeldung = melde_an(anfrage, benutzername, 'falsches_passwort')  # Versuche, sich mit einem falschen Passwort anzumelden
        self.assertTrue(fehlerliste_anmeldung)  # Überprüfung, dass eine Fehlerliste zurückgegeben wurde
        konto.refresh_from_db()  # Aktualisiere das Konto aus der Datenbank
        self.assertEqual(konto.fehlversuche,5)
        self.assertEqual(konto.fehlversuchszeitraum_beginn,fensterbeginn_vorher)
        self.assertEqual(testzeitpunkt + timezone.timedelta(minutes=5),konto.gesperrt_bis)
