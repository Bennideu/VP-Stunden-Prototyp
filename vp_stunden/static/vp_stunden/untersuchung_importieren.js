import { sendeFormular } from "./backend.js"; // Übermittelt Formulardaten und liest die JSON-Antwort.

// Uploadformular, Fehlerliste, Statusbereich und zugehörigen Button ermitteln.
const formular = document.getElementById("untersuchungsformular");
const fehlerbereich = document.getElementById("untersuchungsfehler");
const meldung = document.getElementById("untersuchungsmeldung");
const knopf = formular.querySelector('button[type="submit"]');

formular.addEventListener("submit", async function (ereignis) {
    // Die direkte Formularnavigation verhindern, da JavaScript die Anfrage übernimmt.
    ereignis.preventDefault();

    // Alte Fehler entfernen, damit nur Meldungen der aktuellen Anfrage erscheinen.
    fehlerbereich.replaceChildren();

    // Den Button während der Anfrage sperren und den laufenden Vorgang anzeigen.
    knopf.disabled = true;
    meldung.textContent = "Untersuchungsdatei wird geprüft und importiert.";

    try {
        // Datei samt CSRF-Prüfwert senden, Prüfung und Speicherung erfolgen im Backend.
        const ergebnis = await sendeFormular(formular);
        meldung.textContent = ergebnis.nachricht;

        // Vorhandene Fehlermeldungen als einzelne Listeneinträge anzeigen.
        if (ergebnis.fehlerliste) {
            for (const fehler of ergebnis.fehlerliste) {
                const eintrag = document.createElement("li");
                eintrag.textContent = fehler; // Den Fehler als reinen Text einsetzen.
                fehlerbereich.append(eintrag);
            }
        }

        // Die Dateiauswahl nur nach bestätigtem Import zurücksetzen.
        if (ergebnis.erfolg) {
            formular.reset();
        }
    } catch {
        // Fehler beim Senden oder Lesen der Antwort allgemein anzeigen.
        meldung.textContent =
            "Die Anfrage konnte nicht verarbeitet werden.";
    } finally {
        // Den Button unabhängig vom Ausgang der Anfrage wieder freigeben.
        knopf.disabled = false;
    }
});