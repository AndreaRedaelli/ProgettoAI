"""Fornitore Groq: API in stile "chat completions", la più diffusa."""

import groq

from .. import config
from .base import Risposta, traduci_errore


class ProviderGroq:
    NOME_CHIAVE = "GROQ_API_KEY"

    def __init__(self, client=None) -> None:
        # Senza argomenti, il client legge la chiave da GROQ_API_KEY.
        # Nei test passiamo un client finto al posto di quello vero.
        self.client = client or groq.Groq()

    def chiedi(self, messaggi: list, su_testo, system: str | None = None) -> Risposta:
        """Invia l'intera conversazione; chiama `su_testo` a ogni frammento.

        `system` sostituisce il system prompt abituale: serve a usare lo
        stesso modello per un compito diverso, come il filtro di ambito.
        """
        # Qui il system prompt è il primo messaggio della lista.
        richiesta = [{"role": "system", "content": system or config.SYSTEM_PROMPT}, *messaggi]

        parti: list[str] = []
        motivo = None
        uso = None
        modello = config.MODELLO
        try:
            stream = self.client.chat.completions.create(
                model=config.MODELLO, messages=richiesta, stream=True
            )
            for pezzo in stream:
                modello = pezzo.model or modello
                if pezzo.choices:
                    scelta = pezzo.choices[0]
                    if scelta.delta.content:
                        parti.append(scelta.delta.content)
                        su_testo(scelta.delta.content)
                    motivo = scelta.finish_reason or motivo
                # Il conteggio dei token arriva solo nell'ultimo pezzo.
                if pezzo.x_groq and pezzo.x_groq.usage:
                    uso = pezzo.x_groq.usage
                elif pezzo.usage:
                    uso = pezzo.usage
        except groq.APIError as errore:
            raise traduci_errore(groq, errore, self.NOME_CHIAVE) from errore

        testo = "".join(parti)
        return Risposta(
            messaggio={"role": "assistant", "content": testo},
            testo=testo,
            modello=modello,
            token_ingresso=uso.prompt_tokens if uso else 0,
            token_uscita=uso.completion_tokens if uso else 0,
            esito="troncata" if motivo == "length" else "fine",
        )
