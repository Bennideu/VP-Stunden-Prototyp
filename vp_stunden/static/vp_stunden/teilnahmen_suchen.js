import { sendeFormular } from "./backend.js"; // Übermittelt Formulardaten und liest die JSON-Antwort.

// Suchformular, Ergebnisbereich, Stundenanzeige und Suchbutton ermitteln.
const formular = document.getElementById("teilnahmeformular");
const meldung = document.getElementById("teilnahmemeldung");
const tabellenzeilen = document.getElementById("teilnahmezeilen");
const stundenbereich = document.getElementById("stundenberechnung");
const knopf = formular.querySelector('button[type="submit"]');

// Reportformular samt verborgener Matrikelnummer, Statusbereich und Button ermitteln.
const reportformular = document.getElementById("reportformular");
const reportnummer = document.getElementById("report_matrikelnummer");
const reportmeldung = document.getElementById("reportmeldung");
const reportknopf = reportformular.querySelector('button[type="submit"]');

// Löschformular, zugehörige Matrikelnummer, Ablagebestätigung und Rückmeldungen ermitteln.
const loeschformular = document.getElementById("loeschformular");
const loeschnummer = document.getElementById("loesch_matrikelnummer");
const ablage = document.getElementById("loesch_ablage_bestaetigt");
const loeschknopf = loeschformular.querySelector('button[type="submit"]');
const loeschmeldung = document.getElementById("loeschmeldung");
const loeschfehler = document.getElementById("loeschfehler");

let angezeigteSuche = null; // Formularkopie der zuletzt erfolgreich angezeigten Suche.
let reportUrl = null; // Temporäre Browseradresse des zuletzt geladenen PDF-Inhalts.

// Die gespeicherte Blob-URL freigeben und ihre Zuordnung entfernen.
function gibReportUrlFrei() {
    if (reportUrl !== null) {
        URL.revokeObjectURL(reportUrl);
        reportUrl = null;
    }
}

// Teilnahmen und Berechnung für die übergebenen Suchwerte laden und anzeigen.
async function sucheTeilnahmen(suchformular) {
    angezeigteSuche = null;

    // Vorherige Ergebnisse, Berechnung sowie Report- und Löschzuordnung zurücksetzen.
    tabellenzeilen.replaceChildren();
    stundenbereich.textContent = "";
    reportnummer.value = "";
    reportmeldung.textContent = "";
    reportknopf.disabled = true;
    loeschnummer.value = "";
    ablage.checked = false;
    loeschknopf.disabled = true;

    // Den Suchbutton während der Anfrage sperren und den laufenden Vorgang anzeigen.
    knopf.disabled = true;
    meldung.textContent = "Teilnahmen werden gesucht.";

    try {
        const ergebnis = await sendeFormular(suchformular);
        meldung.textContent = ergebnis.nachricht;

        if (ergebnis.erfolg) {
            // Für jede Teilnahme eine Zeile in der vom Backend gelieferten Reihenfolge anlegen.
            for (const teilnahme of ergebnis.teilnahmen) {
                const zeile = document.createElement("tr");

                // Spaltenwerte vorbereiten, Stunden deutsch und Zeiten für Berlin formatieren.
                const werte = [
                    teilnahme.matrikelnummer,
                    teilnahme.studienname,
                    teilnahme.stundenwert.toLocaleString("de-DE"),
                    teilnahme.einordnung,
                    teilnahme.lehrperson,
                    new Date(teilnahme.uploadzeitpunkt).toLocaleString(
                        "de-DE",
                        { timeZone: "Europe/Berlin" }
                    ),
                ];

                // Die Werte als reine Textinhalte in einzelne Tabellenzellen einsetzen.
                for (const wert of werte) {
                    const zelle = document.createElement("td");
                    zelle.textContent = wert;
                    zeile.append(zelle);
                }

                tabellenzeilen.append(zeile);
            }

            // Summen und Erfüllungsstatus aus der Backendberechnung übernehmen.
            const berechnung = ergebnis.berechnung;
            const status = berechnung.erfuellt ? "erfüllt" : "nicht erfüllt";

            stundenbereich.textContent =
                `Präsenzstunden: ${berechnung.praesenzstunden.toLocaleString("de-DE")} · ` +
                `Onlinestunden: ${berechnung.onlinestunden.toLocaleString("de-DE")} · ` +
                `Gesamtstunden: ${berechnung.gesamtstunden.toLocaleString("de-DE")} · ` +
                `Status: ${status}`;

            // Die erfolgreich dargestellte Formularkopie für spätere Aktualisierungen merken.
            angezeigteSuche = suchformular;

            // Report und Löschung an die angezeigte Nummer und ihren Erfüllungsstatus binden.
            reportnummer.value = new FormData(suchformular)
                .get("matrikelnummer");
            reportknopf.disabled = !berechnung.erfuellt;
            loeschnummer.value = reportnummer.value;
            loeschknopf.disabled = !berechnung.erfuellt;
        }
    } catch {
        // Auch teilweise erzeugte Ergebnisse und zugehörige Aktionszuordnungen entfernen.
        angezeigteSuche = null;
        tabellenzeilen.replaceChildren();
        stundenbereich.textContent = "";
        reportnummer.value = "";
        reportknopf.disabled = true;
        loeschnummer.value = "";
        ablage.checked = false;
        loeschknopf.disabled = true;
        meldung.textContent = "Die Anfrage konnte nicht verarbeitet werden.";
    } finally {
        // Den Suchbutton unabhängig vom Ausgang der Anfrage wieder freigeben.
        knopf.disabled = false;
    }
}

formular.addEventListener("submit", async function (ereignis) {
    // Die direkte Formularnavigation verhindern, da JavaScript die Anfrage übernimmt.
    ereignis.preventDefault();

    // Bei gesperrter Bedienung keine zusätzliche Suche beginnen.
    if (knopf.disabled) {
        return;
    }

    // Löschmeldungen nur bei einer neuen manuellen Suche entfernen.
    loeschmeldung.textContent = "";
    loeschfehler.replaceChildren();

    // Das Formular samt Feldern kopieren, damit spätere Eingaben diese Suche nicht verändern.
    await sucheTeilnahmen(formular.cloneNode(true));
});

// Anderen Modulen die Aktualisierung mit den zuletzt abgeschickten Suchwerten ermöglichen.
export async function aktualisiereTeilnahmen() {
    if (angezeigteSuche !== null) {
        await sucheTeilnahmen(angezeigteSuche);
    }
}

reportformular.addEventListener("submit", async function (ereignis) {
    // Den PDF-Abruf über JavaScript steuern und die direkte Formularnavigation verhindern.
    ereignis.preventDefault();

    // Nur bei freigegebenem Reportbutton und vorhandener Suchanzeige einen Report anfordern.
    if (reportknopf.disabled || angezeigteSuche === null) {
        return;
    }

    // Eine laufende Anfrage oder Bearbeitung vor dem Reportabruf abschließen lassen.
    if (knopf.disabled) {
        reportmeldung.textContent =
            "Bitte die laufende Suche oder Bearbeitung abschließen.";
        return;
    }

    // Für Anfrage und Dateiname dieselbe angezeigte Matrikelnummer festhalten.
    const angefragteNummer = reportnummer.value;

    // Die Teilnahmesuche und weitere Reportabrufe während der Anfrage sperren.
    knopf.disabled = true;
    reportknopf.disabled = true;
    reportmeldung.textContent = "PDF-Report wird erzeugt.";

    try {
        // Direkt abrufen, da dieser Endpunkt PDF-Inhalt oder eine JSON-Fehlermeldung liefert.
        const antwort = await fetch(reportformular.getAttribute("action"), {
            method: "POST",
            body: new FormData(reportformular),
            mode: "same-origin",
        });

        // Bei einer HTTP-Abweisung die JSON-Meldung auswerten und keinen Download beginnen.
        if (!antwort.ok) {
            const ergebnis = await antwort.json();
            reportmeldung.textContent = ergebnis.nachricht;
            return;
        }

        // Den gemeldeten Medientyp prüfen und mögliche Zusatzparameter ignorieren.
        const inhaltstyp = antwort.headers.get("Content-Type") ?? "";

        if (inhaltstyp.split(";")[0].trim() !== "application/pdf") {
            throw new Error("Keine PDF-Antwort erhalten.");
        }

        // Den PDF-Inhalt als Blob laden und eine temporäre Browseradresse dafür erzeugen.
        const pdf = await antwort.blob();
        const neueUrl = URL.createObjectURL(pdf);

        // Die vorherige Blob-URL freigeben und nur die neue Downloadadresse behalten.
        gibReportUrlFrei();
        reportUrl = neueUrl;

        // Einen unsichtbaren Downloadlink mit der angefragten Matrikelnummer im Dateinamen anlegen.
        const downloadlink = document.createElement("a");
        downloadlink.href = reportUrl;
        downloadlink.download = `vp_stunden_${angefragteNummer}.pdf`;
        downloadlink.hidden = true;
        document.body.append(downloadlink);

        // Den Download anstoßen und den Hilfslink auch bei einem Fehler wieder entfernen.
        try {
            downloadlink.click();
        } finally {
            downloadlink.remove();
        }

        // Der Downloadanstoß bestätigt noch keine abgeschlossene externe Speicherung.
        reportmeldung.textContent = "PDF-Download angestoßen.";
    } catch {
        // Fehler beim PDF-Abruf oder Download melden und die Suchergebnisse erhalten.
        reportmeldung.textContent =
            "Der PDF-Download konnte nicht angestoßen werden.";
    } finally {
        // Suche freigeben und den Reportbutton nur bei unverändertem Suchkontext aktivieren.
        knopf.disabled = false;
        reportknopf.disabled =
            angezeigteSuche === null ||
            reportnummer.value !== angefragteNummer;
    }
});

// Beim Verlassen der Seite die gespeicherte Blob-URL freigeben.
window.addEventListener("pagehide", gibReportUrlFrei);