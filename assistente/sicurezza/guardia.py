"""La guardia: mette in fila i controlli e decide se una richiesta passa.

I controlli vanno dal più economico al più costoso. Appena uno blocca, gli
altri non vengono eseguiti: una domanda troppo lunga non arriva mai al
modello giudice, e non costa nulla.
"""

from dataclasses import dataclass, field

from ..provider import Risposta, RisultatoStrumento
from .ambito import giudica_ambito
from .controlli import LimiteFrequenza, cerca_injection
from .dati_sensibili import maschera


@dataclass
class Verdetto:
    consentita: bool
    # Il testo da inviare al modello: la domanda con i dati sensibili mascherati.
    testo: str
    # Se bloccata: quale controllo l'ha fermata e perché.
    controllo: str = ""
    motivo: str = ""
    mascherati: list[str] = field(default_factory=list)
    # La risposta del modello giudice, se è stato interpellato (per contarne i token).
    giudice: Risposta | None = None


class RichiestaBloccata(Exception):
    def __init__(self, verdetto: Verdetto) -> None:
        super().__init__(verdetto.motivo)
        self.verdetto = verdetto


class Guardia:
    def __init__(
        self,
        provider,
        ambito: str = "",
        audit=None,
        max_caratteri: int = 4000,
        max_richieste_al_minuto: int = 10,
        max_richieste_sessione: int = 50,
        system_prompt: str = "",
        strumenti=(),
    ) -> None:
        self.provider = provider
        # Ambito vuoto = filtro di ambito spento.
        self.ambito = ambito
        self.audit = audit
        self.max_caratteri = max_caratteri
        self.limite = LimiteFrequenza(max_richieste_al_minuto)
        self.max_richieste_sessione = max_richieste_sessione
        self.richieste_sessione = 0
        self.system_prompt = system_prompt
        # Installare uno strumento allarga ciò che l'assistente è fatto per
        # fare: il giudice deve saperlo, o bloccherebbe le richieste che lo usano.
        self.capacita = "; ".join(f"{s.nome} ({s.descrizione})" for s in strumenti)

    def verifica(self, domanda: str, scambi=()) -> Verdetto:
        """Fa passare la domanda da tutti i controlli e registra l'esito."""
        verdetto = self._decidi(domanda, scambi)
        if self.audit:
            self.audit.registra(
                "richiesta",
                esito="consentita" if verdetto.consentita else "bloccata",
                controllo=verdetto.controllo,
                motivo=verdetto.motivo,
                mascherati=verdetto.mascherati,
                # Nel log finisce il testo già mascherato, e mai tutto.
                testo=verdetto.testo[:500],
            )
        return verdetto

    def _decidi(self, domanda: str, scambi) -> Verdetto:
        # Mascheriamo subito: da qui in poi nessuno vede più i dati originali.
        testo, mascherati = maschera(domanda)

        def blocca(controllo: str, motivo: str, giudice=None) -> Verdetto:
            return Verdetto(False, testo, controllo, motivo, mascherati, giudice)

        # 1. Lunghezza: un confronto tra numeri.
        if len(domanda) > self.max_caratteri:
            return blocca(
                "lunghezza",
                f"Domanda troppo lunga: {len(domanda)} caratteri, il massimo è {self.max_caratteri}.",
            )

        # 2. Frequenza: non più di tante richieste al minuto.
        if not self.limite.consenti():
            return blocca("frequenza", "Troppe richieste in poco tempo: aspetta un minuto.")

        # 3. Tetto della sessione: un freno alla spesa complessiva.
        if self.richieste_sessione >= self.max_richieste_sessione:
            return blocca(
                "tetto_sessione",
                f"Raggiunto il tetto di {self.max_richieste_sessione} richieste per sessione.",
            )
        self.richieste_sessione += 1

        # 4. Prompt injection: ricerca di frasi note.
        if cerca_injection(domanda):
            return blocca(
                "prompt_injection",
                "La richiesta sembra un tentativo di aggirare le regole dell'assistente.",
            )

        # 5. Ambito: l'unico controllo che costa una chiamata all'AI, quindi è l'ultimo.
        giudice = None
        if self.ambito:
            ambito = self.ambito
            if self.capacita:
                ambito += f". Sono dentro anche le richieste che usano questi strumenti dell'assistente: {self.capacita}"
            giudizio = giudica_ambito(self.provider, ambito, testo, scambi)
            giudice = giudizio.risposta
            if not giudizio.dentro:
                return blocca("ambito", f"Richiesta fuori ambito. {giudizio.motivo}".strip(), giudice)

        return Verdetto(True, testo, mascherati=mascherati, giudice=giudice)

    def filtra_risultato(self, chiamata, risultato: RisultatoStrumento) -> RisultatoStrumento:
        """Controlla ciò che uno strumento restituisce prima che arrivi al modello.

        Un file, una pagina o la risposta di un plugin possono contenere
        istruzioni scritte apposta per il modello ("prompt injection
        indiretta"). Qui applichiamo gli stessi controlli della domanda:
        mascheramento e ricerca delle frasi sospette.
        """
        testo, mascherati = maschera(risultato.contenuto)
        bloccato = cerca_injection(testo) is not None
        if bloccato:
            risultato = RisultatoStrumento(
                risultato.id,
                "Contenuto bloccato: sembra contenere istruzioni rivolte all'assistente.",
                errore=True,
            )
        else:
            risultato = RisultatoStrumento(risultato.id, testo, risultato.errore)

        if self.audit:
            self.audit.registra(
                "strumento",
                nome=chiamata.nome,
                argomenti=maschera(str(chiamata.argomenti))[0][:300],
                errore=risultato.errore,
                bloccato=bloccato,
                mascherati=mascherati,
            )
        return risultato

    def controlla_uscita(self, testo: str) -> list[str]:
        """Cerca problemi nella risposta del modello.

        Con lo streaming il testo è già stato mostrato: qui possiamo solo
        avvisare e lasciare traccia. Per bloccare davvero bisognerebbe
        rinunciare allo streaming e controllare prima di mostrare.
        """
        avvisi: list[str] = []
        _, trovati = maschera(testo)
        if trovati:
            avvisi.append("la risposta contiene dati sensibili: " + ", ".join(trovati))
        # Se un pezzo lungo del system prompt compare nella risposta, è trapelato.
        if self.system_prompt and self.system_prompt[:60] in testo:
            avvisi.append("la risposta riporta il system prompt")

        if self.audit:
            self.audit.registra("risposta", caratteri=len(testo), avvisi=avvisi)
        return avvisi
