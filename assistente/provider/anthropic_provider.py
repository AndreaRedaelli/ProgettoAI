"""Fornitore Anthropic (Claude): API "messages"."""

import anthropic

from .. import config
from .base import ChiamataStrumento, Risposta, RisultatoStrumento, traduci_errore

# Su questi modelli, se i filtri di sicurezza rifiutano una richiesta, l'API può
# riprovarla da sola su un altro modello ("fallback").
MODELLI_CON_FALLBACK = {"claude-opus-5-5", "claude-sonnet-5-5"}

ESITI = {"max_tokens": "troncata", "refusal": "rifiuto"}


class ProviderAnthropic:
    NOME_CHIAVE = "ANTHROPIC_API_KEY"

    def __init__(self, client=None) -> None:
        # Senza argomenti, il client legge la chiave da ANTHROPIC_API_KEY.
        # Nei test passiamo un client finto al posto di quello vero.
        self.client = client or anthropic.Anthropic()

    def chiedi(self, messaggi: list, su_testo, system: str | None = None, strumenti=None) -> Risposta:
        """Invia l'intera conversazione; chiama `su_testo` a ogni frammento.

        `system` sostituisce il system prompt abituale: serve a usare lo
        stesso modello per un compito diverso, come il filtro di ambito.
        `strumenti` è l'elenco degli strumenti che il modello può chiedere.
        """
        parametri = dict(
            model=config.MODELLO,
            max_tokens=config.MAX_TOKENS,
            # Qui il system prompt è un parametro a parte, non un messaggio.
            system=system or config.SYSTEM_PROMPT,
            messages=messaggi,
            output_config={"effort": config.EFFORT},
        )
        if strumenti:
            # Stesse informazioni di Groq, con nomi di campo diversi.
            parametri["tools"] = [
                {"name": s.nome, "description": s.descrizione, "input_schema": s.parametri}
                for s in strumenti
            ]
        if config.MODELLO in MODELLI_CON_FALLBACK:
            parametri["betas"] = ["server-side-fallback-2026-07-01"]
            parametri["fallbacks"] = "default"

        try:
            with self.client.beta.messages.stream(**parametri) as stream:
                for frammento in stream.text_stream:
                    su_testo(frammento)
                finale = stream.get_final_message()
        except anthropic.APIError as errore:
            raise traduci_errore(anthropic, errore, self.NOME_CHIAVE) from errore

        return Risposta(
            # Teniamo TUTTI i blocchi della risposta, non solo il testo:
            # il modello li rivuole indietro così come li ha prodotti.
            messaggio={"role": "assistant", "content": finale.content},
            testo="".join(b.text for b in finale.content if b.type == "text"),
            modello=finale.model,
            token_ingresso=finale.usage.input_tokens,
            token_uscita=finale.usage.output_tokens,
            esito=ESITI.get(finale.stop_reason, "fine"),
            # Qui gli argomenti arrivano già come dizionario, non come testo.
            chiamate=[
                ChiamataStrumento(b.id, b.name, b.input if isinstance(b.input, dict) else None)
                for b in finale.content
                if b.type == "tool_use"
            ],
        )

    def messaggi_risultati(self, risultati: list[RisultatoStrumento]) -> list[dict]:
        """I risultati degli strumenti nel formato di Anthropic: tutti in UN messaggio utente."""
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": r.id,
                        "content": r.contenuto,
                        "is_error": r.errore,
                    }
                    for r in risultati
                ],
            }
        ]
