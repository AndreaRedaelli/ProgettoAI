"""Gli strumenti che l'agente può usare."""

from pathlib import Path

from .. import config
from .base import ErroreStrumento, Registro, Strumento
from .file import crea_strumenti_file
from .python import crea_strumento_python
from .utili import crea_strumenti_utili

__all__ = ["ErroreStrumento", "Registro", "Strumento", "crea_registro"]


def crea_registro(area: Path | None = None) -> Registro:
    """Il registro con gli strumenti predefiniti, legati all'area di lavoro."""
    area = Path(area or config.AREA_LAVORO)
    area.mkdir(parents=True, exist_ok=True)
    return Registro(
        [
            *crea_strumenti_file(area),
            *crea_strumenti_utili(),
            crea_strumento_python(area, config.TEMPO_MASSIMO_SCRIPT),
        ]
    )
