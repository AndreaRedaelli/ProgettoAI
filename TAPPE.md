# Percorso AI Engineering — le tappe

Un unico progetto: un assistente che a ogni tappa guadagna una capacità nuova.
Regola di fondo: **niente framework**, così i concetti restano visibili nel
nostro codice.

La spiegazione tecnica di ogni tappa è in [docs/DOCUMENTAZIONE.md](docs/DOCUMENTAZIONE.md).

Stato: ⬜ da fare · 🔄 in corso · ✅ fatta

## Regole valide per tutte le tappe

### Ogni tappa ha il suo branch

| Tappa | Branch |
|---|---|
| 1 | `tappa-1-chat` |
| 2 | `tappa-2-sicurezza` |
| 3 | `tappa-3-agente` |
| 4 | `tappa-4-plugin` |
| 5 | `tappa-5-loop` |
| 6 | `tappa-6-interfaccia` |

I branch sono a catena: ognuno parte dal precedente. `main` contiene la base
e la documentazione; le tappe si uniscono a `main` dopo averle studiate.

### Ogni tappa ha i suoi test

Una tappa è chiusa quando:

- il codice funziona con il modello vero;
- i test automatici passano (`pytest`), senza rete e senza costi, grazie a un
  fornitore finto;
- la sua sezione nella documentazione tecnica è aggiornata.

### Il fornitore di AI si sceglie

L'assistente non è legato a una sola AI. La variabile d'ambiente
`AI_PROVIDER` (nel file `.env`) decide quale usare:

| Valore | Fornitore | Costo | Chiave richiesta |
|---|---|---|---|
| `groq` (predefinito) | Groq, modelli open source | piano gratuito con limiti giornalieri | `GROQ_API_KEY` |
| `anthropic` | Anthropic, modelli Claude | a consumo | `ANTHROPIC_API_KEY` |

Se `AI_PROVIDER` manca, vale `groq`. `MODELLO` è facoltativa: se manca, ogni
fornitore usa il suo modello predefinito.

Tutto ciò che dipende dal fornitore sta in `assistente/provider/`, un file per
fornitore. **Ogni capacità aggiunta nelle tappe successive deve funzionare con
entrambi i fornitori.**

---

## ✅ Tappa 1 — Chat via API

**Cosa costruiamo:** fai una domanda dal terminale e ricevi la risposta in
streaming, con la cronologia della conversazione.

**Concetti da imparare**
- L'API è senza memoria: a ogni richiesta rimandiamo tutta la conversazione.
- Ruoli dei messaggi (`user`, `assistant`) e system prompt.
- Streaming: mostrare la risposta mentre viene generata.
- Token in ingresso e in uscita, e come diventano un costo.
- Perché il modello si è fermato (fine, troncata, rifiuto).
- Errori dell'API (chiave errata, limiti di frequenza, rete).
- Astrazione del fornitore: le API si somigliano ma non sono uguali.
- Come si testa codice che chiama un'AI senza chiamarla davvero.

**Fatto quando**
- [x] `python -m assistente` apre la chat e risponde in streaming con Groq
- [x] la seconda domanda può riferirsi alla prima (la cronologia funziona)
- [ ] con `AI_PROVIDER=anthropic` la stessa chat funziona senza altre modifiche (coperto dai test, da provare con una chiave vera)
- [x] `/costo` mostra token e spesa stimata della sessione
- [x] chiave mancante, chiave errata o fornitore sconosciuto danno un messaggio chiaro
- [x] i test passano

**Esperimenti per capire**
- Commenta la riga che aggiunge la risposta alla cronologia: cosa succede?
- Cambia il system prompt in `config.py` e osserva come cambia il tono.
- Confronta `groq_provider.py` e `anthropic_provider.py`: cosa cambia davvero tra le due API?

---

## ✅ Tappa 2 — Controlli di sicurezza

**Cosa costruiamo:** uno strato che ogni richiesta deve attraversare prima di
arrivare al modello. In particolare un **filtro di ambito**: l'assistente ha
una funzione prevista, e le richieste che ne escono vengono bloccate.

**Concetti da imparare**
- I controlli stanno fuori da `provider/`: valgono per qualunque fornitore.
- Controlli a strati, dal più economico al più costoso.
- Limiti: lunghezza della domanda, richieste al minuto, tetto per sessione.
- Mascheramento di dati sensibili (email, chiavi, carte) prima dell'invio.
- Prompt injection: cos'è, come si riconosce, perché non si elimina del tutto.
- Filtro di ambito con un modello che fa da giudice, e risposta del giudice
  validata con uno schema.
- "Fail closed": se un controllo non riesce a decidere, si blocca.
- Log di audit: cosa è stato chiesto, quando, e cosa è stato bloccato.
- **Evals**: domande di prova (anche ostili) da rilanciare a ogni modifica.

**Fatto quando**
- [x] una richiesta troppo lunga o oltre i limiti viene rifiutata con un motivo
- [x] i dati sensibili vengono mascherati prima di lasciare il computer
- [x] una richiesta fuori ambito viene bloccata, una dentro passa
- [x] un tentativo di prompt injection viene bloccato
- [x] ogni richiesta lascia una riga nel log di audit
- [x] i test passano e le evals si lanciano con un comando

---

## ✅ Tappa 3 — Agente

**Cosa costruiamo:** diamo al modello degli strumenti e scriviamo a mano il
ciclo: il modello chiede uno strumento → lo eseguiamo → gli restituiamo il
risultato → ripete.

**Concetti da imparare**
- Tool use: come si descrive uno strumento al modello (nome, descrizione, schema).
- Uno strumento si definisce una volta sola; ogni fornitore lo traduce nel
  proprio formato.
- Il ciclo agentico: continua finché il modello chiede strumenti.
- Gestione degli errori degli strumenti: l'errore torna al modello, non all'utente.
- Confinamento: l'agente lavora solo dentro la cartella `area_lavoro/`.
- Permessi: azioni libere, azioni che chiedono conferma, azioni vietate.
- I controlli della tappa 2 applicati anche a ciò che gli strumenti restituiscono.

**Fatto quando**
- [x] l'agente risponde a una domanda sui file usando gli strumenti (provato con Groq; Anthropic coperto dai test)
- [x] un'azione che modifica qualcosa chiede conferma prima di partire
- [x] un percorso fuori da `area_lavoro/` viene rifiutato
- [x] i test coprono il ciclo e ogni strumento

---

## ✅ Tappa 4 — Plugin

**Cosa costruiamo:** gli strumenti diventano estendibili senza toccare il nucleo.

**Concetti da imparare**
- Un registro di plugin fatto da noi: aggiungi un file, compare uno strumento.
- MCP (Model Context Protocol), lo standard per collegare strumenti esterni.
- Collegare un server MCP esistente.
- Scrivere un nostro server MCP.
- Fiducia: un plugin è codice altrui, quindi permessi e controlli per plugin.

**Fatto quando**
- [x] aggiungere uno strumento non richiede modifiche al ciclo dell'agente
- [x] l'assistente usa strumenti di un server MCP esterno
- [ ] un nostro server MCP funziona anche da altri client (è un server standard, ma provato solo con il nostro client)
- [x] i test passano

---

## ✅ Tappa 5 — Loop

**Cosa costruiamo:** dai un obiettivo e l'agente lavora in autonomia:
pianifica, agisce, verifica, ripete finché non ha finito.

**Concetti da imparare**
- Differenza tra ciclo agentico (tappa 3, un turno) e loop autonomo (molti turni).
- Criteri di arresto: obiettivo raggiunto, budget finito, nessun progresso.
- Con Groq il budget è il numero di richieste, con Anthropic è la spesa.
- Senza un umano che conferma, gli strumenti rischiosi restano spenti.
- Verifica del risultato: chi decide che il lavoro è fatto bene?
- Stato salvato su disco tra un'iterazione e l'altra, per riprendere.
- Gestione del contesto che cresce.

**Fatto quando**
- [x] l'agente porta a termine un obiettivo in più iterazioni senza intervento
- [x] si ferma da solo quando finisce il budget o non fa progressi
- [x] un'esecuzione interrotta riprende da dove era rimasta
- [x] i test passano

---

## ✅ Tappa 6 — Interfaccia grafica

**Cosa costruiamo:** una finestra (Tkinter, inclusa in Python) con una maschera
per scegliere l'AI, inserire la chiave e conversare, al posto del terminale.

**Concetti da imparare**
- Separare logica e interfaccia: la stessa sessione serve terminale e finestra.
- Streaming in una finestra: la richiesta gira in un thread separato per non
  bloccare l'interfaccia.
- Gestione della chiave: campo mascherato, tenuta in memoria, salvataggio in
  `.env` solo su richiesta.
- Mostrare all'utente i blocchi dei controlli e le richieste di conferma.

**Fatto quando**
- [x] dalla finestra si scelgono fornitore, modello e chiave senza toccare file
- [x] la risposta compare a frammenti e la finestra resta reattiva
- [x] la chiave non viene mai mostrata in chiaro né salvata senza consenso
- [x] i test coprono la logica dietro la finestra

**Da verificare a mano:** l'aspetto della finestra e la finestra di dialogo
delle conferme (i test la guidano da programma, senza guardarla).

---

## Fili che attraversano tutte le tappe

- **Test ed evals** — misurare prima di cambiare.
- **Costi e limiti** — sapere sempre quanto costa una richiesta.
- **Osservabilità** — poter ricostruire cosa è successo e perché.
