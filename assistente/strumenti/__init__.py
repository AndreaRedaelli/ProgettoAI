"""Gli strumenti che l'agente può usare."""

import json
from pathlib import Path

from .. import config
from .base import ErroreStrumento, Registro, Strumento
from .file import crea_strumenti_file
from .mcp_client import carica_server_mcp
from .plugin import carica_plugin
from .python import crea_strumento_python
from .utili import crea_strumenti_utili

__all__ = ["ErroreStrumento", "Registro", "Strumento", "crea_registro"]


def crea_registro(area: Path | None = None, estensioni: bool = False) -> Registro:
    """Il registro con gli strumenti predefiniti, legati all'area di lavoro.

    Con `estensioni=True` carica anche i plugin e collega i server MCP.
    Gli strumenti predefiniti vengono registrati per primi: un'estensione
    non può prenderne il nome.
    """
    area = Path(area or config.AREA_LAVORO)
    area.mkdir(parents=True, exist_ok=True)
    registro = Registro(
        [
            *crea_strumenti_file(area),
            *crea_strumenti_utili(),
            crea_strumento_python(area, config.TEMPO_MASSIMO_SCRIPT),
        ]
    )

    if estensioni:
        registro.note += carica_plugin(registro, Path(config.CARTELLA_PLUGIN), config.PLUGIN_FIDATI)
        registro.note += carica_server_mcp(registro, _leggi_configurazione_mcp())
    return registro


def _leggi_configurazione_mcp() -> dict:
    file = Path(config.FILE_MCP)
    if not file.is_file():
        return {}
    try:
        configurazione = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return configurazione if isinstance(configurazione, dict) else {}
