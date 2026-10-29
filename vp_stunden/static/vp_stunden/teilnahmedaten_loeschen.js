import { sendeFormular } from "./backend.js"; // Übermittelt Formulardaten und liest die JSON-Antwort.
import { aktualisiereTeilnahmen } from "./teilnahmen_suchen.js";
import {
    aktualisiereUntersuchungen,
    setzeLoeschsperre,
} from "./untersuchungen_suchen.js";

// Löschformular, Rückmeldungen, Ablagebestätigung und Löschbutton ermitteln.
const formular = document.getElementById("loeschformular");
const meldung = document.getElementById("loeschmeldung");
const fehlerbereich = document.getElementById("loeschfehler");
const ablage = document.getElementById("loesch_ablage_bestaetigt");
const knopf = formular.querySelector('button[type="submit"]');

// Zugehörige Such- und Reportbuttons für die gemeinsame Sperrung ermitteln.
const teilnahmesuchknopf = document
    .getElementById("teilnahmeformular")
    .querySelector('button[type="submit"]');
const studiensuchknopf = document
    .getElementById("studienformular")
    .querySelector('button[type="submit"]');
const reportknopf = document
    .getElementById("reportformular")
    .querySelector('button[type="submit"]');

formular.addEventListener("submit", async function (ereignis) {
    // Die direkte Formularnavigation verhindern, da JavaScript die Anfrage übernimmt.
    ereignis.preventDefault();

    // Bei gesperrtem Löschbutton keine weitere Anfrage beginnen.
    if (knopf.disabled) {
        return;
    }

    // Laufende Suchen, Reporterzeugung oder Inlinebearbeitung zuerst abschließen lassen.
    if (teilnahmesuchknopf.disabled || studiensuchknopf.disabled) {
        meldung.textContent =
            "Bitte die laufende Suche oder Bearbeitung abschließen.";
        return;
    }

    // Die gesetzte Checkbox als Bestätigung der externen Reportablage prüfen.
    if (!ablage.checked) {
        meldung.textContent = "Bitte die externe Reportablage bestätigen.";
        return;
    }

    const reportWarGesperrt = reportknopf.disabled; // Bisherigen Reportzustand merken.
    let geloescht = false; // Erst eine erfolgreiche Backendantwort bestätigt die Löschung.

    // Suchen, Inlinebearbeitung, Report und erneutes Löschen während des Vorgangs sperren.
    teilnahmesuchknopf.disabled = true;
    setzeLoeschsperre(true);
    reportknopf.disabled = true;
    knopf.disabled = true;
    fehlerbereich.replaceChildren();
    meldung.textContent = "Teilnahmedaten werden gelöscht.";

    try {
        // FormData vor dem Sperren der Checkbox erzeugen, da deaktivierte Felder fehlen würden.
        const anfrage = sendeFormular(formular);
        ablage.disabled = true;

        const ergebnis = await anfrage;
        meldung.textContent = ergebnis.nachricht;

        // Vorhandene Fehler einzeln anzeigen; eine fehlende Fehlerliste durch [] ersetzen.
        for (const fehlertext of ergebnis.fehlerliste ?? []) {
            const eintrag = document.createElement("li");
            eintrag.textContent = fehlertext; // Den Fehler als reinen Text einsetzen.
            fehlerbereich.append(eintrag);
        }

        // Bei einer Abweisung die bisherigen Suchanzeigen erhalten.
        if (!ergebnis.erfolg) {
            return;
        }

        geloescht = true;

        // Zuerst Untersuchungen, dann Teilnahmen mit den gespeicherten Suchwerten aktualisieren.
        await aktualisiereUntersuchungen();
        await aktualisiereTeilnahmen();
    } catch {
        // Ohne bestätigten Erfolg bleibt offen, ob die Löschung ausgeführt wurde.
        // Nach bestätigtem Erfolg betrifft ein Fehler die anschließende Aktualisierung.
        meldung.textContent = geloescht
            ? "Löschung erfolgreich. Die Anzeige konnte nicht vollständig aktualisiert werden."
            : "Die Löschung konnte nicht bestätigt werden. Bitte die Matrikelnummer erneut suchen.";
    } finally {
        // Die Checkbox nach Abschluss des Löschversuchs wieder bedienbar machen.
        ablage.disabled = false;

        // Nach Erfolg gelten die Buttonzustände aus der erneuten Teilnahmesuche.
        // Andernfalls den alten Reportzustand und den Löschbutton wiederherstellen.
        if (!geloescht) {
            reportknopf.disabled = reportWarGesperrt;
            knopf.disabled = false;
        }

        // Die Suchfunktionen nach Abschluss des gesamten Löschversuchs wieder freigeben.
        teilnahmesuchknopf.disabled = false;
        setzeLoeschsperre(false);
    }
});