"""Gli strumenti dell'agente: confinamento, permessi e validazione."""

import pytest

from assistente.provider import ChiamataStrumento
from assistente.strumenti import ErroreStrumento, Registro, Strumento, crea_registro
from assistente.strumenti.file import risolvi
from assistente.strumenti.utili import calcola


@pytest.fixture
def area(tmp_path):
    cartella = tmp_path / "area"
    cartella.mkdir()
    (cartella / "nota.txt").write_text("Comprare il latte\nChiamare Mario", encoding="utf-8")
    (cartella / "sotto").mkdir()
    (cartella / "sotto" / "dati.csv").write_text("nome,eta\nMario,40", encoding="utf-8")
    # Un file FUORI dall'area, che l'agente non deve mai raggiungere.
    (tmp_path / "segreto.txt").write_text("password: 1234", encoding="utf-8")
    return cartella


@pytest.fixture
def registro(area):
    return crea_registro(area)


def chiama(registro, nome, conferma=None, **argomenti):
    return registro.esegui(ChiamataStrumento("id-1", nome, argomenti), conferma)


def si(_strumento, _argomenti):
    return True


def no(_strumento, _argomenti):
    return False


# --- Confinamento nell'area di lavoro -------------------------------------

@pytest.mark.parametrize(
    "percorso",
    ["../segreto.txt", "sotto/../../segreto.txt", "C:/Windows/win.ini", "/etc/passwd"],
)
def test_i_percorsi_fuori_dall_area_sono_rifiutati(area, percorso):
    with pytest.raises(ErroreStrumento, match="fuori dall'area"):
        risolvi(area, percorso)


def test_i_percorsi_dentro_l_area_sono_accettati(area):
    assert risolvi(area, "sotto/dati.csv") == (area / "sotto" / "dati.csv").resolve()
    # ".." è lecito se alla fine si resta dentro.
    assert risolvi(area, "sotto/../nota.txt") == (area / "nota.txt").resolve()


def test_leggere_fuori_dall_area_restituisce_un_errore_al_modello(registro):
    risultato = chiama(registro, "leggi_file", percorso="../segreto.txt")

    assert risultato.errore
    assert "1234" not in risultato.contenuto


# --- Strumenti liberi -----------------------------------------------------

def test_elenca_file(registro):
    contenuto = chiama(registro, "elenca_file").contenuto

    assert "nota.txt" in contenuto
    assert "sotto/" in contenuto


def test_leggi_file(registro):
    assert chiama(registro, "leggi_file", percorso="nota.txt").contenuto.startswith("Comprare il latte")


def test_cerca_testo_indica_file_e_riga(registro):
    assert chiama(registro, "cerca_testo", testo="mario").contenuto.splitlines() == [
        "nota.txt:2: Chiamare Mario",
        "sotto/dati.csv:2: Mario,40",
    ]


@pytest.mark.parametrize(
    "espressione, atteso",
    [("2 + 3 * 4", "14"), ("(10 - 4) / 3", "2.0"), ("2 ** 10", "1024"), ("-7 % 3", "2")],
)
def test_calcola(espressione, atteso):
    assert calcola(espressione) == atteso


@pytest.mark.parametrize(
    "espressione",
    ["__import__('os').system('dir')", "open('x')", "a + 1", "9 ** 9 ** 9", "1 / 0", "2 +"],
)
def test_calcola_rifiuta_tutto_cio_che_non_e_aritmetica(espressione):
    with pytest.raises(ErroreStrumento):
        calcola(espressione)


# --- Strumenti che chiedono conferma --------------------------------------

def test_scrivere_senza_conferma_non_scrive(registro, area):
    risultato = chiama(registro, "scrivi_file", conferma=no, percorso="nuovo.txt", contenuto="ciao")

    assert risultato.errore
    assert "non autorizzata" in risultato.contenuto
    assert not (area / "nuovo.txt").exists()


def test_senza_nessuno_a_cui_chiedere_la_risposta_e_no(registro, area):
    risultato = chiama(registro, "scrivi_file", percorso="nuovo.txt", contenuto="ciao")

    assert risultato.errore
    assert not (area / "nuovo.txt").exists()


def test_scrivere_con_conferma_scrive(registro, area):
    risultato = chiama(registro, "scrivi_file", conferma=si, percorso="nuovo.txt", contenuto="ciao")

    assert not risultato.errore
    assert (area / "nuovo.txt").read_text(encoding="utf-8") == "ciao"


def test_la_conferma_riceve_cosa_sta_per_succedere(registro):
    viste = []

    def annota(strumento, argomenti):
        viste.append(strumento.anteprima(**argomenti))
        return False

    chiama(registro, "scrivi_file", conferma=annota, percorso="a.txt", contenuto="contenuto nuovo")

    assert "a.txt" in viste[0] and "contenuto nuovo" in viste[0]


def test_eliminare_con_conferma_elimina(registro, area):
    chiama(registro, "elimina_file", conferma=si, percorso="nota.txt")

    assert not (area / "nota.txt").exists()


def test_esegui_python_restituisce_l_output(registro, area):
    (area / "saluta.py").write_text("print('ciao dal file')", encoding="utf-8")

    risultato = chiama(registro, "esegui_python", conferma=si, percorso="saluta.py")

    assert "ciao dal file" in risultato.contenuto
    assert "Codice di uscita: 0" in risultato.contenuto


def test_uno_script_troppo_lento_viene_interrotto(area):
    from assistente.strumenti.python import crea_strumento_python

    (area / "lento.py").write_text("import time; time.sleep(30)", encoding="utf-8")
    registro = Registro([crea_strumento_python(area, tempo_massimo=1)])

    risultato = chiama(registro, "esegui_python", conferma=si, percorso="lento.py")

    assert risultato.errore
    assert "superato 1 secondi" in risultato.contenuto


# --- Il registro: validare ciò che scrive il modello ----------------------

def test_strumento_sconosciuto(registro):
    assert "sconosciuto" in chiama(registro, "formatta_disco").contenuto


def test_argomento_obbligatorio_mancante(registro):
    assert "Manca l'argomento obbligatorio 'percorso'" in chiama(registro, "leggi_file").contenuto


def test_argomento_non_previsto(registro):
    assert "non previsto" in chiama(registro, "leggi_file", percorso="nota.txt", forza=True).contenuto


def test_argomento_di_tipo_sbagliato(registro):
    assert "deve essere di tipo string" in chiama(registro, "leggi_file", percorso=42).contenuto


def test_argomenti_illeggibili(registro):
    risultato = registro.esegui(ChiamataStrumento("id-1", "leggi_file", None))

    assert risultato.errore and "non leggibili" in risultato.contenuto


def test_un_guasto_dello_strumento_diventa_un_errore_per_il_modello():
    def rotto():
        raise RuntimeError("dettaglio interno da non mostrare")

    registro = Registro([Strumento("rotto", "si rompe", {"type": "object", "properties": {}}, rotto)])

    risultato = chiama(registro, "rotto")

    assert risultato.errore
    assert "dettaglio interno" not in risultato.contenuto


def test_un_risultato_enorme_viene_tagliato():
    registro = Registro(
        [Strumento("fiume", "tanto testo", {"type": "object", "properties": {}}, lambda: "x" * 50_000)]
    )

    contenuto = chiama(registro, "fiume").contenuto

    assert len(contenuto) < 5000
    assert contenuto.endswith("[... risultato tagliato ...]")
