from django.db import models
from django.contrib.auth.models import AbstractUser

# Klasse für das benutzerdefinierte Benutzerkonto-Modell
class Benutzerkonto(AbstractUser):
    LEHRPERSON = 'Lehrperson'
    ADMINISTRATOR = 'Administrator'
    ROLLE_CHOICES = [
        (LEHRPERSON, 'Lehrperson'),
        (ADMINISTRATOR, 'Administrator'),
    ]

    rolle = models.CharField(max_length=13, choices=ROLLE_CHOICES) # Feld mit den möglichen Rollen des Benutzers
    fehlversuche = models.PositiveIntegerField(default=0)  # Feld für die Anzahl der fehlgeschlagenen Anmeldeversuche
    fehlversuchszeitraum_beginn = models.DateTimeField(null=True, blank=True) # Feld für den Zeitpunkt des Beginns der fehlgeschlagenen Anmeldeversuche
    gesperrt_bis = models.DateTimeField(null=True, blank=True) # Feld für den Zeitpunkt, bis zu dem das Konto gesperrt ist

    REQUIRED_FIELDS = ['rolle']

    # innere Konfigurationsklasse für das Ausschließen von ungültigen Rollen
    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rolle__in=['Lehrperson', 'Administrator']),
                name='valid_rolle'
            ),
        ]


class Untersuchung(models.Model):
    '''
    Modell für eine Untersuchung.
    '''
    PRAESENZ = 'P'
    ONLINE = 'O'
    EINORDNUNG_CHOICES = [
        (PRAESENZ, 'Präsenz'),
        (ONLINE, 'Online'),
    ]

    studienname = models.CharField(max_length=100)  # Name der Untersuchung
    studienname_vergleich = models.TextField()  # interner Vergleichwert für die Untersuchung
    stundenwert = models.FloatField()  # VP-Stundenwert der Untersuchung
    einordnung = models.CharField(max_length=1, choices=EINORDNUNG_CHOICES)  # Einordnung der Untersuchung (Präsenz oder Online)
    lehrperson = models.CharField(max_length=100)  # Importierter Name der Lehrperson
    uploadzeitpunkt = models.DateTimeField(auto_now_add=True)  # Zeitpunkt des Uploads der Untersuchung

    # innere Konfigurationsklasse für die Definition von Einschränkungen und Bedingungen
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['studienname_vergleich'], # Eindeutigkeit der studienname_vergleich-Spalte
                name='eindeutiger_studienname_vergleich' # Name der Bedingung
                ),
            models.CheckConstraint(
                condition=models.Q(einordnung__in=['P', 'O']), # Bedingung für die Einordnung (nur P oder O erlaubt)
                name='gueltige_einordnung' # Name der Bedingung
            ),
        ]

class Teilnahme(models.Model):
    '''
    Modell für die Teilnahme an einer Untersuchung.
    '''

    untersuchung = models.ForeignKey(Untersuchung, on_delete=models.PROTECT)  # on_delete=PROTECT verhindert das Löschen einer Untersuchung, wenn noch Teilnahmen existieren
    matrikelnummer = models.CharField(max_length=7)  # Matrikelnummer der Teilnehmner:in

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['untersuchung', 'matrikelnummer'], # Eindeutigkeit der Kombination aus Untersuchung und Matrikelnummer
                name='eindeutige_teilnahme' # Name der Bedingung
            ),
        ]