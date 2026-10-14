from django.contrib.auth.password_validation import validate_password # Bibliothek für Passwortvalidierung
from django.core.exceptions import ValidationError # Bibliothek für Fehlerbehandlung
from django.test import SimpleTestCase # Bibliothek für Unit-Tests ohne Datenbankzugriff
from vp_stunden.models import Benutzerkonto # Import des benutzerdefinierten Benutzerkontos-Modells
from django.contrib.auth.hashers import get_hasher # Import der Passwort-Hashing-Funktion
from django.test import TestCase  # Bibliothek für Unit-Tests mit Datenbankzugriff

# Testklasse für die Passwortvalidierung
class PasswortregelnTests(SimpleTestCase):
    def test_qa01_14_zeichen_werden_abgewiesen(self):

        with self.assertRaises(ValidationError):
            validate_password('a' * 14)  # 14 Zeichen, sollte abgewiesen werden

    def test_qa01_15_zeichen_werden_akzeptiert(self):
        self.assertIsNone(validate_password('a' * 15))  # 15 Zeichen, sollte akzeptiert werden

    def test_qa01_64_zeichen_werden_akzeptiert(self):
        self.assertIsNone(validate_password('a' * 64))  # 64 Zeichen, sollte akzeptiert werden

    def test_qa01_65_zeichen_werden_akzeptiert(self):
        self.assertIsNone(validate_password('a' * 65))  # 65 Zeichen, sollte akzeptiert werden

    def test_qa01_reines_zahlenpasswort_wird_akzeptiert(self):
        self.assertIsNone(validate_password('123456789012345'))  # Reines Zahlenpasswort, sollte akzeptiert werden


# Testklasse für das Passwort-Hashing und die Passwortüberprüfung
class PasswortHashingTests(SimpleTestCase):
    def test_qa01_passwortvergleich(self):
        # Testen des Passwort-Hashings und der Passwortüberprüfung
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

