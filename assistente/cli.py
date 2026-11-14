"""Interfaccia a riga di comando: legge la domanda, mostra la risposta."""

import sys

from . import config
from .provider import ErroreAI, costo_in_dollari, crea_provider

AIUTO = "Comandi: /costo  /nuovo  /esci"


def main() -> None:
    # Il terminale di Windows non sempre usa UTF-8: lo forziamo per gli accenti.
    sys.stdout.reconfigure(encoding="utf-8")

    try:
        provider = crea_provider()
    except ErroreAI as errore:
        print(errore)
        return

    # La cronologia vive qui, nel nostro programma: è questa la "memoria".
    messaggi: list = []
    token_ingresso = 0
    token_uscita = 0
    spesa = 0.0

    print(f"Assistente pronto ({config.PROVIDER}, modello: {config.MODELLO}). {AIUTO}")

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
            messaggi.clear()
            print("Conversazione azzerata.")
            continue
        if domanda == "/costo":
            print(
                f"Token in ingresso: {token_ingresso} · in uscita: {token_uscita} · "
                f"spesa stimata: ${spesa:.4f}"
            )
            continue
        if domanda.startswith("/"):
            print(AIUTO)
            continue

        messaggi.append({"role": "user", "content": domanda})
        print("\nAI> ", end="", flush=True)

        try:
            risposta = provider.chiedi(
                messaggi, lambda testo: print(testo, end="", flush=True)
            )
        except KeyboardInterrupt:
            print("\n[Interrotto]")
            messaggi.pop()
            continue
        except ErroreAI as errore:
            print(f"\n{errore}")
            messaggi.pop()
            continue
        print()

        # Il costo si paga anche se la risposta viene rifiutata o troncata.
        token_ingresso += risposta.token_ingresso
        token_uscita += risposta.token_uscita
        spesa += costo_in_dollari(
            risposta.modello, risposta.token_ingresso, risposta.token_uscita
        )

        if risposta.esito == "rifiuto":
            print("[Il modello ha rifiutato la richiesta: non la tengo in cronologia.]")
            messaggi.pop()
            continue
        if risposta.esito == "troncata":
            print("[Risposta troncata: raggiunto il limite di token.]")

        # Alla prossima domanda il modello riceverà anche questa risposta.
        messaggi.append(risposta.messaggio)
