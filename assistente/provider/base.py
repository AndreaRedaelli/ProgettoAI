"""Ciò che tutti i fornitori hanno in comune.

Ogni fornitore (Groq, Anthropic) ha il suo SDK, il suo formato dei messaggi e
i suoi errori. Qui definiamo la forma unica in cui il resto del programma li
vede, così la chat non deve sapere con chi sta parlando.
"""

from dataclasses import dataclass, field

from .. import config


class ErroreAI(Exception):
    """Errore di un fornitore, già tradotto in un messaggio per l'utente."""

    # True se ha senso aspettare e riprovare (per esempio: troppe richieste).
    riprovabile = False


@dataclass
class ChiamataStrumento:
    """Il modello chiede di eseguire uno strumento."""

    id: str
    nome: str
    # None se il modello ha scritto argomenti che non si riescono a leggere.
    argomenti: dict | None


@dataclass
class RisultatoStrumento:
    """Ciò che restituiamo al modello dopo aver eseguito (o rifiutato) lo strumento."""

    id: str
    contenuto: str
    errore: bool = False


@dataclass
class Risposta:
    # Messaggio da aggiungere alla cronologia, già nel formato del fornitore.
    messaggio: dict
    # Solo il testo della risposta, uguale per tutti i fornitori.
    testo: str
    modello: str
    token_ingresso: int
    token_uscita: int
    # "fine", "troncata" oppure "rifiuto"
    esito: str
    # Strumenti che il modello chiede di eseguire. Vuota = risposta definitiva.
    chiamate: list[ChiamataStrumento] = field(default_factory=list)


def traduci_errore(sdk, errore: Exception, nome_chiave: str) -> ErroreAI:
    """Trasforma un errore dell'SDK in un ErroreAI.

    Gli SDK di Groq e Anthropic espongono classi di errore con gli stessi
    nomi, quindi basta passare il modulo giusto.
    """
    if isinstance(errore, sdk.AuthenticationError):
        return ErroreAI(f"Chiave API non valida: controlla {nome_chiave} nel file .env.")
    if isinstance(errore, sdk.RateLimitError):
        tradotto = ErroreAI("Limite di richieste raggiunto: aspetta un po' e riprova.")
        tradotto.riprovabile = True
        return tradotto
    if isinstance(errore, sdk.APIStatusError):
        return ErroreAI(f"Errore dell'API ({errore.status_code}): {errore.message}")
    if isinstance(errore, sdk.APIConnectionError):
        return ErroreAI("Errore di rete: controlla la connessione.")
    return ErroreAI(f"Errore inatteso: {errore}")


def costo_in_dollari(modello: str, token_ingresso: int, token_uscita: int) -> float:
    """Stima del costo di una risposta. I modelli non in listino valgono zero."""
    prezzo_in, prezzo_out = config.PREZZI.get(modello, (0.0, 0.0))
    return (token_ingresso * prezzo_in + token_uscita * prezzo_out) / 1_000_000
