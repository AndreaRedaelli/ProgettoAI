"""Strumenti sui file, confinati nell'area di lavoro."""

from pathlib import Path

from .base import ErroreStrumento, Strumento

MAX_BYTE_FILE = 100_000
MAX_RISULTATI_RICERCA = 50


def risolvi(area: Path, percorso: str) -> Path:
    """Trasforma un percorso scritto dal modello in un percorso sicuro.

    È il cuore del confinamento. `resolve()` elimina i ".." e segue i
    collegamenti: solo dopo confrontiamo il risultato con l'area. Controllare
    il testo ("contiene ..?") non basterebbe.
    """
    radice = area.resolve()
    destinazione = (radice / percorso).resolve()
    if destinazione != radice and radice not in destinazione.parents:
        raise ErroreStrumento("Percorso fuori dall'area di lavoro: rifiutato.")
    return destinazione


def crea_strumenti_file(area: Path) -> list[Strumento]:
    """Gli strumenti sui file, legati a una specifica area di lavoro."""

    def relativo(percorso: Path) -> str:
        return percorso.relative_to(area.resolve()).as_posix()

    def elenca_file(percorso: str = ".") -> str:
        cartella = risolvi(area, percorso)
        if not cartella.is_dir():
            raise ErroreStrumento(f"Non è una cartella: {percorso}")
        righe = [
            f"{voce.name}/" if voce.is_dir() else f"{voce.name}  ({voce.stat().st_size} byte)"
            for voce in sorted(cartella.iterdir())
        ]
        return "\n".join(righe) or "(cartella vuota)"

    def leggi_file(percorso: str) -> str:
        file = risolvi(area, percorso)
        if not file.is_file():
            raise ErroreStrumento(f"File non trovato: {percorso}")
        if file.stat().st_size > MAX_BYTE_FILE:
            raise ErroreStrumento(f"File troppo grande (oltre {MAX_BYTE_FILE} byte).")
        return file.read_text(encoding="utf-8", errors="replace")

    def cerca_testo(testo: str) -> str:
        trovati: list[str] = []
        for file in sorted(area.resolve().rglob("*")):
            if not file.is_file() or file.stat().st_size > MAX_BYTE_FILE:
                continue
            righe = file.read_text(encoding="utf-8", errors="replace").splitlines()
            for numero, riga in enumerate(righe, start=1):
                if testo.lower() in riga.lower():
                    trovati.append(f"{relativo(file)}:{numero}: {riga.strip()}")
                    if len(trovati) >= MAX_RISULTATI_RICERCA:
                        return "\n".join(trovati) + "\n[... altri risultati omessi ...]"
        return "\n".join(trovati) or "Nessun risultato."

    def scrivi_file(percorso: str, contenuto: str) -> str:
        file = risolvi(area, percorso)
        if file.is_dir():
            raise ErroreStrumento(f"È una cartella: {percorso}")
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(contenuto, encoding="utf-8")
        return f"Scritto {relativo(file)} ({len(contenuto)} caratteri)."

    def elimina_file(percorso: str) -> str:
        file = risolvi(area, percorso)
        if not file.is_file():
            raise ErroreStrumento(f"File non trovato: {percorso}")
        file.unlink()
        return f"Eliminato {percorso}."

    percorso_obbligatorio = {
        "type": "object",
        "properties": {
            "percorso": {"type": "string", "description": "Percorso relativo all'area di lavoro"}
        },
        "required": ["percorso"],
    }

    return [
        Strumento(
            "elenca_file",
            "Elenca file e cartelle dell'area di lavoro, o di una sua sottocartella.",
            {
                "type": "object",
                "properties": {
                    "percorso": {
                        "type": "string",
                        "description": "Sottocartella da elencare; ometti per la radice",
                    }
                },
            },
            elenca_file,
        ),
        Strumento("leggi_file", "Legge il contenuto di un file di testo.", percorso_obbligatorio, leggi_file),
        Strumento(
            "cerca_testo",
            "Cerca un testo in tutti i file dell'area di lavoro. Restituisce file, riga e contenuto.",
            {
                "type": "object",
                "properties": {"testo": {"type": "string", "description": "Testo da cercare"}},
                "required": ["testo"],
            },
            cerca_testo,
        ),
        Strumento(
            "scrivi_file",
            "Crea un file o ne sostituisce il contenuto. Richiede la conferma dell'utente.",
            {
                "type": "object",
                "properties": {
                    "percorso": {"type": "string", "description": "Percorso relativo all'area di lavoro"},
                    "contenuto": {"type": "string", "description": "Contenuto completo del file"},
                },
                "required": ["percorso", "contenuto"],
            },
            scrivi_file,
            permesso="conferma",
            anteprima=lambda percorso, contenuto: f"Scrivere {percorso}:\n{contenuto}",
        ),
        Strumento(
            "elimina_file",
            "Elimina un file. Richiede la conferma dell'utente.",
            percorso_obbligatorio,
            elimina_file,
            permesso="conferma",
            anteprima=lambda percorso: f"Eliminare {percorso}",
        ),
    ]
