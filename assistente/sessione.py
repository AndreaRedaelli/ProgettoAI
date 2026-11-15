"""Una conversazione: la cronologia, i suoi contatori e il ciclo agentico.

Questa classe non sa nulla di terminali o finestre: riceve una domanda e
restituisce una risposta. Così la stessa logica serve qualunque interfaccia,
e si può provare nei test senza tastiera né rete.
"""

from . import config
from .provider import ErroreAI, Risposta, RisultatoStrumento, costo_in_dollari
from .sicurezza import RichiestaBloccata


class Sessione:
    def __init__(self, provider, guardia=None, strumenti=None, conferma=None) -> None:
        self.provider = provider
        # Senza guardia la sessione funziona lo stesso, ma senza controlli.
        self.guardia = guardia
        # Registro degli strumenti. Senza, è una semplice chat.
        self.strumenti = strumenti
        # Funzione che chiede all'utente il permesso per le azioni rischiose.
        self.conferma = conferma
        # La cronologia vive qui, nel nostro programma: è questa la "memoria".
        self.messaggi: list = []
        # Gli stessi scambi come semplice testo (domanda, risposta): servono
        # al filtro di ambito per capire le domande di seguito.
        self.scambi: list[tuple[str, str]] = []
        # Quante volte abbiamo interpellato l'AI: con un piano gratuito è il vero budget.
        self.richieste = 0
        self.token_ingresso = 0
        self.token_uscita = 0
        self.spesa = 0.0
        # Esito dei controlli sull'ultima domanda, per chi vuole mostrarlo.
        self.dati_mascherati: list[str] = []
        self.avvisi: list[str] = []

    def invia(self, domanda: str, su_testo, su_strumento=None, gia_verificata: bool = False) -> Risposta:
        """Manda la domanda con tutta la cronologia e registra la risposta.

        `su_testo` viene chiamata a ogni frammento di testo in arrivo.
        `su_strumento(chiamata, risultato)` dopo ogni strumento eseguito.
        Solleva RichiestaBloccata se i controlli fermano la domanda.
        Se qualcosa fallisce, la cronologia torna com'era prima della domanda.
        `gia_verificata` salta i controlli sulla domanda: lo usa il loop
        autonomo, che la domanda la scrive da sé. I risultati degli strumenti
        vengono controllati comunque.
        """
        self.dati_mascherati, self.avvisi = [], []

        if self.guardia and not gia_verificata:
            verdetto = self.guardia.verifica(domanda, self.scambi[-2:])
            if verdetto.giudice:
                # Anche la chiamata al modello giudice consuma token.
                self._conta(verdetto.giudice)
            if not verdetto.consentita:
                raise RichiestaBloccata(verdetto)
            # Da qui in poi usiamo il testo con i dati sensibili mascherati.
            domanda = verdetto.testo
            self.dati_mascherati = verdetto.mascherati

        inizio = len(self.messaggi)
        self.messaggi.append({"role": "user", "content": domanda})
        try:
            risposta = self._ciclo_agentico(su_testo, su_strumento)
        except BaseException:  # anche Ctrl+C, non solo gli errori dell'API
            del self.messaggi[inizio:]
            raise

        if risposta.esito == "rifiuto":
            del self.messaggi[inizio:]
            return risposta

        self.scambi.append((domanda, risposta.testo))
        if self.guardia:
            self.avvisi = self.guardia.controlla_uscita(risposta.testo)
        return risposta

    def _ciclo_agentico(self, su_testo, su_strumento) -> Risposta:
        """Il ciclo dell'agente: chiedi, esegui gli strumenti richiesti, richiedi.

        Il modello non agisce: chiede. Finché la risposta contiene richieste
        di strumenti le eseguiamo, aggiungiamo i risultati alla cronologia e
        interpelliamo di nuovo il modello. Quando risponde senza chiedere
        nulla, quella è la risposta finale.
        """
        definizioni = self.strumenti.definizioni() if self.strumenti else None
        passi = 0

        while True:
            risposta = self.provider.chiedi(self.messaggi, su_testo, strumenti=definizioni)
            # Il costo si paga a ogni giro, anche se la risposta è rifiutata o troncata.
            self._conta(risposta)

            if risposta.esito == "rifiuto":
                return risposta
            if risposta.chiamate and risposta.esito == "troncata":
                # Una chiamata tagliata a metà ha argomenti incompleti: non va eseguita.
                raise ErroreAI("Risposta troncata durante la richiesta di uno strumento.")

            self.messaggi.append(risposta.messaggio)
            if not risposta.chiamate:
                return risposta

            passi += 1
            if passi > config.MAX_PASSI_AGENTE:
                # Freno d'emergenza: rispondiamo "basta" a ogni richiesta e
                # togliamo gli strumenti, così il prossimo giro è l'ultimo.
                risultati = [
                    RisultatoStrumento(c.id, "Limite di passi raggiunto: rispondi con ciò che sai.", True)
                    for c in risposta.chiamate
                ]
                definizioni = None
            else:
                risultati = [self._esegui(chiamata, su_strumento) for chiamata in risposta.chiamate]

            # Tutti i risultati tornano al modello, nel formato del suo fornitore.
            self.messaggi.extend(self.provider.messaggi_risultati(risultati))

    def _esegui(self, chiamata, su_strumento) -> RisultatoStrumento:
        risultato = self.strumenti.esegui(chiamata, self.conferma)
        if self.guardia:
            # Ciò che uno strumento restituisce è un dato non fidato: passa
            # dai controlli prima di arrivare al modello.
            risultato = self.guardia.filtra_risultato(chiamata, risultato)
        if su_strumento:
            su_strumento(chiamata, risultato)
        return risultato

    def _conta(self, risposta: Risposta) -> None:
        self.richieste += 1
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
            f"Richieste: {self.richieste} · "
            f"token in ingresso: {self.token_ingresso} · in uscita: {self.token_uscita} · "
            f"spesa stimata: ${self.spesa:.4f}"
        )
