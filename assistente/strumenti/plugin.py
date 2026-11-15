"""Plugin: strumenti aggiunti mettendo un file in una cartella.

Un plugin è un file Python che definisce una lista `STRUMENTI`. Per
aggiungere una capacità all'agente non si tocca il nucleo: si aggiunge un file.

ATTENZIONE: caricare un plugin significa ESEGUIRE il suo codice. La conferma
protegge dalle chiamate agli strumenti, non da ciò che il file fa mentre
viene caricato. Un plugin va letto prima di metterlo nella cartella.
"""

import importlib.util
from dataclasses import replace
from pathlib import Path

from .base import Registro, Strumento


def carica_plugin(registro: Registro, cartella: Path, fidati=()) -> list[str]:
    """Carica i plugin della cartella nel registro. Restituisce le note per l'utente."""
    note: list[str] = []
    if not cartella.is_dir():
        return note

    for file in sorted(cartella.glob("*.py")):
        nome = file.stem
        if nome.startswith("_"):
            continue

        try:
            specifica = importlib.util.spec_from_file_location(f"plugin_{nome}", file)
            modulo = importlib.util.module_from_spec(specifica)
            specifica.loader.exec_module(modulo)
            strumenti = list(modulo.STRUMENTI)
        except Exception as problema:  # un plugin rotto non deve fermare l'assistente
            note.append(f"Plugin '{nome}' non caricato: {type(problema).__name__}: {problema}")
            continue

        for strumento in strumenti:
            if not isinstance(strumento, Strumento):
                note.append(f"Plugin '{nome}': un elemento di STRUMENTI non è uno Strumento.")
                continue
            if strumento.nome in registro.strumenti:
                # Un plugin non può sostituire uno strumento esistente: altrimenti
                # potrebbe rimpiazzare `leggi_file` con una versione senza controlli.
                note.append(f"Plugin '{nome}': '{strumento.nome}' esiste già, ignorato.")
                continue
            if nome not in fidati:
                # Di un plugin non dichiarato fidato non ci fidiamo nemmeno del
                # permesso che si è dato da solo.
                strumento = replace(strumento, permesso="conferma")
            registro.aggiungi(strumento)

        note.append(f"Plugin '{nome}' caricato" + ("" if nome in fidati else " (non fidato: chiede sempre conferma)"))
    return note
