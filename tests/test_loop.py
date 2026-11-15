"""Il loop autonomo: quando continua, quando si ferma, come riprende."""

import json

import pytest

from assistente.loop import LoopAutonomo, StatoLoop
from assistente.provider import ChiamataStrumento, ErroreAI
from assistente.sicurezza import Guardia
from assistente.strumenti import crea_registro
from conftest import ProviderFinto, risposta_finta


def continua(nota):
    return json.dumps({"stato": "continua", "nota": nota, "risultato": ""})


def completato(risultato, nota="finito"):
    return json.dumps({"stato": "completato", "nota": nota, "risultato": risultato})


APPROVATO = '{"approvato": true, "motivo": "soddisfa l\'obiettivo"}'
RESPINTO = '{"approvato": false, "motivo": "manca il secondo file"}'


@pytest.fixture
def crea_loop(tmp_path):
    """Costruisce un loop con un fornitore finto e senza attese reali."""

    def crea(risposte, **opzioni):
        provider = ProviderFinto(risposte)
        opzioni.setdefault("file_stato", tmp_path / "stato" / "loop.json")
        opzioni.setdefault("pausa", lambda _secondi: None)
        loop = LoopAutonomo(provider, crea_registro(tmp_path / "area"), **opzioni)
        return loop, provider

    return crea


# --- Il percorso normale --------------------------------------------------

def test_lavora_per_piu_iterazioni_fino_al_completamento(crea_loop):
    loop, _ = crea_loop([continua("letto il primo file"), completato("Riepilogo finale"), APPROVATO])

    stato = loop.esegui("riassumi i file")

    assert stato.esito == "completato"
    assert stato.risultato == "Riepilogo finale"
    assert stato.iterazione == 2
    assert stato.richieste == 3  # due iterazioni più la verifica


def test_le_note_sono_la_memoria_tra_un_iterazione_e_l_altra(crea_loop):
    loop, provider = crea_loop([continua("letto nota.txt: parla di latte"), completato("ok"), APPROVATO])

    loop.esegui("riassumi i file")

    seconda = provider.richieste[1]["messaggi"]
    # Contesto nuovo: un solo messaggio, non la conversazione precedente...
    assert len(seconda) == 1
    # ...ma con dentro ciò che l'iterazione prima aveva annotato.
    assert "letto nota.txt: parla di latte" in seconda[0]["content"]


def test_gli_strumenti_che_chiedono_conferma_non_sono_disponibili(crea_loop):
    loop, provider = crea_loop([completato("ok"), APPROVATO])

    loop.esegui("obiettivo")

    nomi = {s.nome for s in provider.richieste[0]["strumenti"]}
    assert "leggi_file" in nomi
    assert nomi.isdisjoint({"scrivi_file", "elimina_file", "esegui_python"})


def test_durante_un_iterazione_l_agente_puo_usare_gli_strumenti(crea_loop, tmp_path):
    (tmp_path / "area").mkdir()
    (tmp_path / "area" / "nota.txt").write_text("Comprare il latte", encoding="utf-8")
    chiede = risposta_finta(testo="", chiamate=[ChiamataStrumento("c1", "leggi_file", {"percorso": "nota.txt"})])
    loop, provider = crea_loop([chiede, completato("La nota dice di comprare il latte"), APPROVATO])

    stato = loop.esegui("cosa dice la nota?")

    assert stato.esito == "completato"
    assert provider.richieste[1]["messaggi"][-1]["content"] == "Comprare il latte"


# --- La verifica del risultato --------------------------------------------

def test_un_risultato_respinto_non_chiude_il_lavoro(crea_loop):
    loop, provider = crea_loop(
        [completato("riepilogo parziale"), RESPINTO, completato("riepilogo completo"), APPROVATO]
    )

    stato = loop.esegui("riassumi tutti i file")

    assert stato.esito == "completato"
    assert stato.risultato == "riepilogo completo"
    # Il motivo del rifiuto arriva all'iterazione successiva.
    assert "manca il secondo file" in provider.richieste[2]["messaggi"][0]["content"]


@pytest.mark.parametrize("verifica", ["non saprei dire", '{"approvato": "forse"}', ErroreAI("guasto")])
def test_senza_un_si_esplicito_il_risultato_non_e_approvato(crea_loop, verifica):
    loop, _ = crea_loop([completato("fatto"), verifica], max_iterazioni=1)

    assert loop.esegui("obiettivo").esito == "fermato"


# --- I criteri di arresto -------------------------------------------------

def test_si_ferma_al_massimo_di_iterazioni(crea_loop):
    loop, provider = crea_loop([continua(f"passo {n}") for n in range(10)], max_iterazioni=3)

    stato = loop.esegui("obiettivo senza fine")

    assert (stato.esito, stato.iterazione) == ("fermato", 3)
    assert "iterazioni" in stato.motivo
    assert len(provider.richieste) == 3


def test_si_ferma_al_budget_di_richieste(crea_loop):
    loop, _ = crea_loop([continua(f"passo {n}") for n in range(10)], max_richieste=2)

    stato = loop.esegui("obiettivo")

    assert stato.esito == "fermato" and "budget" in stato.motivo
    assert stato.richieste == 2


def test_si_ferma_allo_scadere_del_tempo(crea_loop):
    adesso = [0.0]

    def orologio():
        adesso[0] += 40  # ogni lettura dell'orologio "passano" 40 secondi
        return adesso[0]

    loop, _ = crea_loop([continua(f"passo {n}") for n in range(10)], max_secondi=100, orologio=orologio)

    stato = loop.esegui("obiettivo")

    assert stato.esito == "fermato" and "tempo" in stato.motivo
    assert stato.iterazione == 2


def test_si_ferma_se_l_agente_gira_a_vuoto(crea_loop):
    loop, _ = crea_loop([continua("sto pensando")] * 10)

    stato = loop.esegui("obiettivo")

    assert stato.esito == "fermato" and "senza progressi" in stato.motivo
    assert stato.iterazione == 3  # la prima nota è nuova, le due successive sono ripetizioni


def test_si_ferma_se_l_agente_non_rispetta_il_formato(crea_loop):
    loop, _ = crea_loop(["testo libero", "ancora testo libero", continua("troppo tardi")])

    stato = loop.esegui("obiettivo")

    assert stato.esito == "fermato" and stato.iterazione == 2


# --- Errori del fornitore -------------------------------------------------

def troppe_richieste():
    errore = ErroreAI("Limite di richieste raggiunto")
    errore.riprovabile = True
    return errore


def test_se_il_fornitore_e_al_limite_aspetta_e_riprova(crea_loop):
    attese = []
    loop, _ = crea_loop([troppe_richieste(), completato("ok"), APPROVATO], pausa=attese.append)

    stato = loop.esegui("obiettivo")

    assert stato.esito == "completato"
    assert attese == [30]


def test_un_errore_non_riprovabile_non_fa_crollare_il_loop(crea_loop):
    loop, _ = crea_loop([ErroreAI("richiesta malformata"), completato("ok"), APPROVATO])

    stato = loop.esegui("obiettivo")

    assert stato.esito == "completato"
    assert stato.iterazione == 2


# --- Stato su disco e ripresa ---------------------------------------------

def test_lo_stato_viene_salvato_a_ogni_iterazione(crea_loop, tmp_path):
    loop, _ = crea_loop([continua("primo passo")], max_iterazioni=1)

    loop.esegui("obiettivo")

    salvato = StatoLoop.carica(tmp_path / "stato" / "loop.json")
    assert salvato.note == ["primo passo"]
    assert salvato.esito == "fermato"


def test_un_lavoro_interrotto_riprende_da_dove_era_rimasto(crea_loop):
    primo, _ = crea_loop([continua("letto il file A")], max_iterazioni=1)
    primo.esegui("riassumi A e B")

    secondo, provider = crea_loop([completato("riepilogo di A e B"), APPROVATO])
    stato = secondo.esegui(riprendi=True)

    assert stato.esito == "completato"
    assert stato.iterazione == 2  # prosegue il conteggio, non riparte da zero
    assert "letto il file A" in provider.richieste[0]["messaggi"][0]["content"]
    assert "riassumi A e B" in provider.richieste[0]["messaggi"][0]["content"]


def test_riprendere_un_lavoro_gia_finito_non_fa_nulla(crea_loop):
    primo, _ = crea_loop([completato("fatto"), APPROVATO])
    primo.esegui("obiettivo")

    secondo, provider = crea_loop([])
    stato = secondo.esegui(riprendi=True)

    assert stato.esito == "completato"
    assert provider.richieste == []


# --- I controlli della tappa 2 --------------------------------------------

def test_un_obiettivo_fuori_ambito_non_parte_nemmeno(tmp_path):
    provider = ProviderFinto(['{"ambito": "fuori", "motivo": "è cucina"}'])
    loop = LoopAutonomo(
        provider,
        crea_registro(tmp_path / "area"),
        Guardia(provider, ambito="programmazione"),
        file_stato=tmp_path / "loop.json",
    )

    stato = loop.esegui("trova la ricetta migliore della carbonara")

    assert stato.esito == "fermato" and "bloccato" in stato.motivo
    assert stato.iterazione == 0
    assert len(provider.richieste) == 1  # solo il giudice


def test_le_iterazioni_non_ripassano_dal_filtro_di_ambito(tmp_path):
    """L'obiettivo è già stato approvato: giudicare ogni iterazione raddoppierebbe le richieste."""
    provider = ProviderFinto(['{"ambito": "dentro", "motivo": "ok"}', completato("fatto"), APPROVATO])
    loop = LoopAutonomo(
        provider,
        crea_registro(tmp_path / "area"),
        Guardia(provider, ambito="programmazione"),
        file_stato=tmp_path / "loop.json",
    )

    stato = loop.esegui("elenca i file")

    assert stato.esito == "completato"
    assert len(provider.richieste) == 3  # giudice, un'iterazione, verifica
