"""L'interfaccia grafica: la maschera, il filo di lavoro, la finestra.

Quasi tutti i test riguardano gui_logica.py e non aprono finestre. Solo gli
ultimi costruiscono la finestra vera, con un fornitore finto.
"""

import queue
import threading
import time

import pytest

from assistente import config
from assistente.gui_logica import (
    Impostazioni,
    Lavoratore,
    RichiestaConferma,
    crea_sessione,
    salva_nel_file_env,
    valida,
)
from assistente.provider import ChiamataStrumento, ErroreAI
from conftest import ProviderFinto, risposta_finta

CHIAVE_FINTA = "chiave-di-prova"


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    """Ogni test lavora in cartelle temporanee e lascia config com'era.

    config.applica cambia delle variabili globali: registrandole qui con il
    loro valore attuale, pytest le ripristina alla fine del test.
    """
    for nome in ("PROVIDER", "MODELLO", "AMBITO", "SYSTEM_PROMPT"):
        monkeypatch.setattr(config, nome, getattr(config, nome))
    monkeypatch.setattr(config, "AREA_LAVORO", str(tmp_path / "area"))
    monkeypatch.setattr(config, "CARTELLA_PLUGIN", str(tmp_path / "nessun_plugin"))
    monkeypatch.setattr(config, "FILE_MCP", str(tmp_path / "nessun_mcp.json"))
    monkeypatch.setattr(config, "FILE_AUDIT", str(tmp_path / "audit.jsonl"))


def sessione_finta(risposte, ambito="libero"):
    provider = ProviderFinto(risposte)
    impostazioni = Impostazioni("groq", "", CHIAVE_FINTA, ambito)
    sessione, _registro = crea_sessione(impostazioni, lambda _chiave: provider)
    return sessione, provider


def eventi_di(lavoratore, domanda, su_conferma=None):
    """Invia la domanda e raccoglie gli eventi fino a "fine"."""
    assert lavoratore.invia(domanda)
    eventi = []
    while True:
        tipo, dato = lavoratore.coda.get(timeout=5)
        eventi.append((tipo, dato))
        if tipo == "conferma" and su_conferma:
            dato.rispondi(su_conferma(dato))
        if tipo == "fine":
            lavoratore.filo.join(timeout=5)
            return eventi


# --- La maschera ------------------------------------------------------------

def test_una_maschera_compilata_bene_non_ha_errori():
    assert valida(Impostazioni("groq", "", CHIAVE_FINTA)) == []


@pytest.mark.parametrize(
    "impostazioni, atteso",
    [
        (Impostazioni("groq", "", ""), "Inserisci la chiave"),
        (Impostazioni("groq", "", "   "), "Inserisci la chiave"),
        (Impostazioni("groq", "", "chiave con spazi"), "spazi"),
        (Impostazioni("altro", "", CHIAVE_FINTA), "Fornitore sconosciuto"),
    ],
)
def test_la_maschera_segnala_cosa_manca(impostazioni, atteso):
    assert atteso in " ".join(valida(impostazioni))


# --- Dalla maschera alla sessione --------------------------------------------

def test_le_scelte_della_maschera_diventano_la_configurazione():
    chiavi = []
    impostazioni = Impostazioni("anthropic", "", "  " + CHIAVE_FINTA + "  ", "cucina italiana")

    sessione, registro = crea_sessione(impostazioni, lambda chiave: chiavi.append(chiave) or ProviderFinto())

    assert config.PROVIDER == "anthropic"
    assert config.MODELLO == config.MODELLI_PREDEFINITI["anthropic"]
    assert config.AMBITO == "cucina italiana"
    assert "cucina italiana" in config.SYSTEM_PROMPT
    # La chiave arriva al fornitore ripulita dagli spazi, senza passare dal disco.
    assert chiavi == [CHIAVE_FINTA]
    assert sessione.strumenti is registro
    assert sessione.guardia.ambito == "cucina italiana"


def test_ambito_libero_spegne_il_filtro():
    sessione, provider = sessione_finta(["ciao"], ambito="libero")

    sessione.invia("qual è la ricetta della carbonara?", lambda _t: None)

    assert config.AMBITO == ""
    assert len(provider.richieste) == 1  # nessuna chiamata al giudice


def test_un_modello_scritto_a_mano_ha_la_precedenza():
    crea_sessione(Impostazioni("groq", "un-altro-modello", CHIAVE_FINTA, "libero"), lambda _c: ProviderFinto())

    assert config.MODELLO == "un-altro-modello"


# --- Il salvataggio nel file .env ---------------------------------------------

def test_salvare_scrive_fornitore_modello_e_chiave(tmp_path):
    file_env = tmp_path / ".env"

    salva_nel_file_env(Impostazioni("groq", "modello-x", CHIAVE_FINTA), file_env)

    righe = file_env.read_text(encoding="utf-8").splitlines()
    assert "AI_PROVIDER=groq" in righe
    assert "MODELLO=modello-x" in righe
    assert f"GROQ_API_KEY={CHIAVE_FINTA}" in righe


def test_salvare_non_tocca_le_altre_righe(tmp_path):
    file_env = tmp_path / ".env"
    file_env.write_text("EFFORT=high\nGROQ_API_KEY=vecchia\nANTHROPIC_API_KEY=resta\n", encoding="utf-8")

    salva_nel_file_env(Impostazioni("groq", "", "nuova"), file_env)

    righe = file_env.read_text(encoding="utf-8").splitlines()
    assert "EFFORT=high" in righe
    assert "GROQ_API_KEY=nuova" in righe
    assert "ANTHROPIC_API_KEY=resta" in righe
    assert "GROQ_API_KEY=vecchia" not in righe


# --- La conferma tra due fili --------------------------------------------------

def test_la_conferma_aspetta_la_risposta_dell_altro_filo():
    richiesta = RichiestaConferma("scrivi_file", "dettaglio")
    threading.Timer(0.05, richiesta.rispondi, args=(True,)).start()

    assert richiesta.attendi(5) is True


def test_una_conferma_senza_risposta_vale_no():
    assert RichiestaConferma("scrivi_file", "dettaglio").attendi(0.01) is False


# --- Il filo di lavoro ---------------------------------------------------------

def test_la_risposta_arriva_come_eventi_e_finisce_con_fine():
    sessione, _ = sessione_finta(["Ciao!"])

    eventi = eventi_di(Lavoratore(sessione), "saluta")

    assert eventi == [("testo", "Ciao!"), ("fine", None)]
    assert sessione.richieste == 1


def test_una_domanda_bloccata_diventa_un_evento_non_un_eccezione():
    sessione, _ = sessione_finta(['{"ambito": "fuori", "motivo": "è cucina"}'], ambito="programmazione")

    eventi = eventi_di(Lavoratore(sessione), "ricetta della carbonara")

    assert [tipo for tipo, _ in eventi] == ["bloccata", "fine"]
    assert "fuori ambito" in eventi[0][1]


@pytest.mark.parametrize("guasto", [ErroreAI("chiave non valida"), RuntimeError("imprevisto")])
def test_un_errore_non_lascia_la_finestra_in_attesa(guasto):
    sessione, _ = sessione_finta([guasto])

    eventi = eventi_di(Lavoratore(sessione), "domanda")

    assert [tipo for tipo, _ in eventi] == ["errore", "fine"]
    assert str(guasto) in eventi[0][1]


def test_non_parte_una_seconda_domanda_mentre_la_prima_e_in_corso():
    sessione, _ = sessione_finta(["ok"])
    lavoratore = Lavoratore(sessione)
    via_libera = threading.Event()
    sessione.invia = lambda *_argomenti: via_libera.wait(5)  # una risposta "lenta"

    assert lavoratore.invia("prima") is True
    assert lavoratore.invia("seconda") is False
    via_libera.set()
    lavoratore.filo.join(timeout=5)


def scrive_un_file():
    chiamata = ChiamataStrumento("c1", "scrivi_file", {"percorso": "nota.txt", "contenuto": "ciao"})
    return [risposta_finta(testo="", chiamate=[chiamata]), "Fatto."]


@pytest.mark.parametrize("consenso", [True, False])
def test_gli_strumenti_rischiosi_passano_dalla_conferma(tmp_path, consenso):
    sessione, _ = sessione_finta(scrive_un_file())
    richieste = []

    eventi = eventi_di(Lavoratore(sessione), "scrivi la nota", lambda r: richieste.append(r) or consenso)

    assert [tipo for tipo, _ in eventi] == ["conferma", "strumento", "testo", "fine"]
    assert richieste[0].nome == "scrivi_file"
    assert (tmp_path / "area" / "nota.txt").exists() is consenso


# --- La finestra vera ----------------------------------------------------------

@pytest.fixture
def finestra(monkeypatch):
    tk = pytest.importorskip("tkinter")
    from assistente.gui import Finestra

    # Nessuna chiave vera deve comparire nella maschera durante i test.
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    try:
        radice = tk.Tk()
    except tk.TclError:
        pytest.skip("nessuno schermo disponibile")
    radice.withdraw()  # la finestra esiste ma non compare
    provider = ProviderFinto(["Ciao dalla finestra!"])
    finestra = Finestra(radice, lambda _chiave: provider, chiedi_conferma=lambda _nome, _dettaglio: True)
    finestra.provider_finto = provider
    yield finestra
    finestra.chiudi()


def attendi_risposta(finestra):
    """Fa girare la finestra finché il filo di lavoro non ha finito."""
    scadenza = time.monotonic() + 5
    while finestra.lavoratore.occupato or not finestra.coda.empty():
        assert time.monotonic() < scadenza, "la risposta non è arrivata"
        finestra.leggi_coda()
        finestra.radice.update()
        time.sleep(0.01)


def test_senza_chiave_la_finestra_non_si_connette(finestra):
    finestra.var_chiave.set("")

    finestra.connetti()

    assert "chiave" in finestra.var_stato.get()
    assert finestra.sessione is None
    assert str(finestra.pulsante_invia["state"]) == "disabled"


def test_dalla_maschera_alla_risposta_nella_chat(finestra):
    finestra.var_chiave.set(CHIAVE_FINTA)
    finestra.var_ambito.set("libero")
    finestra.connetti()
    assert "Connesso a groq" in finestra.var_stato.get()

    finestra.campo_domanda.insert(0, "saluta")
    finestra.invia()
    attendi_risposta(finestra)

    chat = finestra.testo.get("1.0", "end")
    assert "Tu: saluta" in chat
    assert "AI: Ciao dalla finestra!" in chat
    assert "Richieste: 1" in finestra.var_riepilogo.get()
    assert str(finestra.pulsante_invia["state"]) == "normal"
    # La chiave non finisce mai nella chat.
    assert CHIAVE_FINTA not in chat


def test_la_chiave_e_nascosta_finche_non_si_chiede_di_mostrarla(finestra):
    assert finestra.campo_chiave.cget("show") == "•"

    finestra.var_mostra.set(True)
    finestra._mostra_chiave()

    assert finestra.campo_chiave.cget("show") == ""


def test_cambiando_ai_cambia_il_modello_proposto(finestra):
    finestra.var_provider.set("anthropic")

    finestra.cambia_provider()

    assert finestra.var_modello.get() == config.MODELLI_PREDEFINITI["anthropic"]
    assert finestra.var_chiave.get() == ""
