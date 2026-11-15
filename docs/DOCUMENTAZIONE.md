# Documentazione tecnica

Questo documento spiega **come è fatto** l'assistente e **perché**. Il percorso
da seguire è in [TAPPE.md](../TAPPE.md), le istruzioni per avviarlo in
[AVVIO.md](../AVVIO.md).

Il documento cresce con il progetto: ogni tappa vive in un branch e aggiorna
la propria sezione qui sotto.

## Come leggere il progetto

| Branch | Contenuto | Stato |
|---|---|---|
| `main` | Base: chat con due fornitori, più questo documento | presente |
| `tappa-1-chat` | Tappa 1 completata, con i test | presente |
| `tappa-2-sicurezza` | Controlli sulle richieste e filtro di ambito | da fare |
| `tappa-3-agente` | Strumenti e ciclo agentico | da fare |
| `tappa-4-plugin` | Plugin e MCP | da fare |
| `tappa-5-loop` | Loop autonomo | da fare |
| `tappa-6-interfaccia` | Interfaccia grafica | da fare |

I branch sono **a catena**: ognuno parte dal precedente. Per vedere che cosa
aggiunge una tappa basta confrontarla con quella prima:

```powershell
git diff tappa-1-chat tappa-2-sicurezza
```

Per studiare una tappa:

```powershell
git switch tappa-2-sicurezza
```

---

## Concetti di base

### L'API è senza memoria

Un modello linguistico non ricorda nulla tra una richiesta e l'altra. La
"conversazione" esiste solo perché il nostro programma conserva la lista dei
messaggi e la rimanda **tutta** a ogni domanda. Conseguenze:

- la memoria è una struttura dati nostra (una lista), non un servizio;
- a ogni turno i token in ingresso aumentano, e con loro il costo;
- possiamo modificarla: azzerarla, accorciarla, riassumerla.

### Messaggi e ruoli

Una conversazione è una lista di messaggi, ciascuno con un ruolo:

| Ruolo | Chi parla |
|---|---|
| `system` | Chi ha scritto il programma: definisce ruolo, tono e regole |
| `user` | L'utente |
| `assistant` | Il modello |

### Token

Il modello non legge caratteri ma token (pezzi di parola). Costi e limiti si
misurano in token, separando quelli in ingresso (ciò che mandiamo) da quelli
in uscita (ciò che il modello scrive), che costano di più.

### Streaming

La risposta arriva a frammenti mentre viene generata. Serve a mostrare subito
il testo invece di aspettare la fine.

---

## Architettura

```
assistente/
├── __main__.py              avvio:  python -m assistente
├── cli.py                   interfaccia a riga di comando, cronologia
├── config.py                impostazioni lette da .env
├── sessione.py              cronologia e contatori (dalla tappa 1)
└── provider/
    ├── __init__.py          sceglie il fornitore (AI_PROVIDER)
    ├── base.py              forma comune: Risposta, ErroreAI
    ├── groq_provider.py     chiamata all'API di Groq
    └── anthropic_provider.py chiamata all'API di Anthropic
```

### Il percorso di una domanda

1. `cli.py` legge la domanda e la aggiunge alla cronologia come messaggio `user`.
2. Chiama `provider.chiedi(messaggi, su_testo)` passando l'intera cronologia.
3. Il fornitore invia la richiesta e, per ogni frammento ricevuto, chiama
   `su_testo`, che lo stampa a schermo.
4. Il fornitore restituisce una `Risposta`.
5. `cli.py` aggiorna token e spesa, poi aggiunge il messaggio del modello alla
   cronologia.

Se qualcosa va storto, la domanda viene tolta dalla cronologia: così la lista
resta sempre un'alternanza valida di `user` e `assistant`.

### L'astrazione del fornitore

Le API di Groq e Anthropic fanno la stessa cosa ma con forme diverse:

| Aspetto | Groq | Anthropic |
|---|---|---|
| System prompt | primo messaggio della lista | parametro separato `system` |
| Risposta in streaming | pezzi con `choices[0].delta.content` | flusso di testo `text_stream` |
| Conteggio token | `prompt_tokens`, `completion_tokens` | `input_tokens`, `output_tokens` |
| Fine risposta | `finish_reason`: `stop`, `length` | `stop_reason`: `end_turn`, `max_tokens`, `refusal` |
| Contenuto della risposta | una stringa | una lista di blocchi |

Tutto ciò che dipende dal fornitore sta in `provider/`. Il resto del programma
vede solo:

- `crea_provider()` — restituisce il fornitore configurato;
- `provider.chiedi(messaggi, su_testo)` — restituisce una `Risposta`;
- `Risposta` — messaggio da mettere in cronologia, modello, token, esito
  (`fine`, `troncata`, `rifiuto`);
- `ErroreAI` — qualunque errore, già tradotto in un messaggio leggibile.

Per aggiungere un terzo fornitore si scrive un file in `provider/` con una
classe che ha `NOME_CHIAVE` e `chiedi(...)`, e si aggiunge un ramo in
`crea_provider()`.

### Configurazione

Tutte le impostazioni sono in `config.py`, che le legge dal file `.env`.

| Variabile | Significato | Predefinito |
|---|---|---|
| `AI_PROVIDER` | Fornitore: `groq` o `anthropic` | `groq` |
| `GROQ_API_KEY` | Chiave di Groq | — |
| `ANTHROPIC_API_KEY` | Chiave di Anthropic | — |
| `MODELLO` | Modello da usare | dipende dal fornitore |
| `EFFORT` | Solo Anthropic: impegno del modello | `medium` |

Le chiavi stanno solo in `.env`, che è escluso da git.

---

## Tappa 1 — Chat via API

Branch `tappa-1-chat`.

### Cosa aggiunge rispetto a `main`

- `assistente/sessione.py`: la conversazione diventa una classe a sé.
- `tests/`: i test automatici.
- I fornitori accettano un client già pronto e la `Risposta` ha anche il campo `testo`.

### La classe `Sessione`

Su `main` cronologia e contatori stavano dentro il ciclo di `cli.py`, mescolati
a `input()` e `print()`. Erano impossibili da provare senza una tastiera.
`Sessione` contiene solo la logica:

| Metodo | Cosa fa |
|---|---|
| `invia(domanda, su_testo)` | Aggiunge la domanda, chiama il fornitore, aggiorna i contatori, aggiunge la risposta |
| `azzera()` | Svuota la cronologia |
| `riepilogo()` | Testo con token e spesa |

`cli.py` ora fa solo due cose: leggere dalla tastiera e stampare. La stessa
`Sessione` servirà la finestra grafica della tappa 6.

Due regole che `invia` garantisce:

- se la richiesta fallisce (errore o `Ctrl+C`), la domanda viene tolta dalla
  cronologia, altrimenti resterebbero due messaggi `user` di fila;
- se il modello rifiuta, la domanda viene tolta ma i token si contano lo
  stesso, perché sono stati consumati.

### Come si testa codice che chiama un'AI

Un'AI vera nei test sarebbe lenta, costosa e darebbe ogni volta risposte
diverse. La soluzione è sostituirla con un oggetto finto che risponde ciò che
decidiamo noi. Lo facciamo a due livelli:

| Cosa proviamo | Cosa sostituiamo | File |
|---|---|---|
| La logica della conversazione | L'intero fornitore, con `ProviderFinto` | `tests/test_sessione.py` |
| La traduzione delle API | Il client dell'SDK, con un oggetto che ne imita i pezzi usati | `tests/test_provider.py` |

Perché questo funzioni il codice deve **ricevere** le sue dipendenze invece
di crearsele: `Sessione(provider)` e `ProviderGroq(client)`. Si chiama
*dependency injection* ed è il motivo per cui i costruttori hanno quei parametri.

Per eseguire i test:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

```powershell
.venv\Scripts\python.exe -m pytest
```

Cosa i test **non** dicono: se il modello vero risponde bene. Quello si
verifica a mano, e dalla tappa 2 con le evals.

### Ordine di lettura consigliato

1. `assistente/config.py` — le impostazioni.
2. `assistente/provider/base.py` — la forma comune di risposte ed errori.
3. `assistente/provider/groq_provider.py`, poi `anthropic_provider.py` — confrontali.
4. `assistente/sessione.py` — la memoria della conversazione.
5. `assistente/cli.py` — l'interfaccia.
6. `tests/test_sessione.py` — ogni test è una regola del comportamento, scritta come esempio.

### Esperimenti

- In `sessione.py` commenta la riga `self.messaggi.append(risposta.messaggio)`
  e chiedi al modello di ricordare qualcosa: quale test fallisce?
- Fai tre domande e guarda `/costo` dopo ognuna: i token in ingresso crescono
  più in fretta di quelli in uscita. Perché?
- Stacca la rete e fai una domanda, poi guarda `/costo` e fai `/nuovo`.

### Stato della verifica

- Groq: provato con il modello vero (streaming, cronologia, conteggio dei token).
- Anthropic: coperto solo dai test con il client finto; non provato con una chiave vera.

## Tappa 2 — Controlli di sicurezza

Branch `tappa-2-sicurezza`. *Da fare.*

## Tappa 3 — Agente

Branch `tappa-3-agente`. *Da fare.*

## Tappa 4 — Plugin

Branch `tappa-4-plugin`. *Da fare.*

## Tappa 5 — Loop

Branch `tappa-5-loop`. *Da fare.*

## Tappa 6 — Interfaccia grafica

Branch `tappa-6-interfaccia`. *Da fare.*
