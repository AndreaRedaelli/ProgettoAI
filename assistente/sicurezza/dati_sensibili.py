"""Mascheramento dei dati sensibili prima che lascino il computer.

Il modello non ha bisogno della tua email o della tua carta per rispondere:
le sostituiamo con un segnaposto. È un controllo locale e gratuito, fatto con
espressioni regolari, quindi riconosce solo le forme che gli abbiamo insegnato.
"""

import re

# L'ordine conta: le forme più specifiche vengono prima di quelle generiche.
MODELLI = [
    ("chiave API", re.compile(r"\b(?:gsk|sk|pk|ghp|gho|xoxb|xoxp)[-_][A-Za-z0-9_-]{16,}")),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")),
    ("codice fiscale", re.compile(r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b", re.IGNORECASE)),
]

CARTA = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def _supera_luhn(numero: str) -> bool:
    """Controllo di Luhn: distingue una carta vera da una fila qualsiasi di cifre."""
    cifre = [int(c) for c in numero if c.isdigit()]
    somma = 0
    for posizione, cifra in enumerate(reversed(cifre)):
        if posizione % 2 == 1:
            cifra *= 2
            if cifra > 9:
                cifra -= 9
        somma += cifra
    return somma % 10 == 0


def maschera(testo: str) -> tuple[str, list[str]]:
    """Restituisce il testo con i dati sensibili sostituiti e l'elenco dei tipi trovati."""
    trovati: list[str] = []

    for nome, modello in MODELLI:
        if modello.search(testo):
            trovati.append(nome)
            testo = modello.sub(f"[{nome.upper()}]", testo)

    def sostituisci_carta(corrispondenza: re.Match) -> str:
        if not _supera_luhn(corrispondenza.group()):
            return corrispondenza.group()
        if "carta" not in trovati:
            trovati.append("carta")
        return "[CARTA]"

    testo = CARTA.sub(sostituisci_carta, testo)
    return testo, trovati
