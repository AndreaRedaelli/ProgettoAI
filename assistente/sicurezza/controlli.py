"""Controlli locali: non chiamano nessuna AI, quindi sono istantanei e gratuiti."""

import re
import time
from collections import deque

# Frasi tipiche di chi prova a far ignorare al modello le sue regole.
# È una prima barriera economica: ferma i tentativi più comuni, ma basta
# riformulare la frase per aggirarla. Per questo non è l'unico controllo.
SEGNALI_INJECTION = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignor\w*\s+(?:tutte\s+)?(?:le\s+)?(?:tue\s+)?(?:istruzioni|regole)",
        r"ignore\s+(?:all\s+)?(?:your\s+)?(?:previous|prior|above)?\s*(?:instructions|rules)",
        r"(?:dimentica|scorda)\w*\s+(?:tutto|tutte|le\s+istruzioni|le\s+regole)",
        r"(?:rivela|mostra|stampa|ripeti|dimmi)\w*\s.{0,40}(?:system\s+prompt|prompt\s+di\s+sistema|istruzioni\s+(?:iniziali|di\s+sistema))",
        r"(?:reveal|show|print|repeat)\s.{0,40}(?:system\s+prompt|initial\s+instructions)",
        r"(?:da\s+ora|d'ora\s+in\s+poi|from\s+now\s+on)\b.{0,40}\b(?:sei|you\s+are|agisci|act\s+as)\b",
        r"\b(?:jailbreak|developer\s+mode|modalit[aà]\s+sviluppatore)\b",
    ]
]


def cerca_injection(testo: str) -> str | None:
    """Restituisce il frammento sospetto, oppure None se non ne trova."""
    for segnale in SEGNALI_INJECTION:
        if corrispondenza := segnale.search(testo):
            return corrispondenza.group()
    return None


class LimiteFrequenza:
    """Al massimo `massimo` richieste ogni `finestra` secondi (finestra scorrevole)."""

    def __init__(self, massimo: int, finestra: float = 60.0, orologio=time.monotonic) -> None:
        self.massimo = massimo
        self.finestra = finestra
        # L'orologio è un parametro: nei test ne passiamo uno che controlliamo noi.
        self.orologio = orologio
        self.istanti: deque[float] = deque()

    def consenti(self) -> bool:
        adesso = self.orologio()
        # Dimentica le richieste uscite dalla finestra.
        while self.istanti and adesso - self.istanti[0] >= self.finestra:
            self.istanti.popleft()
        if len(self.istanti) >= self.massimo:
            return False
        self.istanti.append(adesso)
        return True
