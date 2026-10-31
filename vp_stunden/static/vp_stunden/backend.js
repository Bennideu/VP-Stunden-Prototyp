// Formularversand und JSON-Auswertung für Aktions- und Suchmodule bündeln.
export async function sendeFormular(formular) {
    // Das action-Attribut enthält den vorhandenen relativen Backendpfad.
    const antwort = await fetch(formular.getAttribute("action"), {
        method: "POST",
        // Eingaben, ausgewählte Dateien und das vorhandene CSRF-Feld übernehmen.
        body: new FormData(formular),
        // Anfragen auf dieselbe Kombination aus Protokoll, Host und Port begrenzen.
        mode: "same-origin",
    });

    // Die erwartete JSON-Antwort auch bei einem HTTP-Fehlerstatus einlesen.
    // Fehler beim Senden oder Einlesen behandelt das aufrufende Modul.
    return await antwort.json();
}