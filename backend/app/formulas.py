"""Moteur d'évaluation sûr pour les colonnes calculées (Phase 3).

N'utilise jamais `eval`/`exec` : la formule est parsée en AST Python puis
interprétée par un évaluateur récursif qui n'autorise qu'un ensemble
restreint de nœuds (opérateurs arithmétiques/logiques/comparaisons,
appels vers des fonctions whitelistées, accès aux colonnes du DataFrame).
Toute autre construction (imports, attributs, comprehensions, lambdas...)
est rejetée.
"""
from __future__ import annotations

import ast
import math
import operator
import re
from typing import Any

import pandas as pd

from app.errors import AppError

_BRACE_PATTERN = re.compile(r"\{([^{}]+)\}")
# `if` est un mot-clé réservé en Python : `if(cond, a, b)` n'est pas un appel
# de fonction valide pour ast.parse. On le réécrit vers un nom d'appel
# autorisé avant le parsing, tout en gardant `if(...)` dans la syntaxe
# publique de la formule (celle documentée aux utilisateurs).
_IF_CALL_PATTERN = re.compile(r"\bif\s*\(")


class FormulaError(Exception):
    """Erreur structurelle de formule (syntaxe, colonne/fonction inconnue)."""


def _safe_div(a: Any, b: Any) -> Any:
    if b == 0:
        raise ZeroDivisionError("division par zéro")
    return a / b


_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: _safe_div,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}

_COMPARE_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


def _fn_substring(s: Any, start: int, end: int | None = None) -> str:
    return str(s)[int(start):(int(end) if end is not None else None)]


def _fn_if(cond: Any, if_true: Any, if_false: Any) -> Any:
    return if_true if cond else if_false


FUNCTIONS = {
    "abs": abs,
    "round": lambda v, ndigits=0: round(v, int(ndigits)),
    "sqrt": math.sqrt,
    "pow": pow,
    "log": lambda v, base=math.e: math.log(v, base),
    "log10": math.log10,
    "exp": math.exp,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "ceil": math.ceil,
    "floor": math.floor,
    "min": min,
    "max": max,
    "upper": lambda s: str(s).upper(),
    "lower": lambda s: str(s).lower(),
    "strip": lambda s: str(s).strip(),
    "len": lambda s: len(str(s)),
    "concat": lambda *args: "".join(str(a) for a in args),
    "replace": lambda s, old, new: str(s).replace(str(old), str(new)),
    "substring": _fn_substring,
    "__if__": _fn_if,
}


def preprocess_formula(formula: str) -> tuple[str, dict[str, str]]:
    """Remplace les références `{col}` par des identifiants Python valides.

    Retourne la formule réécrite ainsi qu'un mapping placeholder -> nom de
    colonne réel (utile pour les noms de colonnes contenant des espaces ou
    caractères non valides en identifiant Python).
    """
    mapping: dict[str, str] = {}
    counter = {"n": 0}

    def _replace(match: re.Match) -> str:
        col_name = match.group(1).strip()
        placeholder = f"__col_{counter['n']}__"
        counter["n"] += 1
        mapping[placeholder] = col_name
        return placeholder

    processed = _IF_CALL_PATTERN.sub("__if__(", formula)
    processed = _BRACE_PATTERN.sub(_replace, processed)
    return processed, mapping


def parse_formula(formula: str) -> tuple[ast.AST, dict[str, str]]:
    processed, mapping = preprocess_formula(formula)
    try:
        tree = ast.parse(processed, mode="eval")
    except SyntaxError as exc:
        raise FormulaError(f"Erreur de syntaxe dans la formule : {exc.msg}")
    return tree, mapping


def _resolve_name(node_id: str, row: dict, mapping: dict[str, str]) -> Any:
    if node_id in mapping:
        real_col = mapping[node_id]
        if real_col not in row:
            raise FormulaError(f"Colonne inconnue dans la formule : '{real_col}'")
        return row[real_col]
    if node_id in row:
        return row[node_id]
    if node_id in ("True", "False", "None"):
        return {"True": True, "False": False, "None": None}[node_id]
    raise FormulaError(f"Colonne ou variable inconnue dans la formule : '{node_id}'")


def _eval(node: ast.AST, row: dict, mapping: dict[str, str]) -> Any:
    if isinstance(node, ast.Expression):
        return _eval(node.body, row, mapping)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return _resolve_name(node.id, row, mapping)
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BINOPS:
            raise FormulaError(f"Opérateur non supporté : {op_type.__name__}")
        return _BINOPS[op_type](_eval(node.left, row, mapping), _eval(node.right, row, mapping))
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARYOPS:
            raise FormulaError(f"Opérateur unaire non supporté : {op_type.__name__}")
        return _UNARYOPS[op_type](_eval(node.operand, row, mapping))
    if isinstance(node, ast.BoolOp):
        values = [_eval(v, row, mapping) for v in node.values]
        return all(values) if isinstance(node.op, ast.And) else any(values)
    if isinstance(node, ast.Compare):
        left = _eval(node.left, row, mapping)
        result = True
        for op_node, comparator in zip(node.ops, node.comparators):
            op_type = type(op_node)
            if op_type not in _COMPARE_OPS:
                raise FormulaError(f"Comparateur non supporté : {op_type.__name__}")
            right = _eval(comparator, row, mapping)
            result = result and _COMPARE_OPS[op_type](left, right)
            left = right
        return result
    if isinstance(node, ast.IfExp):
        return _eval(node.body, row, mapping) if _eval(node.test, row, mapping) else _eval(node.orelse, row, mapping)
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise FormulaError("Appel de fonction invalide.")
        fname = node.func.id
        if fname not in FUNCTIONS:
            raise FormulaError(f"Fonction inconnue : '{fname}'")
        if node.keywords:
            raise FormulaError("Les arguments nommés ne sont pas supportés.")
        args = [_eval(a, row, mapping) for a in node.args]
        return FUNCTIONS[fname](*args)
    raise FormulaError(f"Construction non supportée dans la formule : {type(node).__name__}")


def validate_formula(formula: str, columns: list[str]) -> None:
    """Valide la structure de la formule (syntaxe, colonnes/fonctions connues)
    en l'évaluant sur une ligne factice neutre. Lève FormulaError si invalide.
    """
    tree, mapping = parse_formula(formula)
    dummy_row = {col: 1 for col in columns}
    try:
        _eval(tree.body, dummy_row, mapping)
    except FormulaError:
        raise
    except ZeroDivisionError:
        pass  # la formule est structurellement valide, seule cette valeur factice pose problème
    except Exception:
        pass  # erreur dépendant de la valeur (ex: sqrt(-1)) : pas une erreur structurelle


def evaluate_formula(df: pd.DataFrame, formula: str) -> tuple[pd.Series, int]:
    """Évalue la formule pour chaque ligne du DataFrame.

    Retourne (série de résultats, nombre de lignes en erreur -> None).
    Les erreurs structurelles (colonne/fonction inconnue, syntaxe) lèvent une
    AppError immédiatement. Les erreurs dépendant des valeurs d'une ligne
    (division par zéro, sqrt négatif, type mismatch) produisent None pour
    cette ligne uniquement, sans interrompre le calcul des autres lignes.
    """
    try:
        tree, mapping = parse_formula(formula)
        validate_formula(formula, list(df.columns))
    except FormulaError as exc:
        raise AppError(400, "INVALID_FORMULA", str(exc))

    error_count = 0

    def _row_eval(row: pd.Series) -> Any:
        nonlocal error_count
        try:
            return _eval(tree.body, row.to_dict(), mapping)
        except FormulaError as exc:
            raise AppError(400, "INVALID_FORMULA", str(exc))
        except Exception:
            error_count += 1
            return None

    if len(df) == 0:
        return pd.Series([], dtype=object), 0

    result = df.apply(_row_eval, axis=1)
    return result, error_count
