"""I fornitori: scelta, traduzione delle risposte e degli errori.

Al posto dei client veri di Groq e Anthropic usiamo oggetti finti che imitano
solo la parte di SDK che il nostro codice usa.
"""

from types import SimpleNamespace as Oggetto

import pytest

from assistente import config
from assistente.provider import ErroreAI, costo_in_dollari, crea_provider
from assistente.provider.anthropic_provider import ProviderAnthropic
from assistente.provider.base import traduci_errore
from assistente.provider.groq_provider import ProviderGroq


# --- Scelta del fornitore -------------------------------------------------

def test_fornitore_sconosciuto(monkeypatch):
    monkeypatch.setattr(config, "PROVIDER", "pippo")

    with pytest.raises(ErroreAI, match="non riconosciuto"):
        crea_provider()


@pytest.mark.parametrize(
    "nome, chiave",
    [("groq", "GROQ_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY")],
)
def test_chiave_mancante(monkeypatch, nome, chiave):
    monkeypatch.setattr(config, "PROVIDER", nome)
    monkeypatch.delenv(chiave, raising=False)

    with pytest.raises(ErroreAI, match=chiave):
        crea_provider()


@pytest.mark.parametrize(
    "nome, chiave, classe",
    [
        ("groq", "GROQ_API_KEY", ProviderGroq),
        ("anthropic", "ANTHROPIC_API_KEY", ProviderAnthropic),
    ],
)
def test_viene_creato_il_fornitore_richiesto(monkeypatch, nome, chiave, classe):
    monkeypatch.setattr(config, "PROVIDER", nome)
    monkeypatch.setenv(chiave, "chiave-di-prova")

    assert isinstance(crea_provider(), classe)


# --- Groq -----------------------------------------------------------------

def pezzo_groq(testo=None, fine=None, uso=None):
    """Imita un pezzo dello streaming di Groq."""
    return Oggetto(
        model="modello-groq",
        choices=[Oggetto(delta=Oggetto(content=testo), finish_reason=fine)],
        usage=None,
        x_groq=Oggetto(usage=uso) if uso else None,
    )


class ClientGroqFinto:
    def __init__(self, pezzi):
        self.pezzi = pezzi
        self.parametri = None
        self.chat = Oggetto(completions=Oggetto(create=self._create))

    def _create(self, **parametri):
        self.parametri = parametri
        return iter(self.pezzi)


def test_groq_ricompone_il_testo_e_conta_i_token():
    uso = Oggetto(prompt_tokens=12, completion_tokens=3)
    client = ClientGroqFinto(
        [pezzo_groq("Cia"), pezzo_groq("o!"), pezzo_groq(fine="stop", uso=uso)]
    )
    frammenti = []

    risposta = ProviderGroq(client).chiedi([{"role": "user", "content": "ciao"}], frammenti.append)

    assert frammenti == ["Cia", "o!"]
    assert risposta.testo == "Ciao!"
    assert risposta.messaggio == {"role": "assistant", "content": "Ciao!"}
    assert (risposta.token_ingresso, risposta.token_uscita) == (12, 3)
    assert risposta.esito == "fine"


def test_groq_mette_il_system_prompt_come_primo_messaggio():
    client = ClientGroqFinto([pezzo_groq("ok", fine="stop")])

    ProviderGroq(client).chiedi([{"role": "user", "content": "ciao"}], lambda _: None)

    primo, secondo = client.parametri["messages"]
    assert primo == {"role": "system", "content": config.SYSTEM_PROMPT}
    assert secondo == {"role": "user", "content": "ciao"}


def test_groq_segnala_la_risposta_troncata():
    client = ClientGroqFinto([pezzo_groq("testo a met", fine="length")])

    risposta = ProviderGroq(client).chiedi([], lambda _: None)

    assert risposta.esito == "troncata"


# --- Anthropic ------------------------------------------------------------

class StreamAnthropicFinto:
    def __init__(self, frammenti, finale):
        self.text_stream = iter(frammenti)
        self._finale = finale

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def get_final_message(self):
        return self._finale


class ClientAnthropicFinto:
    def __init__(self, frammenti, stop_reason="end_turn"):
        self.parametri = None
        blocchi = [Oggetto(type="text", text="".join(frammenti))]
        finale = Oggetto(
            content=blocchi,
            model="modello-claude",
            stop_reason=stop_reason,
            usage=Oggetto(input_tokens=20, output_tokens=7),
        )
        self._stream = StreamAnthropicFinto(frammenti, finale)
        self.beta = Oggetto(messages=Oggetto(stream=self._crea_stream))

    def _crea_stream(self, **parametri):
        self.parametri = parametri
        return self._stream


def test_anthropic_ricompone_il_testo_e_conta_i_token():
    client = ClientAnthropicFinto(["Cia", "o!"])
    frammenti = []

    risposta = ProviderAnthropic(client).chiedi([{"role": "user", "content": "ciao"}], frammenti.append)

    assert frammenti == ["Cia", "o!"]
    assert risposta.testo == "Ciao!"
    assert (risposta.token_ingresso, risposta.token_uscita) == (20, 7)
    assert risposta.esito == "fine"


def test_anthropic_passa_il_system_prompt_come_parametro():
    client = ClientAnthropicFinto(["ok"])

    ProviderAnthropic(client).chiedi([{"role": "user", "content": "ciao"}], lambda _: None)

    assert client.parametri["system"] == config.SYSTEM_PROMPT
    assert client.parametri["messages"] == [{"role": "user", "content": "ciao"}]


@pytest.mark.parametrize(
    "stop_reason, esito",
    [("end_turn", "fine"), ("max_tokens", "troncata"), ("refusal", "rifiuto")],
)
def test_anthropic_traduce_il_motivo_di_arresto(stop_reason, esito):
    client = ClientAnthropicFinto(["x"], stop_reason=stop_reason)

    assert ProviderAnthropic(client).chiedi([], lambda _: None).esito == esito


# --- Errori e costi -------------------------------------------------------

class SdkFinto:
    """Imita le classi di errore che Groq e Anthropic hanno in comune."""

    class APIError(Exception):
        pass

    class APIConnectionError(APIError):
        pass

    class APIStatusError(APIError):
        status_code = 500
        message = "guasto"

    class AuthenticationError(APIStatusError):
        pass

    class RateLimitError(APIStatusError):
        pass


@pytest.mark.parametrize(
    "errore, atteso",
    [
        (SdkFinto.AuthenticationError(), "Chiave API non valida"),
        (SdkFinto.RateLimitError(), "Limite di richieste"),
        (SdkFinto.APIStatusError(), "Errore dell'API (500)"),
        (SdkFinto.APIConnectionError(), "Errore di rete"),
    ],
)
def test_gli_errori_diventano_messaggi_leggibili(errore, atteso):
    tradotto = traduci_errore(SdkFinto, errore, "CHIAVE")

    assert isinstance(tradotto, ErroreAI)
    assert atteso in str(tradotto)


def test_costo_di_un_modello_a_listino():
    # Opus: 4 $ in ingresso e 20 $ in uscita per milione di token.
    assert costo_in_dollari("claude-opus-5-5", 500_000, 100_000) == pytest.approx(4.0)


def test_un_modello_fuori_listino_costa_zero():
    assert costo_in_dollari("openai/gpt-oss-120b", 1_000_000, 1_000_000) == 0.0
