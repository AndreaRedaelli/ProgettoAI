"""Impostazioni dell'assistente, lette dal file .env."""

import os

from dotenv import load_dotenv

# Carica le variabili del file .env (tra cui le chiavi API) nell'ambiente.
load_dotenv()

# Modello usato da ciascun fornitore quando MODELLO non è impostato.
MODELLI_PREDEFINITI = {
    "groq": "openai/gpt-oss-120b",
    "anthropic": "claude-opus-5-5",
}

# Quale AI usare: "groq" (gratuito, predefinito) oppure "anthropic".
PROVIDER = (os.getenv("AI_PROVIDER") or "groq").strip().lower()
MODELLO = os.getenv("MODELLO") or MODELLI_PREDEFINITI.get(PROVIDER, "")

# Il system prompt definisce ruolo e tono. Resta uguale per tutta la conversazione.
SYSTEM_PROMPT = (
    "Sei un assistente generico usato da riga di comando. "
    "Rispondi in italiano, in modo chiaro e conciso. "
    "L'output viene mostrato in un terminale: usa testo semplice."
)

# Prezzi in dollari per milione di token: (ingresso, uscita).
# I modelli non elencati (come quelli del piano gratuito di Groq) valgono zero.
PREZZI = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}

# --- Solo Anthropic ---
# Quanto "si impegna" il modello: low, medium, high.
EFFORT = os.getenv("EFFORT") or "medium"
# Tetto ai token di UNA risposta. Non è un obiettivo: il modello si ferma prima.
MAX_TOKENS = 64000
