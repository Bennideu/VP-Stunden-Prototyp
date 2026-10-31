# Installation unter Ubuntu 26.04

Benötigt werden eine Internetverbindung und für die Python-Installation ein Konto mit Administrationsrechten (`sudo`).

## 1. Python installieren

Ein Terminal öffnen. Diese Befehle können in jedem Ordner ausgeführt werden:

```bash
sudo apt update
sudo apt install python3.14 python3.14-venv
```

`sudo` verwendet Administrationsrechte. `apt update` aktualisiert die Paketliste. `apt install` installiert Python 3.14. Rückfragen zur Installation bestätigen. Der Installer richtet den Paketmanager pip später innerhalb der Projektumgebung ein.

## 2. Projekt herunterladen

Im [Repository](https://github.com/Bennideu/VP-Stunden-Prototyp) **Code → Download ZIP** wählen und die ZIP-Datei vollständig entpacken. Im Dateimanager den entpackten Ordner öffnen, der `manage.py` und `installieren.py` enthält. Dort über das Kontextmenü ein Terminal öffnen.

## 3. Prototyp einrichten

Im Projektordner ausführen:

```bash
/usr/bin/python3.14 installieren.py
```

`/usr/bin/python3.14` startet das über Ubuntu installierte Python. `installieren.py` richtet die Projektumgebung, benötigten Pakete, lokale Konfiguration und Datenbank ein.

Falls noch kein aktives Administrationskonto besteht, einen Benutzernamen und zweimal dasselbe Passwort mit mindestens 15 Zeichen eingeben. Während der Passworteingabe erscheinen keine Zeichen.

Erfolgskontrolle: Am Ende erscheint `Die lokale Einrichtung ist abgeschlossen.`. Ein bereits vorhandener Schlüssel, Datenbestand und vorhandene Konten werden weiterverwendet.

## 4. Anwendung starten und beenden

Bei jedem Start im Projektordner ausführen:

```bash
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

`.venv/bin/python` verwendet die Projektumgebung. `manage.py` führt den Django-Projektbefehl `runserver` aus. `127.0.0.1:8000` beschränkt den Entwicklungsserver auf diesen Rechner und den Port 8000.

Das Terminal geöffnet lassen. Im Browser [http://127.0.0.1:8000](http://127.0.0.1:8000) öffnen. Die Anmeldeseite muss erscheinen. Mit dem eingerichteten Administrationskonto anmelden.

Zum Beenden im Terminal **Strg+C** drücken.

[Zur README](../README.md)