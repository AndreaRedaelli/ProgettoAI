"""La logica dell'interfaccia grafica, senza nemmeno un pulsante.

Qui c'è tutto ciò che la finestra deve SAPER FARE: validare la maschera,
costruire la sessione, salvare la chiave, parlare con l'AI senza bloccare
la finestra. In gui.py resta solo il disegno. Separarle serve a due cose:
questa parte si prova nei test senza aprire finestre, e la finestra resta
corta e leggibile.
"""

import os
import queue
import threading
from dataclasses import dataclass
from pathlib import Path

from dotenv import set_key

from . import config
from .provider import ErroreAI, crea_provider
from .sessione import Sessione
from .sicurezza import RichiestaBloccata, crea_guardia
from .strumenti import crea_registro

# In quale variabile del file .env sta la chiave di ciascun fornitore.
NOMI_CHIAVE = {"groq": "GROQ_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}


@dataclass
class Impostazioni:
    """Ciò che l'utente scrive nella maschera."""

    provider: str = "groq"
    modello: str = ""  # vuoto = il modello predefinito del fornitore
    chiave: str = ""
    ambito: str = ""  # vuoto o "libero" = filtro di ambito spento
    salva_chiave: bool = False


def chiave_salvata(provider: str) -> str:
    """La chiave già presente nel file .env per questo fornitore, se c'è."""
    return os.getenv(NOMI_CHIAVE.get(provider, "")) or ""


def impostazioni_iniziali() -> Impostazioni:
    """La maschera parte con ciò che è scritto nel file .env."""
    return Impostazioni(
        provider=config.PROVIDER if config.PROVIDER in NOMI_CHIAVE else "groq",
        modello=config.MODELLO,
        chiave=chiave_salvata(config.PROVIDER),
        ambito=config.AMBITO or "libero",
    )


def valida(impostazioni: Impostazioni) -> list[str]:
    """Gli errori della maschera. Lista vuota = si può procedere.

    Controlliamo solo la forma: se la chiave è giusta lo sa soltanto il
    fornitore, e lo scopriremo alla prima domanda.
    """
    errori = []
    if impostazioni.provider not in NOMI_CHIAVE:
        errori.append(f"Fornitore sconosciuto: scegli tra {', '.join(NOMI_CHIAVE)}.")
    chiave = impostazioni.chiave.strip()
    if not chiave:
        errori.append("Inserisci la chiave API.")
    elif any(carattere.isspace() for carattere in chiave):
        errori.append("La chiave API non può contenere spazi.")
    return errori


def crea_sessione(impostazioni: Impostazioni, fabbrica_provider=crea_provider):
    """Costruisce sessione e registro a partire dalla maschera.

    È lo stesso montaggio che fa cli.py, con una differenza: le scelte
    arrivano dalla maschera invece che dal file .env. La chiave passa
    direttamente al fornitore e resta solo in memoria.
    `fabbrica_provider` esiste per i test, che ne passano una finta.
    """
    config.applica(impostazioni.provider, impostazioni.modello, impostazioni.ambito)
    provider = fabbrica_provider(impostazioni.chiave.strip())
    registro = crea_registro(estensioni=True)
    guardia = crea_guardia(provider, registro.definizioni())
    return Sessione(provider, guardia, registro), registro


def salva_nel_file_env(impostazioni: Impostazioni, file_env: str | Path = ".env") -> None:
    """Scrive le scelte nel file .env, così al prossimo avvio sono già lì.

    Viene chiamata solo se l'utente lo chiede con la casella apposita: una
    chiave su disco è più comoda ma anche più esposta di una in memoria.
    Le altre righe del file restano come sono.
    """
    file_env = Path(file_env)
    file_env.touch(exist_ok=True)
    valori = {
        "AI_PROVIDER": impostazioni.provider,
        "MODELLO": impostazioni.modello.strip(),
        NOMI_CHIAVE[impostazioni.provider]: impostazioni.chiave.strip(),
    }
    for nome, valore in valori.items():
        set_key(str(file_env), nome, valore, quote_mode="never")


class RichiestaConferma:
    """Una domanda che il filo di lavoro fa alla finestra, e ne aspetta la risposta.

    Il filo di lavoro non può aprire una finestra di dialogo: Tkinter va
    usato da un filo solo. Allora mette questa richiesta in coda e si ferma
    su `attendi()`; la finestra la mostra e chiama `rispondi()`.
    """

    def __init__(self, nome: str, dettaglio: str) -> None:
        self.nome = nome
        self.dettaglio = dettaglio
        self._risposta = False
        self._pronta = threading.Event()

    def rispondi(self, consenso: bool) -> None:
        self._risposta = consenso
        self._pronta.set()

    def attendi(self, secondi: float | None = None) -> bool:
        # Se nessuno risponde in tempo vale no: nel dubbio non si agisce.
        return self._risposta if self._pronta.wait(secondi) else False


class Lavoratore:
    """Parla con l'AI in un filo separato, così la finestra non si blocca.

    Una risposta può richiedere molti secondi. Se la aspettassimo nel filo
    della finestra, questa smetterebbe di ridisegnarsi e di reagire ai clic.
    Il filo di lavoro non tocca mai la finestra: mette degli EVENTI in una
    coda, e la finestra li legge quando può. Ogni evento è una coppia
    (tipo, dato):

        "testo"      un frammento della risposta
        "strumento"  la descrizione di uno strumento appena eseguito
        "conferma"   una RichiestaConferma a cui la finestra deve rispondere
        "nota"       un'informazione dei controlli (dati mascherati, avvisi)
        "bloccata"   il motivo per cui i controlli hanno fermato la domanda
        "errore"     un messaggio d'errore
        "fine"       il lavoro è terminato (sempre l'ultimo evento)
    """

    def __init__(self, sessione: Sessione, coda: queue.Queue | None = None) -> None:
        self.sessione = sessione
        self.coda = coda or queue.Queue()
        self.filo: threading.Thread | None = None
        # Le conferme della sessione passano da qui, cioè dalla coda.
        sessione.conferma = self._chiedi_conferma

    @property
    def occupato(self) -> bool:
        return self.filo is not None and self.filo.is_alive()

    def invia(self, domanda: str) -> bool:
        """Avvia la domanda in sottofondo. False se ce n'è già una in corso."""
        if self.occupato:
            return False
        # daemon=True: se l'utente chiude la finestra, il filo non la tiene in vita.
        self.filo = threading.Thread(target=self._lavora, args=(domanda,), daemon=True)
        self.filo.start()
        return True

    def _lavora(self, domanda: str) -> None:
        metti = self.coda.put
        try:
            risposta = self.sessione.invia(
                domanda,
                lambda frammento: metti(("testo", frammento)),
                lambda chiamata, risultato: metti(("strumento", descrivi_strumento(chiamata, risultato))),
            )
            if self.sessione.dati_mascherati:
                metti(("nota", "Mascherati prima dell'invio: " + ", ".join(self.sessione.dati_mascherati)))
            for avviso in self.sessione.avvisi:
                metti(("nota", f"Avviso: {avviso}"))
            if risposta.esito == "rifiuto":
                metti(("nota", "Il modello ha rifiutato la richiesta: non la tengo in cronologia."))
            elif risposta.esito == "troncata":
                metti(("nota", "Risposta troncata: raggiunto il limite di token."))
        except RichiestaBloccata as blocco:
            metti(("bloccata", str(blocco)))
        except ErroreAI as errore:
            metti(("errore", str(errore)))
        except Exception as errore:  # un filo che muore in silenzio lascerebbe la finestra in attesa
            metti(("errore", f"Errore imprevisto: {errore}"))
        finally:
            metti(("fine", None))

    def _chiedi_conferma(self, strumento, argomenti) -> bool:
        dettaglio = strumento.anteprima(**argomenti) if strumento.anteprima else str(argomenti)
        richiesta = RichiestaConferma(strumento.nome, dettaglio[:1500])
        self.coda.put(("conferma", richiesta))
        return richiesta.attendi()


def descrivi_strumento(chiamata, risultato) -> str:
    esito = "ERRORE: " + risultato.contenuto if risultato.errore else "ok"
    return f"strumento {chiamata.nome} {chiamata.argomenti}: {esito[:120]}"
