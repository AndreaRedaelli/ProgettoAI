"""Interfaccia grafica (Tkinter): una maschera per le impostazioni e una chat.

Questo file disegna soltanto. Ciò che la finestra sa fare sta in
gui_logica.py; la conversazione vera sta in sessione.py, la stessa usata
dalla riga di comando. Tkinter fa parte di Python: non c'è nulla da installare.
"""

import queue
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from . import config
from .gui_logica import (
    NOMI_CHIAVE,
    Impostazioni,
    Lavoratore,
    chiave_salvata,
    crea_sessione,
    impostazioni_iniziali,
    salva_nel_file_env,
    valida,
)
from .provider import ErroreAI, crea_provider

# Ogni quanti millisecondi la finestra guarda se il filo di lavoro ha novità.
INTERVALLO_CODA = 50


class Finestra:
    def __init__(self, radice: tk.Tk, fabbrica_provider=crea_provider, chiedi_conferma=None) -> None:
        self.radice = radice
        # Questi due parametri esistono per i test: un fornitore finto e una
        # conferma che non apre finestre di dialogo.
        self.fabbrica_provider = fabbrica_provider
        self.chiedi_conferma = chiedi_conferma or self._finestra_di_conferma

        self.coda: queue.Queue = queue.Queue()
        self.sessione = None
        self.registro = None
        self.lavoratore: Lavoratore | None = None

        radice.title("Assistente AI")
        radice.minsize(640, 520)
        self._crea_maschera()
        self._crea_chat()
        radice.protocol("WM_DELETE_WINDOW", self.chiudi)
        # Da qui in poi la finestra controlla la coda a intervalli regolari.
        radice.after(INTERVALLO_CODA, self._controlla_coda)

    # --- Disegno ----------------------------------------------------------

    def _crea_maschera(self) -> None:
        iniziali = impostazioni_iniziali()
        # Le "variabili" di Tkinter legano un valore a un campo della maschera.
        self.var_provider = tk.StringVar(value=iniziali.provider)
        self.var_modello = tk.StringVar(value=iniziali.modello)
        self.var_chiave = tk.StringVar(value=iniziali.chiave)
        self.var_ambito = tk.StringVar(value=iniziali.ambito)
        self.var_mostra = tk.BooleanVar(value=False)
        # Spenta in partenza: la chiave finisce su disco solo se lo chiedi tu.
        self.var_salva = tk.BooleanVar(value=False)
        self.var_stato = tk.StringVar(value="Non connesso.")

        maschera = ttk.LabelFrame(self.radice, text="Impostazioni", padding=8)
        maschera.pack(fill="x", padx=8, pady=(8, 4))
        maschera.columnconfigure(1, weight=1)

        ttk.Label(maschera, text="AI").grid(row=0, column=0, sticky="w")
        scelta = ttk.Combobox(
            maschera, textvariable=self.var_provider, values=list(NOMI_CHIAVE), state="readonly", width=14
        )
        scelta.grid(row=0, column=1, sticky="w", pady=2)
        scelta.bind("<<ComboboxSelected>>", lambda _evento: self.cambia_provider())

        ttk.Label(maschera, text="Modello").grid(row=1, column=0, sticky="w")
        ttk.Entry(maschera, textvariable=self.var_modello).grid(row=1, column=1, sticky="ew", pady=2)

        ttk.Label(maschera, text="Chiave API").grid(row=2, column=0, sticky="w")
        # show="•" nasconde ciò che si scrive, come in un campo password.
        self.campo_chiave = ttk.Entry(maschera, textvariable=self.var_chiave, show="•")
        self.campo_chiave.grid(row=2, column=1, sticky="ew", pady=2)
        ttk.Checkbutton(maschera, text="mostra", variable=self.var_mostra, command=self._mostra_chiave).grid(
            row=2, column=2, padx=(6, 0)
        )

        ttk.Label(maschera, text="Ambito").grid(row=3, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(maschera, textvariable=self.var_ambito).grid(row=3, column=1, sticky="ew", pady=2)
        ttk.Label(maschera, text='("libero" spegne il filtro)').grid(row=3, column=2, padx=(6, 0))

        ttk.Checkbutton(
            maschera, text="Salva queste impostazioni (chiave compresa) nel file .env", variable=self.var_salva
        ).grid(row=4, column=1, sticky="w", pady=2)

        ttk.Button(maschera, text="Connetti", command=self.connetti).grid(row=5, column=1, sticky="w", pady=(4, 0))
        ttk.Label(maschera, textvariable=self.var_stato, wraplength=600).grid(
            row=6, column=0, columnspan=3, sticky="w", pady=(4, 0)
        )

    def _crea_chat(self) -> None:
        self.testo = scrolledtext.ScrolledText(self.radice, wrap="word", height=16, state="disabled")
        self.testo.pack(fill="both", expand=True, padx=8, pady=4)
        # Le "etichette" danno uno stile diverso a chi parla.
        self.testo.tag_configure("utente", foreground="#0b5394", font=("TkDefaultFont", 10, "bold"))
        self.testo.tag_configure("nota", foreground="#666666")
        self.testo.tag_configure("errore", foreground="#b00020")

        riga = ttk.Frame(self.radice)
        riga.pack(fill="x", padx=8, pady=4)
        riga.columnconfigure(0, weight=1)
        self.campo_domanda = ttk.Entry(riga)
        self.campo_domanda.grid(row=0, column=0, sticky="ew")
        self.campo_domanda.bind("<Return>", lambda _evento: self.invia())
        self.pulsante_invia = ttk.Button(riga, text="Invia", command=self.invia, state="disabled")
        self.pulsante_invia.grid(row=0, column=1, padx=(6, 0))
        self.pulsante_nuova = ttk.Button(
            riga, text="Nuova conversazione", command=self.nuova_conversazione, state="disabled"
        )
        self.pulsante_nuova.grid(row=0, column=2, padx=(6, 0))

        self.var_riepilogo = tk.StringVar(value="")
        ttk.Label(self.radice, textvariable=self.var_riepilogo).pack(anchor="w", padx=8, pady=(0, 8))

    def _mostra_chiave(self) -> None:
        self.campo_chiave.configure(show="" if self.var_mostra.get() else "•")

    def scrivi(self, testo: str, stile: str = "") -> None:
        """Aggiunge testo in fondo alla chat."""
        # L'area è di sola lettura per l'utente: la sblocchiamo solo per scrivere.
        self.testo.configure(state="normal")
        self.testo.insert("end", testo, stile)
        self.testo.configure(state="disabled")
        self.testo.see("end")

    # --- Azioni della maschera ---------------------------------------------

    def leggi_maschera(self) -> Impostazioni:
        return Impostazioni(
            provider=self.var_provider.get(),
            modello=self.var_modello.get(),
            chiave=self.var_chiave.get(),
            ambito=self.var_ambito.get(),
            salva_chiave=self.var_salva.get(),
        )

    def cambia_provider(self) -> None:
        """Cambiando AI cambiano anche il modello predefinito e la chiave da usare."""
        provider = self.var_provider.get()
        self.var_modello.set(config.MODELLI_PREDEFINITI.get(provider, ""))
        self.var_chiave.set(chiave_salvata(provider))

    def connetti(self) -> None:
        """Legge la maschera e prepara una nuova sessione."""
        if self.lavoratore and self.lavoratore.occupato:
            self.var_stato.set("Attendi la fine della risposta in corso.")
            return
        impostazioni = self.leggi_maschera()
        if errori := valida(impostazioni):
            self.var_stato.set(" ".join(errori))
            return

        self._chiudi_registro()
        try:
            self.sessione, self.registro = crea_sessione(impostazioni, self.fabbrica_provider)
        except ErroreAI as errore:
            self.sessione = None
            self._abilita(False)
            self.var_stato.set(str(errore))
            return
        self.lavoratore = Lavoratore(self.sessione, self.coda)

        if impostazioni.salva_chiave:
            salva_nel_file_env(impostazioni)
        self.var_stato.set(
            f"Connesso a {config.PROVIDER} (modello: {config.MODELLO}). "
            f"Ambito: {config.AMBITO or 'libero (filtro spento)'}. "
            f"Strumenti: {len(self.registro.definizioni())}."
            + (" Impostazioni salvate in .env." if impostazioni.salva_chiave else "")
        )
        for nota in self.registro.note:
            self.scrivi(f"[{nota}]\n", "nota")
        self.var_riepilogo.set(self.sessione.riepilogo())
        self._abilita(True)
        self.campo_domanda.focus_set()

    def nuova_conversazione(self) -> None:
        if self.sessione and not self.lavoratore.occupato:
            self.sessione.azzera()
            self.scrivi("[Conversazione azzerata]\n\n", "nota")

    # --- Chat ---------------------------------------------------------------

    def invia(self) -> None:
        domanda = self.campo_domanda.get().strip()
        if not domanda or not self.lavoratore:
            return
        # Il lavoro parte in sottofondo: questo metodo ritorna subito.
        if not self.lavoratore.invia(domanda):
            return
        self.campo_domanda.delete(0, "end")
        self.scrivi(f"Tu: {domanda}\n", "utente")
        self.scrivi("AI: ")
        self._abilita(False)

    def _controlla_coda(self) -> None:
        self.leggi_coda()
        self.radice.after(INTERVALLO_CODA, self._controlla_coda)

    def leggi_coda(self) -> None:
        """Svuota la coda degli eventi arrivati dal filo di lavoro.

        È l'unico punto in cui ciò che fa l'AI diventa qualcosa sullo
        schermo, e gira nel filo della finestra: per questo può toccarla.
        """
        while True:
            try:
                tipo, dato = self.coda.get_nowait()
            except queue.Empty:
                return

            if tipo == "testo":
                self.scrivi(dato)
            elif tipo == "strumento":
                self.scrivi(f"\n  [{dato}]\n", "nota")
            elif tipo == "nota":
                self.scrivi(f"\n[{dato}]", "nota")
            elif tipo == "bloccata":
                self.scrivi(f"[Bloccata] {dato}", "errore")
            elif tipo == "errore":
                self.scrivi(dato, "errore")
            elif tipo == "conferma":
                # Il filo di lavoro è fermo ad aspettare questa risposta.
                dato.rispondi(self.chiedi_conferma(dato.nome, dato.dettaglio))
            elif tipo == "fine":
                self.scrivi("\n\n")
                self.var_riepilogo.set(self.sessione.riepilogo())
                self._abilita(True)

    def _finestra_di_conferma(self, nome: str, dettaglio: str) -> bool:
        return messagebox.askyesno(
            "Conferma", f"L'assistente chiede di usare '{nome}':\n\n{dettaglio}\n\nConfermi?", default="no"
        )

    def _abilita(self, attivo: bool) -> None:
        stato = "normal" if attivo else "disabled"
        self.pulsante_invia.configure(state=stato)
        self.pulsante_nuova.configure(state=stato)

    # --- Chiusura -----------------------------------------------------------

    def _chiudi_registro(self) -> None:
        # I server MCP sono processi separati: vanno chiusi.
        if self.registro:
            self.registro.chiudi()
            self.registro = None

    def chiudi(self) -> None:
        self._chiudi_registro()
        self.radice.destroy()


def main() -> None:
    radice = tk.Tk()
    Finestra(radice)
    radice.mainloop()
