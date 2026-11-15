"""Plugin di esempio: strumenti sul testo.

Per scrivere un plugin basta un file come questo nella cartella plugin/:
una o più funzioni, e una lista STRUMENTI che le descrive al modello.
"""

from assistente.strumenti import Strumento


def conta_parole(testo: str) -> str:
    parole = testo.split()
    return f"{len(parole)} parole, {len(testo)} caratteri"


def inverti(testo: str) -> str:
    return testo[::-1]


_UN_TESTO = {
    "type": "object",
    "properties": {"testo": {"type": "string", "description": "Il testo su cui lavorare"}},
    "required": ["testo"],
}

STRUMENTI = [
    Strumento("conta_parole", "Conta parole e caratteri di un testo.", _UN_TESTO, conta_parole),
    Strumento("inverti_testo", "Restituisce il testo scritto al contrario.", _UN_TESTO, inverti),
]
