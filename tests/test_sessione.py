"""La sessione: cronologia e contatori."""

import pytest

from assistente.provider import ErroreAI
from assistente.sessione import Sessione
from conftest import ProviderFinto, risposta_finta


def ignora(_testo):
    pass


def test_la_cronologia_cresce_di_due_messaggi_a_turno():
    sessione = Sessione(ProviderFinto(["ciao!"]))

    sessione.invia("ciao", ignora)

    assert sessione.messaggi == [
        {"role": "user", "content": "ciao"},
        {"role": "assistant", "content": "ciao!"},
    ]


def test_ogni_richiesta_contiene_tutta_la_conversazione():
    """È questo che dà "memoria" al modello: gli rimandiamo tutto ogni volta."""
    provider = ProviderFinto(["uno", "due"])
    sessione = Sessione(provider)

    sessione.invia("prima domanda", ignora)
    sessione.invia("seconda domanda", ignora)

    seconda_richiesta = provider.richieste[1]["messaggi"]
    assert [m["content"] for m in seconda_richiesta] == [
        "prima domanda",
        "uno",
        "seconda domanda",
    ]


def test_i_frammenti_arrivano_alla_funzione_di_stampa():
    sessione = Sessione(ProviderFinto(["testo in arrivo"]))
    ricevuti = []

    sessione.invia("domanda", ricevuti.append)

    assert ricevuti == ["testo in arrivo"]


def test_se_la_richiesta_fallisce_la_domanda_esce_dalla_cronologia():
    sessione = Sessione(ProviderFinto([ErroreAI("rete assente")]))

    with pytest.raises(ErroreAI):
        sessione.invia("domanda", ignora)

    assert sessione.messaggi == []


def test_un_rifiuto_non_resta_in_cronologia_ma_si_paga():
    rifiuto = risposta_finta(esito="rifiuto", ingresso=20, uscita=3)
    sessione = Sessione(ProviderFinto([rifiuto]))

    sessione.invia("domanda", ignora)

    assert sessione.messaggi == []
    assert sessione.token_ingresso == 20
    assert sessione.token_uscita == 3


def test_token_e_spesa_si_sommano_tra_i_turni():
    costosa = risposta_finta(modello="claude-haiku-5-5", ingresso=1_000_000, uscita=1_000_000)
    sessione = Sessione(ProviderFinto([costosa, costosa]))

    sessione.invia("a", ignora)
    sessione.invia("b", ignora)

    assert sessione.token_ingresso == 2_000_000
    # Haiku: 0,10 $ in ingresso + 0,50 $ in uscita per milione, due volte.
    assert sessione.spesa == pytest.approx(1.20)


def test_azzera_svuota_la_cronologia_ma_non_i_contatori():
    sessione = Sessione(ProviderFinto(["ok"]))
    sessione.invia("domanda", ignora)

    sessione.azzera()

    assert sessione.messaggi == []
    assert sessione.token_ingresso == 10
