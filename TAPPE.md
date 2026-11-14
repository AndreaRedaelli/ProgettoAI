# Percorso AI Engineering — le tappe

Un unico progetto: un assistente da riga di comando che a ogni tappa guadagna
una capacità nuova. Regola di fondo: **niente framework** fino alla tappa 4,
così i concetti restano visibili nel nostro codice.

## Regola valida per tutte le tappe: il fornitore di AI si sceglie

L'assistente non è legato a una sola AI. La variabile d'ambiente
`AI_PROVIDER` (nel file `.env`) decide quale usare:

| Valore | Fornitore | Costo | Chiave richiesta |
|---|---|---|---|
| `groq` (predefinito) | Groq, modelli open source | piano gratuito con limiti giornalieri | `GROQ_API_KEY` |
| `anthropic` | Anthropic, modelli Claude | a consumo | `ANTHROPIC_API_KEY` |

Se `AI_PROVIDER` manca, vale `groq`. `MODELLO` è facoltativa: se manca, ogni
fornitore usa il suo modello predefinito.

Come è fatto: tutto ciò che dipende dal fornitore sta in
`assistente/provider/`, un file per fornitore. Il resto del programma vede
solo una forma comune (`chiedi(...)` che restituisce una `Risposta`), quindi
**ogni capacità aggiunta nelle tappe successive deve funzionare con entrambi
i fornitori**. Aggiungere un terzo fornitore significa aggiungere un file lì,
senza toccare il resto.

---

Ogni tappa si chiude quando: il codice funziona, hai provato a romperlo, e
c'è un commit git.

Stato: ⬜ da fare · 🔄 in corso · ✅ fatta

---

## 🔄 Tappa 1 — Chat via API

**Cosa costruiamo:** fai una domanda dal terminale e ricevi la risposta in
streaming, con la cronologia della conversazione.

**Concetti da imparare**
- L'API è senza memoria: a ogni richiesta rimandiamo tutta la conversazione.
- Ruoli dei messaggi (`user`, `assistant`) e system prompt.
- Streaming: mostrare la risposta mentre viene generata.
- Token in ingresso e in uscita, e come diventano un costo.
- `stop_reason`: perché il modello si è fermato.
- Errori dell'API (chiave errata, limiti di frequenza, rete) e retry.
- Astrazione del fornitore: le API si somigliano ma non sono uguali (dove va
  il system prompt, che forma ha la risposta, come si contano i token).

**Fatto quando**
- [ ] `python -m assistente` apre la chat e risponde in streaming con Groq
- [ ] con `AI_PROVIDER=anthropic` la stessa chat funziona senza altre modifiche
- [ ] un valore sconosciuto di `AI_PROVIDER` produce un messaggio chiaro
- [ ] la seconda domanda può riferirsi alla prima (la cronologia funziona)
- [ ] `/costo` mostra token e spesa stimata della sessione
- [ ] una chiave API sbagliata produce un messaggio chiaro, non un crash

**Esperimenti per capire**
- Commenta la riga che aggiunge la risposta alla cronologia: cosa succede?
- Cambia il system prompt in `config.py` e osserva come cambia il tono.
- Cambia `AI_PROVIDER` e `MODELLO` nel file `.env` e confronta qualità, velocità e costo.
- Confronta `groq_provider.py` e `anthropic_provider.py`: cosa cambia davvero tra le due API?

---

## ⬜ Tappa 2 — Controlli di sicurezza

**Cosa costruiamo:** uno strato che ogni richiesta e ogni risposta deve
attraversare prima di proseguire.

**Concetti da imparare**
- I controlli stanno fuori da `provider/`: valgono per qualunque fornitore.
- Controlli in ingresso: lunghezza massima, limite di richieste, tetto di spesa.
- Mascheramento di dati sensibili (email, chiavi, numeri di carta) prima dell'invio.
- Prompt injection: cos'è, come si rileva, perché non si elimina del tutto.
- Controlli in uscita: risposta validata con uno schema (structured output).
- Log di audit: chi ha chiesto cosa, quando, e cosa è stato bloccato.
- **Evals**: un insieme di domande di prova (anche ostili) da rilanciare a ogni modifica.

**Fatto quando**
- [ ] una richiesta troppo lunga o oltre budget viene rifiutata con un motivo
- [ ] i dati sensibili vengono mascherati prima di lasciare il computer
- [ ] ogni richiesta lascia una riga nel log di audit
- [ ] esiste una prima suite di evals che si lancia con un comando

---

## ⬜ Tappa 3 — Agente

**Cosa costruiamo:** diamo al modello degli strumenti (leggere file, cercare,
eseguire comandi) e scriviamo a mano il ciclo: il modello chiede uno
strumento → lo eseguiamo → gli restituiamo il risultato → ripete.

**Concetti da imparare**
- Tool use: come si descrive uno strumento al modello (nome, descrizione, schema).
- Uno strumento si definisce una volta sola; ogni fornitore lo traduce nel
  proprio formato. Prima verifica: il modello gratuito di Groq li usa bene?
- Il ciclo agentico: `while stop_reason == "tool_use"`.
- Chiamate a strumenti in parallelo e gestione degli errori degli strumenti.
- Conferma umana per le azioni rischiose.
- Confinamento: l'agente lavora solo dentro una cartella.
- I controlli della tappa 2 applicati a ogni chiamata di strumento.

**Fatto quando**
- [ ] l'agente risponde a "quanti file Python ci sono qui?" usando gli strumenti, con entrambi i fornitori
- [ ] un comando rischioso chiede conferma prima di partire
- [ ] un percorso fuori dalla cartella di lavoro viene rifiutato
- [ ] le evals coprono anche l'uso degli strumenti

---

## ⬜ Tappa 4 — Plugin

**Cosa costruiamo:** gli strumenti diventano estendibili senza toccare il nucleo.

**Concetti da imparare**
- Un registro di plugin fatto da noi: aggiungi un file, compare uno strumento.
- MCP (Model Context Protocol), lo standard per collegare strumenti esterni.
- Collegare un server MCP esistente.
- Scrivere un nostro server MCP.
- Fiducia: un plugin è codice altrui, quindi permessi e controlli per plugin.

**Fatto quando**
- [ ] aggiungere uno strumento non richiede modifiche al ciclo dell'agente
- [ ] l'assistente usa strumenti di un server MCP esterno
- [ ] un nostro server MCP funziona anche da altri client

---

## ⬜ Tappa 5 — Loop

**Cosa costruiamo:** dai un obiettivo e l'agente lavora in autonomia:
pianifica, agisce, verifica, ripete finché non ha finito.

**Concetti da imparare**
- Differenza tra ciclo agentico (tappa 3, un turno) e loop autonomo (molti turni).
- Criteri di arresto: obiettivo raggiunto, budget finito, nessun progresso.
- Con Groq il budget è il numero di richieste al giorno, con Anthropic è la spesa.
- Verifica del risultato: chi decide che il lavoro è fatto bene?
- Stato salvato su disco tra un'iterazione e l'altra, per riprendere.
- Gestione del contesto che cresce (riassunti, compattazione).
- Esecuzioni pianificate (per esempio ogni mattina).

**Fatto quando**
- [ ] l'agente porta a termine un obiettivo in più iterazioni senza intervento
- [ ] si ferma da solo quando finisce il budget o non fa progressi
- [ ] un'esecuzione interrotta riprende da dove era rimasta

---

## Fili che attraversano tutte le tappe

- **Evals** — misurare prima di cambiare, dalla tappa 2 in poi.
- **Costi** — sapere sempre quanto costa una richiesta.
- **Osservabilità** — poter ricostruire cosa è successo e perché.
