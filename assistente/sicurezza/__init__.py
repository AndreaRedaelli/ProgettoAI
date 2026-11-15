"""Controlli di sicurezza. Stanno fuori da provider/: valgono per qualunque AI."""

from .. import config
from .audit import Audit
from .guardia import Guardia, RichiestaBloccata, Verdetto

__all__ = ["Audit", "Guardia", "RichiestaBloccata", "Verdetto", "crea_guardia"]


def crea_guardia(provider) -> Guardia:
    """La guardia con le impostazioni lette da config."""
    return Guardia(
        provider,
        ambito=config.AMBITO,
        audit=Audit(config.FILE_AUDIT),
        max_caratteri=config.MAX_CARATTERI_DOMANDA,
        max_richieste_al_minuto=config.MAX_RICHIESTE_AL_MINUTO,
        max_richieste_sessione=config.MAX_RICHIESTE_SESSIONE,
        system_prompt=config.SYSTEM_PROMPT,
    )
