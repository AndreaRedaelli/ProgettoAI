"""Una conversazione: la cronologia e i suoi contatori.

Questa classe non sa nulla di terminali o finestre: riceve una domanda e
restituisce una risposta. Così la stessa logica serve qualunque interfaccia,
e si può provare nei test senza tastiera né rete.
"""

from .provider import Risposta, costo_in_dollari


class Sessione:
    def __init__(self, provider) -> None:
        self.provider = provider
        # La cronologia vive qui, nel nostro programma: è questa la "memoria".
        self.messaggi: list = []
        self.token_ingresso = 0
        self.token_uscita = 0
        self.spesa = 0.0

    def invia(self, domanda: str, su_testo) -> Risposta:
        """Manda la domanda con tutta la cronologia e registra la risposta.

        `su_testo` viene chiamata a ogni frammento di testo in arrivo.
        Se la richiesta fallisce o viene rifiutata, la domanda viene tolta
        dalla cronologia, che resta così un'alternanza valida di turni.
        """
        self.messaggi.append({"role": "user", "content": domanda})
        try:
            risposta = self.provider.chiedi(self.messaggi, su_testo)
        except BaseException:  # anche Ctrl+C, non solo gli errori dell'API
            self.messaggi.pop()
            raise

        # Il costo si paga anche se la risposta viene rifiutata o troncata.
        self.token_ingresso += risposta.token_ingresso
        self.token_uscita += risposta.token_uscita
        self.spesa += costo_in_dollari(
            risposta.modello, risposta.token_ingresso, risposta.token_uscita
        )

        if risposta.esito == "rifiuto":
            self.messaggi.pop()
        else:
            # Alla prossima domanda il modello riceverà anche questa risposta.
            self.messaggi.append(risposta.messaggio)
        return risposta

    def azzera(self) -> None:
        """Dimentica la conversazione. I contatori di spesa restano."""
        self.messaggi.clear()

    def riepilogo(self) -> str:
        return (
            f"Token in ingresso: {self.token_ingresso} · in uscita: {self.token_uscita} · "
            f"spesa stimata: ${self.spesa:.4f}"
        )
