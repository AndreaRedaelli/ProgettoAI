"""Interfaccia a riga di comando: legge la domanda, mostra la risposta."""

import sys

from . import config
from .provider import ErroreAI, crea_provider
from .sessione import Sessione
from .sicurezza import RichiestaBloccata, crea_guardia

AIUTO = "Comandi: /costo  /nuovo  /esci"


def stampa_frammento(testo: str) -> None:
    print(testo, end="", flush=True)


def main() -> None:
    # Il terminale di Windows non sempre usa UTF-8: lo forziamo per gli accenti.
    sys.stdout.reconfigure(encoding="utf-8")

    try:
        provider = crea_provider()
    except ErroreAI as errore:
        print(errore)
        return
    sessione = Sessione(provider, crea_guardia(provider))

    print(f"Assistente pronto ({config.PROVIDER}, modello: {config.MODELLO}). {AIUTO}")
    print(f"Ambito: {config.AMBITO or 'libero (filtro spento)'}")

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
        if domanda.startswith("/"):
            print(AIUTO)
            continue

        print("\nAI> ", end="", flush=True)
        try:
            risposta = sessione.invia(domanda, stampa_frammento)
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
