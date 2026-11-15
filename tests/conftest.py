"""Attrezzi condivisi dai test.

I test non chiamano mai un'AI vera: usano un fornitore finto che restituisce
risposte decise da noi. Così sono veloci, gratuiti e danno sempre lo stesso
risultato.
"""

import pytest

from assistente.provider import ErroreAI, Risposta


class ProviderFinto:
    """Fornitore che risponde con i testi preparati, uno per richiesta."""

    NOME_CHIAVE = "CHIAVE_FINTA"

    def __init__(self, risposte=None) -> None:
        self.risposte = list(risposte or ["risposta finta"])
        # Ogni richiesta ricevuta viene annotata qui, per poterla controllare.
        self.richieste: list = []

    def chiedi(self, messaggi, su_testo, **opzioni) -> Risposta:
        # Copiamo la lista: ci interessa com'era al momento della richiesta.
        self.richieste.append({"messaggi": list(messaggi), **opzioni})
        prossima = self.risposte.pop(0) if self.risposte else "risposta finta"

        if isinstance(prossima, Exception):
            raise prossima
        if isinstance(prossima, Risposta):
            return prossima

        su_testo(prossima)
        return Risposta(
            messaggio={"role": "assistant", "content": prossima},
            testo=prossima,
            modello="modello-finto",
            token_ingresso=10,
            token_uscita=5,
            esito="fine",
        )


@pytest.fixture
def provider_finto():
    return ProviderFinto()


def risposta_finta(testo="ok", esito="fine", modello="modello-finto", ingresso=10, uscita=5):
    return Risposta(
        messaggio={"role": "assistant", "content": testo},
        testo=testo,
        modello=modello,
        token_ingresso=ingresso,
        token_uscita=uscita,
        esito=esito,
    )


__all__ = ["ErroreAI", "ProviderFinto", "risposta_finta"]
