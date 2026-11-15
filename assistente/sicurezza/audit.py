"""Log di audit: una riga per ogni evento, per poter ricostruire cosa è successo."""

import json
from datetime import datetime, timezone
from pathlib import Path


class Audit:
    """Scrive gli eventi in un file JSONL: un oggetto JSON per riga.

    Il formato a righe si legge anche con un file enorme o scritto a metà, e
    si filtra con strumenti semplici.
    """

    def __init__(self, percorso: str | Path) -> None:
        self.percorso = Path(percorso)

    def registra(self, evento: str, **dati) -> None:
        self.percorso.parent.mkdir(parents=True, exist_ok=True)
        riga = {"quando": datetime.now(timezone.utc).isoformat(timespec="seconds"), "evento": evento, **dati}
        with self.percorso.open("a", encoding="utf-8") as file:
            file.write(json.dumps(riga, ensure_ascii=False) + "\n")
