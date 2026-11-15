"""Una conversazione: la cronologia e i suoi contatori.

Questa classe non sa nulla di terminali o finestre: riceve una domanda e
restituisce una risposta. Così la stessa logica serve qualunque interfaccia,
e si può provare nei test senza tastiera né rete.
"""

from .provider import Risposta, costo_in_dollari
from .sicurezza import RichiestaBloccata


class Sessione:
    def __init__(self, provider, guardia=None) -> None:
        self.provider = provider
        # Senza guardia la sessione funziona lo stesso, ma senza controlli.
        self.guardia = guardia
        # La cronologia vive qui, nel nostro programma: è questa la "memoria".
        self.messaggi: list = []
        # Gli stessi scambi come semplice testo (domanda, risposta): servono
        # al filtro di ambito per capire le domande di seguito.
        self.scambi: list[tuple[str, str]] = []
        self.token_ingresso = 0
        self.token_uscita = 0
        self.spesa = 0.0
        # Esito dei controlli sull'ultima domanda, per chi vuole mostrarlo.
        self.dati_mascherati: list[str] = []
        self.avvisi: list[str] = []

    def invia(self, domanda: str, su_testo) -> Risposta:
        """Manda la domanda con tutta la cronologia e registra la risposta.

        `su_testo` viene chiamata a ogni frammento di testo in arrivo.
        Solleva RichiestaBloccata se i controlli fermano la domanda.
        Se la richiesta fallisce o viene rifiutata, la domanda viene tolta
        dalla cronologia, che resta così un'alternanza valida di turni.
        """
        self.dati_mascherati, self.avvisi = [], []

        if self.guardia:
            verdetto = self.guardia.verifica(domanda, self.scambi[-2:])
            if verdetto.giudice:
                # Anche la chiamata al modello giudice consuma token.
                self._conta(verdetto.giudice)
            if not verdetto.consentita:
                raise RichiestaBloccata(verdetto)
            # Da qui in poi usiamo il testo con i dati sensibili mascherati.
            domanda = verdetto.testo
            self.dati_mascherati = verdetto.mascherati

        self.messaggi.append({"role": "user", "content": domanda})
        try:
            risposta = self.provider.chiedi(self.messaggi, su_testo)
        except BaseException:  # anche Ctrl+C, non solo gli errori dell'API
            self.messaggi.pop()
            raise

        # Il costo si paga anche se la risposta viene rifiutata o troncata.
        self._conta(risposta)

        if risposta.esito == "rifiuto":
            self.messaggi.pop()
            return risposta

        # Alla prossima domanda il modello riceverà anche questa risposta.
        self.messaggi.append(risposta.messaggio)
        self.scambi.append((domanda, risposta.testo))
        if self.guardia:
            self.avvisi = self.guardia.controlla_uscita(risposta.testo)
        return risposta

    def _conta(self, risposta: Risposta) -> None:
        self.token_ingresso += risposta.token_ingresso
        self.token_uscita += risposta.token_uscita
        self.spesa += costo_in_dollari(
            risposta.modello, risposta.token_ingresso, risposta.token_uscita
        )

    def azzera(self) -> None:
        """Dimentica la conversazione. I contatori di spesa restano."""
        self.messaggi.clear()
        self.scambi.clear()

    def riepilogo(self) -> str:
        return (
            f"Token in ingresso: {self.token_ingresso} · in uscita: {self.token_uscita} · "
            f"spesa stimata: ${self.spesa:.4f}"
        )
