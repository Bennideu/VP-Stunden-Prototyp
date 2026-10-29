import { sendeFormular } from "./backend.js"; // Übermittelt Formulardaten und liest die JSON-Antwort.

// Formular, Statusbereich und zugehörigen Abmeldebutton ermitteln.
const formular = document.getElementById("abmeldeformular");
const meldung = document.getElementById("abmeldung");
const knopf = formular.querySelector('button[type="submit"]');

formular.addEventListener("submit", async function (ereignis) {
    // Die direkte Formularnavigation verhindern, da JavaScript die Anfrage übernimmt.
    ereignis.preventDefault();

    // Den Button während der Anfrage sperren und den laufenden Vorgang anzeigen.
    knopf.disabled = true;
    meldung.textContent = "Abmeldung wird ausgeführt.";

    try {
        // Formular samt CSRF-Prüfwert senden und die Backendantwort abwarten.
        const ergebnis = await sendeFormular(formular);
        meldung.textContent = ergebnis.nachricht;

        if (ergebnis.erfolg) {
            // Nach bestätigter Abmeldung die Seite mit der Anmeldeansicht neu laden.
            window.location.reload();
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