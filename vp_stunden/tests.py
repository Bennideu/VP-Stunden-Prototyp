from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError # Bibliothek für Fehlerbehandlung
from django.test import SimpleTestCase # Bibliothek für Unit-Tests ohne Datenbankzugriff

# Create your tests here.
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


