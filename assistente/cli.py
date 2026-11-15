"""Interfaccia a riga di comando: legge la domanda, mostra la risposta."""

import sys

from . import config
from .provider import ErroreAI, crea_provider
from .sessione import Sessione
from .sicurezza import RichiestaBloccata, crea_guardia
from .strumenti import crea_registro

AIUTO = "Comandi: /costo  /nuovo  /strumenti  /esci"


def stampa_frammento(testo: str) -> None:
    print(testo, end="", flush=True)


def stampa_strumento(chiamata, risultato) -> None:
    esito = "ERRORE: " + risultato.contenuto if risultato.errore else "ok"
    print(f"\n  [strumento {chiamata.nome} {chiamata.argomenti}: {esito[:120]}]")


def chiedi_conferma(strumento, argomenti) -> bool:
    """Mostra all'utente cosa sta per succedere e aspetta il suo sì."""
    dettaglio = strumento.anteprima(**argomenti) if strumento.anteprima else str(argomenti)
    print(f"\n--- L'assistente chiede di usare '{strumento.nome}' ---")
    print(dettaglio[:1500])
    print("---")
    try:
        # Qualunque risposta diversa da "s" vale no.
        return input("Confermi? [s/N] ").strip().lower() == "s"
    except (EOFError, KeyboardInterrupt):
        return False


def main() -> None:
    # Il terminale di Windows non sempre usa UTF-8: lo forziamo per gli accenti.
    sys.stdout.reconfigure(encoding="utf-8")

    try:
        provider = crea_provider()
    except ErroreAI as errore:
        print(errore)
        return
    registro = crea_registro()
    sessione = Sessione(provider, crea_guardia(provider), registro, chiedi_conferma)

    print(f"Assistente pronto ({config.PROVIDER}, modello: {config.MODELLO}). {AIUTO}")
    print(f"Ambito: {config.AMBITO or 'libero (filtro spento)'}")
    print(f"Area di lavoro: {config.AREA_LAVORO}")

    while True:
        try:
            domanda = input("\nTu> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not domanda:
            continue
        if domanda == "/esci":
            break
        if domanda == "/nuovo":
            sessione.azzera()
            print("Conversazione azzerata.")
            continue
        if domanda == "/costo":
            print(sessione.riepilogo())
            continue
        if domanda == "/strumenti":
            for strumento in registro.definizioni():
                print(f"  {strumento.nome:<15} [{strumento.permesso}]  {strumento.descrizione}")
            continue
        if domanda.startswith("/"):
            print(AIUTO)
            continue

        print("\nAI> ", end="", flush=True)
        try:
            risposta = sessione.invia(domanda, stampa_frammento, stampa_strumento)
        except RichiestaBloccata as blocco:
            print(f"[Bloccata] {blocco}")
            continue
        except KeyboardInterrupt:
            print("\n[Interrotto]")
            continue
        except ErroreAI as errore:
            print(f"\n{errore}")
            continue
        print()

        if sessione.dati_mascherati:
            print(f"[Mascherati prima dell'invio: {', '.join(sessione.dati_mascherati)}]")
        for avviso in sessione.avvisi:
            print(f"[Avviso: {avviso}]")
        if risposta.esito == "rifiuto":
            print("[Il modello ha rifiutato la richiesta: non la tengo in cronologia.]")
        elif risposta.esito == "troncata":
            print("[Risposta troncata: raggiunto il limite di token.]")
