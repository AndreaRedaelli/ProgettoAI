"""Client MCP scritto a mano.

MCP (Model Context Protocol) è lo standard con cui un programma mette i propri
strumenti a disposizione di un'AI. Un "server MCP" è un processo separato;
noi siamo il "client". Le due parti si scambiano messaggi JSON-RPC, uno per
riga, sullo standard input e output del processo.

Bastano quattro messaggi:

    initialize                  ci presentiamo e concordiamo la versione
    notifications/initialized   confermiamo che siamo pronti
    tools/list                  chiediamo l'elenco degli strumenti
    tools/call                  ne eseguiamo uno

Esiste una libreria ufficiale che fa tutto questo. Qui lo scriviamo a mano
per vedere che cosa c'è sotto: è lo stesso schema del tool use, spostato in
un altro processo.
"""

import json
import queue
import subprocess
import sys
import threading

from .base import ErroreStrumento, Registro, Strumento

VERSIONE_PROTOCOLLO = "2025-06-18"


class ClientMCP:
    def __init__(self, nome: str, comando: list[str], tempo_massimo: float = 20.0) -> None:
        self.nome = nome
        self.tempo_massimo = tempo_massimo
        self._prossimo_id = 0
        # "python" nel comando indica l'interprete che sta eseguendo l'assistente.
        comando = [sys.executable if parte == "python" else parte for parte in comando]
        try:
            self.processo = subprocess.Popen(
                comando,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except OSError as problema:
            raise ErroreStrumento(f"Server MCP '{nome}' non avviato: {problema}") from problema

        # Un thread legge le righe del server e le mette in coda: così
        # possiamo aspettare una risposta con un tempo massimo.
        self._righe: queue.Queue = queue.Queue()
        threading.Thread(target=self._leggi, daemon=True).start()

        try:
            self._richiesta(
                "initialize",
                {
                    "protocolVersion": VERSIONE_PROTOCOLLO,
                    "capabilities": {},
                    "clientInfo": {"name": "assistente", "version": "1.0"},
                },
            )
            self._invia({"jsonrpc": "2.0", "method": "notifications/initialized"})
        except ErroreStrumento:
            self.chiudi()
            raise

    def _leggi(self) -> None:
        for riga in self.processo.stdout:
            self._righe.put(riga)
        self._righe.put(None)  # il server ha chiuso

    def _invia(self, messaggio: dict) -> None:
        try:
            self.processo.stdin.write(json.dumps(messaggio) + "\n")
            self.processo.stdin.flush()
        except OSError as problema:
            raise ErroreStrumento(f"Server MCP '{self.nome}' non raggiungibile.") from problema

    def _richiesta(self, metodo: str, parametri: dict) -> dict:
        """Manda una richiesta e aspetta la risposta con lo stesso id."""
        self._prossimo_id += 1
        identificativo = self._prossimo_id
        self._invia({"jsonrpc": "2.0", "id": identificativo, "method": metodo, "params": parametri})

        while True:
            try:
                riga = self._righe.get(timeout=self.tempo_massimo)
            except queue.Empty:
                raise ErroreStrumento(f"Server MCP '{self.nome}': nessuna risposta in tempo.") from None
            if riga is None:
                raise ErroreStrumento(f"Server MCP '{self.nome}' si è chiuso.")
            try:
                messaggio = json.loads(riga)
            except json.JSONDecodeError:
                continue  # riga che non è un messaggio: la ignoriamo
            # Il server può mandare anche notifiche: ci interessa solo la nostra risposta.
            if not isinstance(messaggio, dict) or messaggio.get("id") != identificativo:
                continue
            if "error" in messaggio:
                raise ErroreStrumento(f"Server MCP '{self.nome}': {messaggio['error'].get('message', 'errore')}")
            return messaggio.get("result", {})

    def strumenti(self) -> list[dict]:
        return self._richiesta("tools/list", {}).get("tools", [])

    def chiama(self, nome: str, argomenti: dict) -> str:
        risultato = self._richiesta("tools/call", {"name": nome, "arguments": argomenti})
        testo = "\n".join(
            blocco.get("text", "") for blocco in risultato.get("content", []) if blocco.get("type") == "text"
        )
        if risultato.get("isError"):
            raise ErroreStrumento(testo or "Lo strumento ha segnalato un errore.")
        return testo

    def chiudi(self) -> None:
        try:
            self.processo.stdin.close()
            self.processo.terminate()
            self.processo.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            self.processo.kill()


def carica_server_mcp(registro: Registro, configurazione: dict) -> list[str]:
    """Avvia i server configurati e ne aggiunge gli strumenti al registro.

    `configurazione` ha la forma:
        {"nome": {"comando": ["python", "-m", "modulo"], "fidato": true}}
    """
    note: list[str] = []
    for nome, impostazioni in configurazione.items():
        try:
            client = ClientMCP(nome, impostazioni["comando"])
            elenco = client.strumenti()
        except (ErroreStrumento, KeyError, TypeError) as problema:
            note.append(f"Server MCP '{nome}' non collegato: {problema}")
            continue

        registro.risorse.append(client)
        fidato = impostazioni.get("fidato") is True
        aggiunti = 0
        for definizione in elenco:
            # Il nome del server fa da prefisso: due server non possono
            # scontrarsi, e si vede sempre da dove arriva uno strumento.
            nome_completo = f"{nome}__{definizione['name']}"
            if nome_completo in registro.strumenti:
                continue
            registro.aggiungi(
                Strumento(
                    nome_completo,
                    definizione.get("description") or definizione["name"],
                    definizione.get("inputSchema") or {"type": "object", "properties": {}},
                    # I valori predefiniti fissano client e nome per QUESTO strumento.
                    lambda _client=client, _nome=definizione["name"], **argomenti: _client.chiama(_nome, argomenti),
                    permesso="libero" if fidato else "conferma",
                )
            )
            aggiunti += 1
        note.append(
            f"Server MCP '{nome}' collegato: {aggiunti} strumenti"
            + ("" if fidato else " (non fidato: chiedono sempre conferma)")
        )
    return note
