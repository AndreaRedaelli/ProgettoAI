# Assistente AI da riga di comando

Progetto didattico per imparare l'AI Engineering. Il percorso è in [TAPPE.md](TAPPE.md).

La guida completa per configurarlo e avviarlo è in [AVVIO.md](AVVIO.md).

La spiegazione di come è fatto è in [docs/DOCUMENTAZIONE.md](docs/DOCUMENTAZIONE.md).

## Preparazione (una volta sola)

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Poi apri `.env` e inserisci la chiave del fornitore che usi.

## Scelta dell'AI

La variabile `AI_PROVIDER` nel file `.env` decide quale AI usare.

| Valore | Fornitore | Chiave | Modello predefinito |
|---|---|---|---|
| `groq` (predefinito) | Groq, piano gratuito | `GROQ_API_KEY` | `openai/gpt-oss-120b` |
| `anthropic` | Anthropic, a consumo | `ANTHROPIC_API_KEY` | `claude-opus-5-5` |

`MODELLO` è facoltativa e sostituisce il modello predefinito.

## Avvio

```powershell
.venv\Scripts\python.exe -m assistente
```

Comandi nella chat: `/costo`, `/nuovo`, `/esci`.

Interfaccia grafica: `.venv\Scripts\python.exe -m assistente gui`

## Struttura

| File | Ruolo |
|---|---|
| `assistente/config.py` | Impostazioni: fornitore, modello, system prompt, prezzi |
| `assistente/cli.py` | Interfaccia a riga di comando e cronologia |
| `assistente/provider/__init__.py` | Sceglie il fornitore in base a `AI_PROVIDER` |
| `assistente/provider/base.py` | Forma comune di risposte ed errori |
| `assistente/provider/groq_provider.py` | Chiamata all'API di Groq |
| `assistente/provider/anthropic_provider.py` | Chiamata all'API di Anthropic |
