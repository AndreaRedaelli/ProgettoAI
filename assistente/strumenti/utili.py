"""Strumenti senza effetti: calcoli e data. Utili perché un modello sbaglia i conti e non sa che giorno è."""

import ast
import operator
from datetime import datetime

from .base import ErroreStrumento, Strumento

OPERAZIONI = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def calcola(espressione: str) -> str:
    """Calcola un'espressione aritmetica SENZA usare eval().

    eval() eseguirebbe qualunque codice Python scritto dal modello. Qui
    invece leggiamo l'espressione come albero e accettiamo solo numeri e
    operazioni aritmetiche: tutto il resto viene rifiutato.
    """

    def valuta(nodo):
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float)) and not isinstance(nodo.value, bool):
            return nodo.value
        if isinstance(nodo, ast.BinOp) and type(nodo.op) in OPERAZIONI:
            sinistra, destra = valuta(nodo.left), valuta(nodo.right)
            if isinstance(nodo.op, ast.Pow) and abs(destra) > 100:
                raise ErroreStrumento("Esponente troppo grande.")
            return OPERAZIONI[type(nodo.op)](sinistra, destra)
        if isinstance(nodo, ast.UnaryOp) and type(nodo.op) in OPERAZIONI:
            return OPERAZIONI[type(nodo.op)](valuta(nodo.operand))
        raise ErroreStrumento("Sono ammessi solo numeri e operazioni aritmetiche.")

    try:
        albero = ast.parse(espressione, mode="eval")
        return str(valuta(albero.body))
    except SyntaxError:
        raise ErroreStrumento("Espressione non valida.") from None
    except ZeroDivisionError:
        raise ErroreStrumento("Divisione per zero.") from None


def data_e_ora() -> str:
    return datetime.now().strftime("%A %d/%m/%Y, ore %H:%M")


def crea_strumenti_utili() -> list[Strumento]:
    return [
        Strumento(
            "calcola",
            "Calcola un'espressione aritmetica (+ - * / // % **). Usalo per ogni calcolo.",
            {
                "type": "object",
                "properties": {
                    "espressione": {"type": "string", "description": "Per esempio: (12 + 8) * 3"}
                },
                "required": ["espressione"],
            },
            calcola,
        ),
        Strumento(
            "data_e_ora",
            "Restituisce la data e l'ora correnti.",
            {"type": "object", "properties": {}},
            data_e_ora,
        ),
    ]
