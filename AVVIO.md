# Come avviare l'assistente

Guida passo per passo, dal progetto appena scaricato alla prima domanda.
I comandi sono per PowerShell su Windows e vanno eseguiti nella cartella del progetto.

## 1. Requisiti

- Python 3.10 o successivo. Per controllare:

  ```powershell
  python --version
  ```

- Una chiave API del fornitore che vuoi usare (vedi il passo 3).

## 2. Preparare l'ambiente (una volta sola)

Crea l'ambiente virtuale e installa le dipendenze:

```powershell
python -m venv .venv
```

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Crea il tuo file di configurazione partendo dal modello:

```powershell
Copy-Item .env.example .env
```

Il file `.env` contiene le chiavi ed è escluso da git: non va mai caricato su GitHub.

## 3. Scegliere l'AI e ottenere la chiave

L'assistente funziona con due fornitori. Ne basta uno.

### Opzione A — Groq (predefinita, gratuita)

1. Vai su https://console.groq.com e registrati.
2. Apri la sezione **API Keys** e crea una nuova chiave.
3. Copiala subito: viene mostrata una sola volta.

Il piano gratuito ha un limite di richieste al minuto e al giorno.

### Opzione B — Anthropic (Claude, a pagamento)

1. Vai su https://console.anthropic.com e registrati.
2. Nella sezione di fatturazione carica un credito (il costo è a consumo ed è
   separato da un eventuale abbonamento a Claude).
3. Apri la sezione **API Keys** e crea una nuova chiave.
4. Copiala subito: viene mostrata una sola volta.

## 4. Configurare il file `.env`

Apri `.env` con un editor di testo e compila le righe del fornitore scelto.

Per Groq:

```
AI_PROVIDER=groq
GROQ_API_KEY=la-tua-chiave
```

Per Anthropic:

```
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=la-tua-chiave
```

Regole:

- niente spazi intorno al segno `=` e niente virgolette intorno alla chiave;
- se `AI_PROVIDER` manca o è vuota, viene usato `groq`;
- puoi tenere entrambe le chiavi nel file e cambiare solo `AI_PROVIDER`.

Variabili facoltative:

| Variabile | A cosa serve | Se vuota |
|---|---|---|
| `MODELLO` | Modello da usare | `openai/gpt-oss-120b` con Groq, `claude-opus-5-5` con Anthropic |
| `EFFORT` | Solo Anthropic: quanto si impegna il modello (`low`, `medium`, `high`) | `medium` |
| `AMBITO` | Funzione prevista dell'assistente: le richieste che ne escono vengono bloccate | programmazione, informatica, intelligenza artificiale |

Con Anthropic, per spendere meno durante le prove imposta `MODELLO=claude-haiku-5-5`.

Per un assistente senza limiti di argomento imposta `AMBITO=libero`.

## 5. Avviare

```powershell
.venv\Scripts\python.exe -m assistente
```

Se tutto è a posto compare una riga come questa, seguita dal prompt `Tu>`:

```
Assistente pronto (groq, modello: openai/gpt-oss-120b). Comandi: /costo  /nuovo  /esci
```

Scrivi la domanda e premi Invio.

| Comando | Effetto |
|---|---|
| `/costo` | Mostra i token usati e la spesa stimata della sessione |
| `/nuovo` | Azzera la conversazione |
| `/strumenti` | Elenca gli strumenti dell'agente e i loro permessi |
| `/esci` | Chiude il programma |

`Ctrl+C` durante una risposta la interrompe; al prompt chiude il programma.

L'assistente può leggere e scrivere file solo nella cartella `area_lavoro/`,
creata al primo avvio. Prima di scrivere, eliminare o eseguire uno script
mostra cosa sta per fare e chiede `Confermi? [s/N]`: solo `s` vale come sì.

## 6. Il loop autonomo

Oltre alla chat, l'assistente può lavorare da solo a un obiettivo:

```powershell
.venv\Scripts\python.exe -m assistente loop "Leggi i file dell'area di lavoro e riassumili"
```

Lavora per iterazioni, mostrando gli strumenti che usa, e si ferma quando ha
finito o quando raggiunge un tetto di iterazioni, richieste o tempo. In
questa modalità può solo leggere: non scrive, non elimina e non esegue script.
Il risultato finisce in `area_lavoro/risultato_loop.md`.

Per riprendere un lavoro interrotto o fermato per budget esaurito:

```powershell
.venv\Scripts\python.exe -m assistente loop --riprendi
```

## 7. Se qualcosa non va

| Messaggio | Causa | Rimedio |
|---|---|---|
| `Manca la chiave API ...` | Il file `.env` non esiste o la chiave del fornitore scelto è vuota | Ripeti i passi 2 e 4 |
| `AI_PROVIDER='...' non riconosciuto` | Valore diverso da `groq` e `anthropic` | Correggi `AI_PROVIDER` in `.env` |
| `Chiave API non valida` | Chiave errata, incompleta o revocata | Ricopiala o creane una nuova |
| `[Bloccata] Richiesta fuori ambito` | La domanda esce dalla funzione prevista | Cambia `AMBITO` in `.env`, oppure `AMBITO=libero` |
| `[Bloccata] Troppe richieste in poco tempo` | Superato il limite al minuto dell'assistente | Aspetta un minuto, o alza `MAX_RICHIESTE_AL_MINUTO` |
| `Limite di richieste raggiunto` | Superato il limite del piano | Aspetta, oppure cambia fornitore |
| `Errore dell'API (404)` o messaggio sul modello | Il modello indicato non esiste più | Imposta `MODELLO` con un modello disponibile nella console del fornitore |
| `No module named ...` | Dipendenze non installate, o Python diverso da quello di `.venv` | Ripeti il secondo comando del passo 2 e avvia con il comando del passo 5 |
