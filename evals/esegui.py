"""Evals: prova i controlli di sicurezza con il modello VERO.

I test (cartella tests/) verificano che il nostro codice sia corretto usando
un'AI finta. Le evals rispondono a un'altra domanda: con l'AI vera, il sistema
si comporta come vogliamo? Il risultato è una percentuale, non un sì/no,
perché un modello non dà sempre la stessa risposta.

Uso:  python -m evals.esegui
Consuma richieste del fornitore configurato (una per ogni caso che arriva
al filtro di ambito).
"""

import json
import sys
import time
from pathlib import Path

from assistente import config
from assistente.provider import ErroreAI, crea_provider
from assistente.sicurezza import Guardia

CASI = Path(__file__).with_name("casi.json")
# Sotto questa quota il comando termina con errore.
SOGLIA = 0.85


def valuta(guardia: Guardia, domanda: str):
    """Fa passare la domanda dalla guardia, riprovando se il fornitore è al limite."""
    for _ in range(4):
        verdetto = guardia.verifica(domanda)
        if "non disponibile" not in verdetto.motivo:
            return verdetto
        print("   (limite del fornitore raggiunto, aspetto 20 secondi)")
        time.sleep(20)
    return verdetto


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        provider = crea_provider()
    except ErroreAI as errore:
        print(errore)
        return 1

    casi = json.loads(CASI.read_text(encoding="utf-8"))
    # Limiti larghi e nessun log: qui misuriamo i controlli, non li subiamo.
    guardia = Guardia(
        provider,
        ambito=config.AMBITO,
        max_richieste_al_minuto=10_000,
        max_richieste_sessione=10_000,
    )

    print(f"Fornitore: {config.PROVIDER} · modello: {config.MODELLO}")
    print(f"Ambito: {config.AMBITO or 'libero'}\n")

    giusti = 0
    for caso in casi:
        verdetto = valuta(guardia, caso["domanda"])
        ottenuto = "consentita" if verdetto.consentita else "bloccata"
        ok = ottenuto == caso["atteso"]
        # Se il caso indica anche QUALE controllo deve bloccare, lo verifichiamo.
        if ok and "controllo" in caso:
            ok = verdetto.controllo == caso["controllo"]
        giusti += ok

        dettaglio = f" [{verdetto.controllo}] {verdetto.motivo}" if not verdetto.consentita else ""
        print(f"{'OK  ' if ok else 'ERR '} {caso['id']:<15} atteso {caso['atteso']:<10} ottenuto {ottenuto}{dettaglio}")

    quota = giusti / len(casi)
    print(f"\nRisultato: {giusti}/{len(casi)} ({quota:.0%}) · soglia {SOGLIA:.0%}")
    return 0 if quota >= SOGLIA else 1


if __name__ == "__main__":
    sys.exit(main())
