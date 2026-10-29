import { sendeFormular } from "./backend.js"; // Übermittelt Formulardaten und liest die JSON-Antwort.
import { aktualisiereTeilnahmen } from "./teilnahmen_suchen.js";

// Suchformular, Ergebniszeilen sowie getrennte Such- und Korrekturmeldungen ermitteln.
const formular = document.getElementById("studienformular");
const meldung = document.getElementById("studienmeldung");
const tabellenzeilen = document.getElementById("studienzeilen");
const knopf = formular.querySelector('button[type="submit"]');
const korrekturmeldung = document.getElementById("korrekturmeldung");
const fehlerbereich = document.getElementById("korrekturfehler");

// Den Teilnahmesuchbutton während einer Inlinebearbeitung sperren können.
const teilnahmesuchknopf = document
    .getElementById("teilnahmeformular")
    .querySelector('button[type="submit"]');

let angezeigteSuche = null; // Formularkopie der zuletzt erfolgreich angezeigten Suche.
let bearbeiteteZeile = null; // Aktuell bearbeitete Tabellenzeile.
let speichert = false; // Speichervorgang einschließlich anschließender Aktualisierungen.
let loeschsperre = false; // Zusätzliche Sperre während eines Löschversuchs.

// Suchbutton und Bearbeiten-Buttons entsprechend dem aktuellen Sperrzustand setzen.
function aktualisiereBedienung() {
    const gesperrt = bearbeiteteZeile !== null || speichert || loeschsperre;
    knopf.disabled = gesperrt;

    for (const bearbeiten of tabellenzeilen.querySelectorAll(
        'button[data-aktion="bearbeiten"]'
    )) {
        bearbeiten.disabled = gesperrt;
    }
}

// Eine Ergebniszeile mit Untersuchungsangaben und einem Bearbeiten-Button aufbauen.
function zeigeUntersuchung(zeile, untersuchung) {
    zeile.replaceChildren();

    // Stunden deutsch und den Uploadzeitpunkt in Berliner Ortszeit darstellen.
    const werte = [
        untersuchung.studienname,
        untersuchung.stundenwert.toLocaleString("de-DE"),
        untersuchung.einordnung,
        untersuchung.lehrperson,
        new Date(untersuchung.uploadzeitpunkt).toLocaleString(
            "de-DE",
            { timeZone: "Europe/Berlin" }
        ),
    ];

    // Die Werte als reine Textinhalte in Tabellenzellen einsetzen.
    for (const wert of werte) {
        const zelle = document.createElement("td");
        zelle.textContent = wert;
        zeile.append(zelle);
    }

    // Die Aktionszelle anlegen und den aktuellen Sperrzustand übernehmen.
    const aktionszelle = document.createElement("td");
    const bearbeiten = document.createElement("button");
    bearbeiten.type = "button";
    bearbeiten.textContent = "Bearbeiten";
    bearbeiten.dataset.aktion = "bearbeiten"; // Kennung für die gemeinsame Bediensperre.
    bearbeiten.disabled = bearbeiteteZeile !== null || speichert || loeschsperre;

    bearbeiten.addEventListener("click", function () {
        starteBearbeitung(zeile, untersuchung);
    });

    aktionszelle.append(bearbeiten);
    zeile.append(aktionszelle);
}

// Genau eine Ergebniszeile in den Inlineeditor umwandeln.
function starteBearbeitung(zeile, untersuchung) {
    // Keine zweite Bearbeitung oder Bearbeitung bei gesperrter Untersuchungssuche beginnen.
    if (bearbeiteteZeile !== null || speichert || knopf.disabled) {
        return;
    }

    // Nicht parallel zu einer laufenden Aktion der Teilnahmeanzeige bearbeiten.
    if (teilnahmesuchknopf.disabled) {
        korrekturmeldung.textContent =
            "Bitte die laufende Anfrage abwarten.";
        return;
    }

    // Die Referenz auf die zur Ergebnisanzeige gehörende Suchkopie festhalten.
    const bisherigeSuche = angezeigteSuche;

    // Die Bearbeitung markieren, Suchen sperren und den bisherigen Zeileninhalt entfernen.
    bearbeiteteZeile = zeile;
    teilnahmesuchknopf.disabled = true;
    korrekturmeldung.textContent = "";
    fehlerbereich.replaceChildren();
    aktualisiereBedienung();
    zeile.replaceChildren();

    // Das Korrekturformular für den vorhandenen Backend-Endpunkt anlegen.
    const zeilenformular = document.createElement("form");
    zeilenformular.id = "korrekturformular";
    zeilenformular.method = "post";
    zeilenformular.action = "/untersuchung_korrigieren/";

    // Genau die vier gemeinsamen Untersuchungsangaben mit ihren aktuellen Werten bereitstellen.
    const felder = [
        ["studienname", "Studienname", untersuchung.studienname],
        ["stundenwert", "VP-Stunden", untersuchung.stundenwert],
        ["einordnung", "P/O", untersuchung.einordnung],
        ["lehrperson", "Verantwortliche Lehrperson", untersuchung.lehrperson],
    ];

    // Für jede Angabe eine Tabellenzelle mit dem passenden Eingabeelement erzeugen.
    for (const [name, beschriftung, wert] of felder) {
        const zelle = document.createElement("td");
        let eingabe;

        if (name === "einordnung") {
            // Für die Einordnung ausschließlich die Auswahlwerte P und O anbieten.
            eingabe = document.createElement("select");

            for (const [optionswert, optionstext] of [
                ["P", "Präsenz (P)"],
                ["O", "Online (O)"],
            ]) {
                const option = document.createElement("option");
                option.value = optionswert;
                option.textContent = optionstext;
                eingabe.append(option);
            }
        } else {
            // Stunden als Zahlenfeld, Studienname und Lehrperson als Textfelder darstellen.
            eingabe = document.createElement("input");
            eingabe.type = name === "stundenwert" ? "number" : "text";

            if (name === "stundenwert") {
                // Positive Werte in Schritten von 0,5 für die Browserprüfung vorgeben.
                eingabe.min = "0.5";
                eingabe.step = "0.5";
            }
        }

        // Den Rohwert ohne deutsche Zahlenformatierung einsetzen und das Pflichtfeld benennen.
        eingabe.name = name;
        eingabe.value = String(wert);
        eingabe.required = true;
        eingabe.setAttribute("aria-label", beschriftung);

        // Die außerhalb des Formulars liegende Eingabe über dessen ID zuordnen.
        eingabe.setAttribute("form", zeilenformular.id);

        zelle.append(eingabe);
        zeile.append(zelle);
    }

    // Den Uploadzeitpunkt unverändert als Text anzeigen und nicht zur Bearbeitung anbieten.
    const zeitZelle = document.createElement("td");
    zeitZelle.textContent = new Date(untersuchung.uploadzeitpunkt)
        .toLocaleString("de-DE", { timeZone: "Europe/Berlin" });
    zeile.append(zeitZelle);

    // Das vorhandene CSRF-Feld aus dem Suchformular für die Korrektur kopieren.
    const csrfFeld = formular
        .querySelector('[name="csrfmiddlewaretoken"]')
        .cloneNode(true);

    // Die interne Untersuchungskennung als verborgenes Zuordnungsfeld übertragen.
    const idFeld = document.createElement("input");
    idFeld.type = "hidden";
    idFeld.name = "untersuchung_id";
    idFeld.value = untersuchung.untersuchung_id;

    // Speichern als Formularübermittlung und Abbrechen als eigenständige Aktion anlegen.
    const speichern = document.createElement("button");
    speichern.type = "submit";
    speichern.textContent = "Speichern";

    const abbrechen = document.createElement("button");
    abbrechen.type = "button";
    abbrechen.textContent = "Abbrechen";

    // Abbrechen stellt den zuletzt geladenen Untersuchungsstand ohne Backendanfrage dar.
    abbrechen.addEventListener("click", function () {
        if (speichert) {
            return;
        }

        bearbeiteteZeile = null;
        zeigeUntersuchung(zeile, untersuchung);
        korrekturmeldung.textContent = "Bearbeitung abgebrochen.";
        fehlerbereich.replaceChildren();
        teilnahmesuchknopf.disabled = false;
        aktualisiereBedienung();
        zeile.querySelector("button").focus(); // Fokus zum Bearbeiten-Button zurückführen.
    });

    zeilenformular.addEventListener("submit", async function (ereignis) {
        // Die Korrektur über JavaScript statt durch direkte Formularnavigation senden.
        ereignis.preventDefault();

        // Einen bereits laufenden Speichervorgang nicht erneut auslösen.
        if (speichert) {
            return;
        }

        speichert = true;
        fehlerbereich.replaceChildren();
        korrekturmeldung.textContent = "Untersuchung wird gespeichert.";

        // Alle zugeordneten Felder und Buttons als feste Liste für die Sperrung erfassen.
        const bedienelemente = Array.from(zeilenformular.elements);
        let gespeichert = false; // Erst die erfolgreiche Backendantwort bestätigt die Speicherung.

        try {
            // FormData vor der Deaktivierung erzeugen, damit Eingaben und CSRF-Wert enthalten sind.
            const anfrage = sendeFormular(zeilenformular);

            for (const element of bedienelemente) {
                element.disabled = true;
            }

            const ergebnis = await anfrage;
            korrekturmeldung.textContent = ergebnis.nachricht;

            // Vorhandene Korrekturfehler als Text anzeigen und eine fehlende Fehlerliste zulassen.
            for (const fehlertext of ergebnis.fehlerliste ?? []) {
                const eintrag = document.createElement("li");
                eintrag.textContent = fehlertext;
                fehlerbereich.append(eintrag);
            }

            // Bei Abweisung die Eingabefelder und ihre Werte für eine weitere Korrektur erhalten.
            if (!ergebnis.erfolg) {
                return;
            }

            gespeichert = true;

            // Beide Anzeigen mit den zuletzt abgeschickten Suchwerten aktualisieren.
            // Eine Namensänderung kann die Untersuchung aus der bisherigen Trefferliste entfernen.
            await sucheUntersuchungen(bisherigeSuche);
            await aktualisiereTeilnahmen();
        } catch {
            // Ohne Bestätigung bleibt offen, ob die Speicherung ausgeführt wurde.
            // Nach bestätigtem Erfolg betrifft ein Fehler die anschließende Aktualisierung.
            korrekturmeldung.textContent = gespeichert
                ? "Untersuchung gespeichert. Die Anzeige konnte nicht vollständig aktualisiert werden."
                : "Die Speicherung konnte nicht bestätigt werden.";
        } finally {
            // Die erfassten Bedienelemente nach dem Speicherversuch wieder freigeben.
            for (const element of bedienelemente) {
                element.disabled = false;
            }

            speichert = false;

            // Den Bearbeitungszustand nur nach bestätigter Speicherung aufheben.
            if (gespeichert) {
                bearbeiteteZeile = null;
                teilnahmesuchknopf.disabled = false;
            }

            aktualisiereBedienung();
        }
    });

    // CSRF-Feld, Untersuchungskennung und Buttons im Formular der Aktionszelle unterbringen.
    zeilenformular.append(csrfFeld, idFeld, speichern, abbrechen);

    const aktionszelle = document.createElement("td");
    aktionszelle.append(zeilenformular);
    zeile.append(aktionszelle);
    zeile.querySelector("input").focus(); // Fokus auf das erste Eingabefeld setzen.
}

// Untersuchungen für die übergebenen Suchwerte laden und die Ergebnisliste ersetzen.
async function sucheUntersuchungen(suchformular) {
    angezeigteSuche = null;
    tabellenzeilen.replaceChildren();
    knopf.disabled = true;
    meldung.textContent = "Untersuchungen werden gesucht.";

    try {
        const ergebnis = await sendeFormular(suchformular);
        meldung.textContent = ergebnis.nachricht;

        if (ergebnis.erfolg) {
            // Untersuchungen in der vom Backend gelieferten Reihenfolge als Zeilen darstellen.
            for (const untersuchung of ergebnis.untersuchungen) {
                const zeile = document.createElement("tr");
                zeigeUntersuchung(zeile, untersuchung);
                tabellenzeilen.append(zeile);
            }

            // Nur eine erfolgreich dargestellte Suche für spätere Aktualisierungen merken.
            angezeigteSuche = suchformular;
        }
    } catch {
        // Auch teilweise erzeugte Ergebniszeilen bei einem Fehler entfernen.
        tabellenzeilen.replaceChildren();
        meldung.textContent = "Die Anfrage konnte nicht verarbeitet werden.";
    } finally {
        // Weiterhin aktive Bearbeitungs-, Speicher- oder Löschsperren berücksichtigen.
        aktualisiereBedienung();
    }
}

formular.addEventListener("submit", async function (ereignis) {
    // Die direkte Formularnavigation verhindern, da JavaScript die Anfrage übernimmt.
    ereignis.preventDefault();

    // Während einer Bearbeitung, Speicherung oder sonstigen Sperre keine neue Suche beginnen.
    if (knopf.disabled || bearbeiteteZeile !== null || speichert) {
        return;
    }

    // Bei einer manuellen Suche alte Korrekturmeldungen entfernen, bei Aktualisierungen erhalten.
    korrekturmeldung.textContent = "";
    fehlerbereich.replaceChildren();

    // Das Formular samt Feldern kopieren, damit spätere Eingaben diese Suche nicht verändern.
    await sucheUntersuchungen(formular.cloneNode(true));
});

// Anderen Modulen die Aktualisierung einer bereits angezeigten Suche ermöglichen.
export async function aktualisiereUntersuchungen() {
    const bisherigeSuche = angezeigteSuche;

    if (bisherigeSuche !== null) {
        await sucheUntersuchungen(bisherigeSuche);
    }
}

// Dem Löschmodul das Setzen und Aufheben seiner zusätzlichen Bediensperre ermöglichen.
export function setzeLoeschsperre(gesperrt) {
    loeschsperre = gesperrt;
    aktualisiereBedienung();
}