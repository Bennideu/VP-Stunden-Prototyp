"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

import vp_stunden
from vp_stunden.views import melde_an_view, melde_ab_view, aendere_passwort_view, lege_konto_an_view, setze_passwort_zurueck_view

urlpatterns = [
    path('admin/', admin.site.urls),

    # Anfragen an anmelden/ an die Anmelde-View weiterleiten
    path('anmelden/', melde_an_view, name='melde_an'),
    # Anfragen an abmelden/ an die Abmelde-View weiterleiten
    path('abmelden/', melde_ab_view, name='melde_ab'),
    # Anfragen an passwort_aendern/ an die Passwortänderungs-View weiterleiten
    path('passwort_aendern/', aendere_passwort_view, name='aendere_passwort'),
    # Anfragen an konto_anlegen/ an die Kontoerstellungs-View weiterleiten
    path('konto_anlegen/', lege_konto_an_view, name='lege_konto_an'),
    # Anfragen an passwort_zuruecksetzen/ an die Passwort-Zurücksetzungs-View weiterleiten
    path('passwort_zuruecksetzen/', setze_passwort_zurueck_view, name='setze_passwort_zurueck'),
    # Löschanfragen an die View für Teilnahmedaten weiterleiten
    path ('teilnahmedaten_loeschen/', vp_stunden.views.loesche_teilnahmedaten_view, name='loesche_teilnahmedaten'),
    # Suchanfragen nach Matrikelnummer an die Teilnahmesuche-View weiterleiten
    path('teilnahmen_suchen/', vp_stunden.views.suche_teilnahmen_view, name='suche_teilnahmen'),
    # Suchanfragen nach Studienname an die Untersuchungssuche-View weiterleiten
    path('untersuchungen_suchen/', vp_stunden.views.suche_untersuchungen_view, name='suche_untersuchungen'),
    # Administrative Untersuchungskorrekturen an die zuständige View weiterleiten.
    path('untersuchung_korrigieren/', vp_stunden.views.korrigiere_untersuchung_view, name='korrigiere_untersuchung'),
    # Administrative Reportanfragen an die PDF-Reportview weiterleiten.
    path('report_erzeugen/', vp_stunden.views.erzeuge_report_view, name='erzeuge_report'),
        # Reguläre Uploadanfragen an die Import-View weiterleiten.
    path('untersuchung_importieren/', vp_stunden.views.importiere_untersuchung_view, name='importiere_untersuchung',),
        # Administrative Übergangsimporte an die zuständige View weiterleiten.
    path('uebergangsdatei_importieren/', vp_stunden.views.importiere_uebergangsdatei_view, name='importiere_uebergangsdatei',),
]
