"""Cartera: valoración, distribución por clase de activo y rebalanceo."""

import json
from pathlib import Path

import pandas as pd

from .catalog import asset_class

COLUMNS = ["ticker", "cantidad", "precio_medio"]


def empty_positions() -> pd.DataFrame:
    return pd.DataFrame({"ticker": pd.Series(dtype=str), "cantidad": pd.Series(dtype=float), "precio_medio": pd.Series(dtype=float)})


def clean_positions(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza la tabla editada por el usuario y descarta filas inválidas."""
    if df is None or df.empty:
        return empty_positions()
    df = df.reindex(columns=COLUMNS).copy()
    df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
    df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce")
    df["precio_medio"] = pd.to_numeric(df["precio_medio"], errors="coerce")
    df = df[(df["ticker"] != "") & (df["ticker"] != "NAN") & (df["ticker"] != "NONE")]
    df = df.dropna(subset=["cantidad", "precio_medio"])
    df = df[df["cantidad"] > 0]
    return df.reset_index(drop=True)


def load_positions(path: Path) -> pd.DataFrame:
    if not path.exists():
        return empty_positions()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return empty_positions()
    return clean_positions(pd.DataFrame(data))


def save_positions(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean_positions(df).to_dict(orient="records"), indent=2, ensure_ascii=False), encoding="utf-8")


def valuate(positions: pd.DataFrame, prices: dict[str, float]) -> pd.DataFrame:
    """Añade precio actual, valor, coste, ganancia y peso de cada posición."""
    df = clean_positions(positions)
    if df.empty:
        return df.assign(clase=[], precio_actual=[], coste=[], valor=[], ganancia=[], ganancia_pct=[], peso=[])
    df["clase"] = df["ticker"].map(asset_class)
    df["precio_actual"] = df["ticker"].map(prices).astype(float)
    df["coste"] = df["cantidad"] * df["precio_medio"]
    df["valor"] = df["cantidad"] * df["precio_actual"]
    df["ganancia"] = df["valor"] - df["coste"]
    df["ganancia_pct"] = df["ganancia"] / df["coste"]
    total = df["valor"].sum(skipna=True)
    df["peso"] = df["valor"] / total if total else float("nan")
    return df


def allocation_by_class(valued: pd.DataFrame) -> pd.Series:
    if valued.empty:
        return pd.Series(dtype=float)
    by = valued.groupby("clase")["valor"].sum()
    return by / by.sum()


def rebalance(valued: pd.DataFrame, targets: dict[str, float]) -> pd.DataFrame:
    """Compara la distribución actual con la objetivo (pesos que suman 1).

    Devuelve, por clase, el peso actual, el objetivo y cuánto dinero
    habría que comprar (+) o vender (-) para alcanzar el objetivo.
    """
    total = float(valued["valor"].sum()) if not valued.empty else 0.0
    current = valued.groupby("clase")["valor"].sum() if not valued.empty else pd.Series(dtype=float)
    classes = sorted(set(current.index) | {k for k, v in targets.items() if v > 0})
    rows = []
    for cls in classes:
        cur_val = float(current.get(cls, 0.0))
        tgt = float(targets.get(cls, 0.0))
        rows.append(
            {
                "clase": cls,
                "peso_actual": cur_val / total if total else 0.0,
                "peso_objetivo": tgt,
                "ajuste": tgt * total - cur_val,
            }
        )
    return pd.DataFrame(rows, columns=["clase", "peso_actual", "peso_objetivo", "ajuste"])
