"""Esecuzione di script Python: lo strumento più potente e il più rischioso.

ATTENZIONE: il confinamento dei percorsi vale per i nostri strumenti, non per
il codice eseguito. Uno script può leggere, scrivere e cancellare ovunque sul
computer. Le uniche barriere reali sono la conferma dell'utente, che vede il
codice prima che parta, e il tempo massimo. Un isolamento vero richiederebbe
una sandbox (un container o una macchina virtuale).
"""

import os
import subprocess
import sys
from pathlib import Path

from .base import ErroreStrumento, Strumento
from .file import risolvi


def crea_strumento_python(area: Path, tempo_massimo: int = 10) -> Strumento:
    def esegui_python(percorso: str) -> str:
        script = risolvi(area, percorso)
        if not script.is_file() or script.suffix != ".py":
            raise ErroreStrumento(f"Script Python non trovato: {percorso}")
        try:
            esito = subprocess.run(
                # -I: modalità isolata, ignora variabili d'ambiente e cartella utente.
                [sys.executable, "-I", str(script)],
                cwd=area.resolve(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=tempo_massimo,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
        except subprocess.TimeoutExpired:
            raise ErroreStrumento(f"Script interrotto: ha superato {tempo_massimo} secondi.") from None
        return f"Codice di uscita: {esito.returncode}\n--- output ---\n{esito.stdout}\n--- errori ---\n{esito.stderr}"

    def anteprima(percorso: str) -> str:
        try:
            codice = risolvi(area, percorso).read_text(encoding="utf-8", errors="replace")
        except (ErroreStrumento, OSError):
            codice = "(file non leggibile)"
        return f"Eseguire lo script {percorso}:\n{codice}"

    return Strumento(
        "esegui_python",
        "Esegue uno script Python che si trova nell'area di lavoro e ne restituisce l'output. "
        "Richiede la conferma dell'utente.",
        {
            "type": "object",
            "properties": {
                "percorso": {"type": "string", "description": "Percorso dello script .py"}
            },
            "required": ["percorso"],
        },
        esegui_python,
        permesso="conferma",
        anteprima=anteprima,
    )
