"""Sceglie il fornitore di AI in base alla variabile d'ambiente AI_PROVIDER."""

import os

from .. import config
from .base import ErroreAI, Risposta, costo_in_dollari

__all__ = ["ErroreAI", "Risposta", "costo_in_dollari", "crea_provider"]


def crea_provider():
    """Restituisce il fornitore configurato, pronto a ricevere domande."""
    # L'import è dentro il ramo: carichiamo solo l'SDK che serve davvero.
    if config.PROVIDER == "groq":
        from .groq_provider import ProviderGroq as Provider
    elif config.PROVIDER == "anthropic":
        from .anthropic_provider import ProviderAnthropic as Provider
    else:
        raise ErroreAI(
            f"AI_PROVIDER='{config.PROVIDER}' non riconosciuto: "
            f"usa uno tra {', '.join(config.MODELLI_PREDEFINITI)}."
        )

    if not os.getenv(Provider.NOME_CHIAVE):
        raise ErroreAI(
            f"Manca la chiave API: copia .env.example in .env e inserisci {Provider.NOME_CHIAVE}."
        )
    return Provider()
