"""Che cos'è uno strumento e come viene eseguito.

Il modello non esegue nulla: scrive "vorrei chiamare leggi_file con questi
argomenti". Siamo noi a decidere se e come farlo. Tutto ciò che il modello
scrive è quindi un input non fidato, da validare come quello di un utente.
"""

from dataclasses import dataclass
from typing import Callable

from ..provider import ChiamataStrumento, RisultatoStrumento

# Oltre questa lunghezza il risultato viene tagliato: un file enorme
# riempirebbe la conversazione e farebbe salire i costi.
MAX_CARATTERI_RISULTATO = 4000

TIPI = {"string": str, "integer": int, "number": (int, float), "boolean": bool}


class ErroreStrumento(Exception):
    """Errore previsto di uno strumento: il messaggio viene mostrato al modello."""


@dataclass
class Strumento:
    nome: str
    # La descrizione è ciò che il modello legge per decidere quando usarlo.
    descrizione: str
    # Schema JSON dei parametri.
    parametri: dict
    funzione: Callable[..., str]
    # "libero": parte subito. "conferma": serve il sì dell'utente.
    permesso: str = "libero"
    # Facoltativa: testo da mostrare all'utente quando gli si chiede conferma.
    anteprima: Callable[..., str] | None = None


class Registro:
    """L'elenco degli strumenti disponibili e l'unico punto che li esegue."""

    def __init__(self, strumenti=()) -> None:
        self.strumenti: dict[str, Strumento] = {}
        for strumento in strumenti:
            self.aggiungi(strumento)

    def aggiungi(self, strumento: Strumento) -> None:
        self.strumenti[strumento.nome] = strumento

    def definizioni(self) -> list[Strumento]:
        return list(self.strumenti.values())

    def esegui(self, chiamata: ChiamataStrumento, conferma=None) -> RisultatoStrumento:
        """Esegue la chiamata chiesta dal modello e restituisce sempre un risultato.

        Non solleva mai eccezioni: qualunque problema diventa un risultato
        d'errore, che torna al modello perché possa correggersi.
        `conferma(strumento, argomenti)` chiede il permesso all'utente.
        """

        def errore(messaggio: str) -> RisultatoStrumento:
            return RisultatoStrumento(chiamata.id, messaggio, errore=True)

        strumento = self.strumenti.get(chiamata.nome)
        if strumento is None:
            return errore(f"Strumento sconosciuto: {chiamata.nome}")
        if chiamata.argomenti is None:
            return errore("Argomenti non leggibili: devono essere un oggetto JSON.")
        if problema := _valida(strumento.parametri, chiamata.argomenti):
            return errore(problema)

        if strumento.permesso == "conferma":
            # Senza qualcuno a cui chiedere, la risposta è no.
            if conferma is None or not conferma(strumento, chiamata.argomenti):
                return errore("Azione non autorizzata dall'utente.")

        try:
            testo = str(strumento.funzione(**chiamata.argomenti))
        except ErroreStrumento as problema:
            return errore(str(problema))
        except Exception as problema:  # un errore dello strumento non deve fermare l'agente
            return errore(f"Errore interno dello strumento ({type(problema).__name__}).")

        if len(testo) > MAX_CARATTERI_RISULTATO:
            testo = testo[:MAX_CARATTERI_RISULTATO] + "\n[... risultato tagliato ...]"
        return RisultatoStrumento(chiamata.id, testo)


def _valida(schema: dict, argomenti: dict) -> str | None:
    """Controlla gli argomenti contro lo schema. Restituisce il problema, o None."""
    proprieta = schema.get("properties", {})
    for nome in schema.get("required", []):
        if nome not in argomenti:
            return f"Manca l'argomento obbligatorio '{nome}'."
    for nome, valore in argomenti.items():
        if nome not in proprieta:
            return f"Argomento non previsto: '{nome}'."
        tipo = TIPI.get(proprieta[nome].get("type"))
        # In Python True è anche un intero: lo escludiamo a mano.
        if tipo and (not isinstance(valore, tipo) or (tipo is not bool and isinstance(valore, bool))):
            return f"L'argomento '{nome}' deve essere di tipo {proprieta[nome]['type']}."
    return None
