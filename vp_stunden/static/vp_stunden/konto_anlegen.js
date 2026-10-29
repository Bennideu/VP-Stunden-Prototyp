import { sendeFormular } from "./backend.js"; // Übermittelt Formulardaten und liest die JSON-Antwort.

// Formular, Fehlerliste, Statusbereich und zugehörigen Button ermitteln.
const formular = document.getElementById("kontoformular");
const fehlerbereich = document.getElementById("kontofehler");
const meldung = document.getElementById("kontomeldung");
const knopf = formular.querySelector('button[type="submit"]');

formular.addEventListener("submit", async function (ereignis) {
    // Die direkte Formularnavigation verhindern, da JavaScript die Anfrage übernimmt.
    ereignis.preventDefault();

    // Alte Fehler entfernen, damit nur Meldungen der aktuellen Anfrage erscheinen.
    fehlerbereich.replaceChildren();

    // Den Button während der Anfrage sperren und den laufenden Vorgang anzeigen.
    knopf.disabled = true;
    meldung.textContent = "Benutzerkonto wird angelegt.";

    try {
        // Kontenangaben samt CSRF-Prüfwert senden und die Backendantwort abwarten.
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

        // Nur nach bestätigtem Erfolg zurücksetzen, bei Abweisung Eingaben erhalten.
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