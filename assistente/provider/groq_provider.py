"""Fornitore Groq: API in stile "chat completions", la più diffusa."""

import json

import groq

from .. import config
from .base import ChiamataStrumento, Risposta, RisultatoStrumento, traduci_errore


class ProviderGroq:
    NOME_CHIAVE = "GROQ_API_KEY"

    def __init__(self, client=None, chiave: str | None = None) -> None:
        # Nei test passiamo un client finto al posto di quello vero.
        self.client = client or groq.Groq(api_key=chiave)

    def chiedi(self, messaggi: list, su_testo, system: str | None = None, strumenti=None) -> Risposta:
        """Invia l'intera conversazione; chiama `su_testo` a ogni frammento.

        `system` sostituisce il system prompt abituale: serve a usare lo
        stesso modello per un compito diverso, come il filtro di ambito.
        `strumenti` è l'elenco degli strumenti che il modello può chiedere.
        """
        # Qui il system prompt è il primo messaggio della lista.
        richiesta = [{"role": "system", "content": system or config.SYSTEM_PROMPT}, *messaggi]
        parametri = dict(model=config.MODELLO, messages=richiesta, stream=True)
        if strumenti:
            # Ogni strumento è descritto da nome, descrizione e schema dei parametri.
            parametri["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": s.nome,
                        "description": s.descrizione,
                        "parameters": s.parametri,
                    },
                }
                for s in strumenti
            ]

        parti: list[str] = []
        # Le chiamate agli strumenti arrivano a pezzi come il testo: le
        # ricomponiamo usando l'indice di ciascuna.
        in_arrivo: dict[int, dict] = {}
        motivo = None
        uso = None
        modello = config.MODELLO
        try:
            stream = self.client.chat.completions.create(**parametri)
            for pezzo in stream:
                modello = pezzo.model or modello
                if pezzo.choices:
                    scelta = pezzo.choices[0]
                    if scelta.delta.content:
                        parti.append(scelta.delta.content)
                        su_testo(scelta.delta.content)
                    for frammento in scelta.delta.tool_calls or []:
                        voce = in_arrivo.setdefault(
                            frammento.index, {"id": "", "nome": "", "argomenti": ""}
                        )
                        if frammento.id:
                            voce["id"] = frammento.id
                        if frammento.function and frammento.function.name:
                            voce["nome"] = frammento.function.name
                        if frammento.function and frammento.function.arguments:
                            voce["argomenti"] += frammento.function.arguments
                    motivo = scelta.finish_reason or motivo
                # Il conteggio dei token arriva solo nell'ultimo pezzo.
                if pezzo.x_groq and pezzo.x_groq.usage:
                    uso = pezzo.x_groq.usage
                elif pezzo.usage:
                    uso = pezzo.usage
        except groq.APIError as errore:
            raise traduci_errore(groq, errore, self.NOME_CHIAVE) from errore

        testo = "".join(parti)
        voci = [in_arrivo[indice] for indice in sorted(in_arrivo)]
        messaggio: dict = {"role": "assistant", "content": testo or None}
        if voci:
            # Il messaggio va rimesso in cronologia con le chiamate così come
            # il modello le ha scritte.
            messaggio["tool_calls"] = [
                {
                    "id": v["id"],
                    "type": "function",
                    "function": {"name": v["nome"], "arguments": v["argomenti"] or "{}"},
                }
                for v in voci
            ]

        return Risposta(
            messaggio=messaggio,
            testo=testo,
            modello=modello,
            token_ingresso=uso.prompt_tokens if uso else 0,
            token_uscita=uso.completion_tokens if uso else 0,
            esito="troncata" if motivo == "length" else "fine",
            chiamate=[
                ChiamataStrumento(v["id"], v["nome"], _leggi_argomenti(v["argomenti"]))
                for v in voci
            ],
        )

    def messaggi_risultati(self, risultati: list[RisultatoStrumento]) -> list[dict]:
        """I risultati degli strumenti nel formato di Groq: un messaggio per risultato."""
        return [
            {
                "role": "tool",
                "tool_call_id": r.id,
                "content": ("ERRORE: " if r.errore else "") + r.contenuto,
            }
            for r in risultati
        ]


def _leggi_argomenti(grezzi: str) -> dict | None:
    """Gli argomenti arrivano come testo JSON scritto dal modello: può essere sbagliato."""
    try:
        argomenti = json.loads(grezzi or "{}")
    except json.JSONDecodeError:
        return None
    return argomenti if isinstance(argomenti, dict) else None
