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

