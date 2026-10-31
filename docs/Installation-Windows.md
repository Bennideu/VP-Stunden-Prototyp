# Installation unter Windows 10/11

Für die Einrichtung wird eine Internetverbindung benötigt. Die Befehle werden in PowerShell ausgeführt.

## 1. Python installieren

Den **Python Install Manager** von [python.org](https://www.python.org/downloads/) herunterladen, die heruntergeladene Installationsdatei öffnen und installieren. Danach ein neues PowerShell-Fenster öffnen und ausführen:

```powershell
pymanager install 3.14
```

`pymanager` ist die Python-Installationsverwaltung. `install 3.14` installiert eine Python-Version der Reihe 3.14.

## 2. Projekt herunterladen

Im [Repository](https://github.com/Bennideu/VP-Stunden-Prototyp) **Code → Download ZIP** wählen und die ZIP-Datei über **Alle extrahieren** vollständig entpacken. Im Explorer den entpackten Ordner öffnen, der `manage.py` und `installieren.py` enthält. In dessen Adressleiste `powershell` eingeben und die Eingabetaste drücken. PowerShell öffnet sich in diesem Projektordner.

## 3. Prototyp einrichten

Im Projektordner ausführen:

```powershell
py -3.14 installieren.py
```

`py` startet Python, `-3.14` wählt die benötigte Versionsreihe. `installieren.py` richtet die Projektumgebung, benötigten Pakete, lokale Konfiguration und Datenbank ein. pip wird dabei innerhalb der Projektumgebung eingerichtet.

Falls noch kein aktives Administrationskonto besteht, einen Benutzernamen und zweimal dasselbe Passwort mit mindestens 15 Zeichen eingeben. Während der Passworteingabe erscheinen keine Zeichen.

Erfolgskontrolle: Am Ende erscheint `Die lokale Einrichtung ist abgeschlossen.`. Ein bereits vorhandener Schlüssel, Datenbestand und vorhandene Konten werden weiterverwendet.

## 4. Anwendung starten und beenden

Bei jedem Start im Projektordner ausführen:

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

`.\.venv\Scripts\python.exe` verwendet die Projektumgebung im aktuellen Ordner. `manage.py` führt den Django-Projektbefehl `runserver` aus. `127.0.0.1:8000` beschränkt den Entwicklungsserver auf diesen Rechner und den Port 8000.

Das Terminal geöffnet lassen. Im Browser [http://127.0.0.1:8000](http://127.0.0.1:8000) öffnen. Die Anmeldeseite muss erscheinen. Mit dem eingerichteten Administrationskonto anmelden.

Zum Beenden in PowerShell **Strg+C** drücken.
[Zur README](../README.md)