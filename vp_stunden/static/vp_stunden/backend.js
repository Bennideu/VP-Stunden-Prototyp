export async function sendeFormular(formular) {
    // Formularfelder einschließlich des CSRF-Prüfwerts übertragen.
    const antwort = await fetch(formular.getAttribute("action"), {
        method: "POST",
        body: new FormData(formular),
        mode: "same-origin",
    });

    // Auch Fehlerantworten wie HTTP 400 enthalten eine JSON-Meldung.
    return await antwort.json();
}