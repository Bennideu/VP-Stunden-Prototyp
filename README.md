# VP-Stunden-Prototyp

Webprototyp zur digitalen Verwaltung von Versuchspersonenstunden, entwickelt im Rahmen einer Bachelorarbeit.

## Funktionen und Rollen

Beide Rollen können sich anmelden, abmelden und ihr eigenes Passwort ändern.

- **Lehrperson:** Teilnahmedaten einer Untersuchung über eine Excel-Datei hochladen.
- **Administrator:in:** zusätzlich Konten anlegen, Passwörter zurücksetzen, Übergangsdateien importieren, Daten suchen, Untersuchungsangaben korrigieren, Stundensummen und Erfüllungsstatus einsehen, PDF-Reports erzeugen und sämtliche Teilnahmen einer Matrikelnummer unter den vorgesehenen Voraussetzungen löschen.

## Installation

Voraussetzung sind Python 3.14.x und eine Internetverbindung für die Einrichtung. Die folgenden Anleitungen enthalten die Python-Installation und verwenden dasselbe Skript `installieren.py`:

- [Ubuntu 26.04](docs/Installation-Linux.md)
- [Windows 10/11](docs/Installation-Windows.md)

## Technik und Betrieb

Python mit Django, SQLite sowie HTML, CSS und JavaScript.

Die Anwendung läuft auf dem jeweiligen Rechner unter [http://127.0.0.1:8000](http://127.0.0.1:8000) mit Djangos Entwicklungsserver `runserver`. Browser, Backend und Datenbank befinden sich auf demselben Rechner. Dieser Aufbau dient der lokalen Prototypprüfung.

## Lokale Dateien

Der Installer erzeugt die Projektumgebung `.venv`, die lokale Konfiguration `config/local_settings.py` mit einem zufälligen `SECRET_KEY` und die Datenbank `db.sqlite3`, soweit diese noch fehlen. Das erste Administrationskonto wird interaktiv eingerichtet, falls kein aktives Administrationskonto besteht.

Diese lokalen Dateien und die Projektumgebung sind von Git ausgeschlossen. Ein erneuter Installeraufruf verwendet die vorhandene Konfiguration und Datenbank weiter.