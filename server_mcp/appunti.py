"""Un nostro server MCP: un blocco di appunti.

Qui usiamo la libreria ufficiale `mcp`, che si occupa del protocollo: noi
scriviamo solo le funzioni. Essendo un server MCP standard, funziona con
qualunque client MCP, non solo con il nostro assistente.

Avvio a mano (resta in attesa di messaggi sullo standard input):
    python -m server_mcp.appunti
"""

import json
import os
from pathlib import Path

from mcp.server import MCPServer

# Gli appunti stanno nell'area di lavoro, come tutto ciò che l'agente tocca.
FILE_APPUNTI = Path(os.getenv("AREA_LAVORO") or "area_lavoro") / "appunti.json"

server = MCPServer("appunti")


def _leggi() -> list[str]:
    if not FILE_APPUNTI.is_file():
        return []
    return json.loads(FILE_APPUNTI.read_text(encoding="utf-8"))


@server.tool()
def aggiungi_appunto(testo: str) -> str:
    """Salva un appunto nel blocco."""
    appunti = _leggi()
    appunti.append(testo)
    FILE_APPUNTI.parent.mkdir(parents=True, exist_ok=True)
    FILE_APPUNTI.write_text(json.dumps(appunti, ensure_ascii=False, indent=2), encoding="utf-8")
    return f"Appunto {len(appunti)} salvato."


@server.tool()
def elenca_appunti() -> str:
    """Elenca tutti gli appunti salvati, numerati."""
    appunti = _leggi()
    return "\n".join(f"{n}. {testo}" for n, testo in enumerate(appunti, start=1)) or "Nessun appunto."


@server.tool()
def cerca_appunti(testo: str) -> str:
    """Cerca gli appunti che contengono il testo indicato."""
    trovati = [a for a in _leggi() if testo.lower() in a.lower()]
    return "\n".join(trovati) or "Nessun appunto trovato."


if __name__ == "__main__":
    server.run()
