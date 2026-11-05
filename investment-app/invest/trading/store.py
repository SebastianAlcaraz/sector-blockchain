"""Almacenamiento del bot en SQLite: propuestas, operaciones, valor de la cartera, eventos y estado.

SQLite permite que el bot (proceso programado) y la web (aprobaciones) escriban a la vez sin pisarse.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TEXT NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,            -- comprar / vender
    amount REAL,                   -- importe (compras)
    units REAL,                    -- unidades (ventas)
    price REAL NOT NULL,           -- precio al proponer
    confidence REAL,
    reason TEXT,
    risks TEXT,
    checks TEXT,                   -- notas del control de riesgo (JSON)
    status TEXT NOT NULL,          -- pendiente / aprobada / rechazada / ejecutada / caducada / fallida
    decided TEXT,
    result TEXT,
    stop_pct REAL                  -- compras: distancia del stop-loss en % (NULL = el fijo de la configuración)
);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    units REAL NOT NULL,
    price REAL NOT NULL,
    amount REAL NOT NULL,
    fee REAL NOT NULL DEFAULT 0,
    proposal_id INTEGER,
    origin TEXT                    -- aprobada / stop-loss / automatica
);
CREATE TABLE IF NOT EXISTS equity (
    ts TEXT NOT NULL,
    equity REAL NOT NULL,
    cash REAL NOT NULL,
    benchmark REAL
);
CREATE TABLE IF NOT EXISTS events (
    ts TEXT NOT NULL,
    level TEXT NOT NULL,           -- info / aviso / error
    message TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TEXT NOT NULL,
    status TEXT NOT NULL,          -- activa / candidata / retirada / descartada
    origin TEXT,                   -- inicial / IA / optimizador / manual
    params TEXT NOT NULL,          -- JSON
    playbook TEXT NOT NULL,
    lessons TEXT,                  -- JSON: lista de lecciones
    changelog TEXT,
    diagnosis TEXT,
    metrics TEXT,                  -- JSON: backtest y comparación
    recommended INTEGER
);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    ticker TEXT NOT NULL,
    action TEXT NOT NULL,          -- comprar / vender / mantener
    confidence REAL,
    score REAL,                    -- puntuación de la estrategia
    price REAL NOT NULL,
    bench_price REAL,
    strategy_id INTEGER,
    proposal_id INTEGER,
    features TEXT,                 -- JSON del estudio de mercado
    reason TEXT,
    fwd_return REAL,               -- se rellena al evaluar
    bench_return REAL,
    evaluated TEXT
);
CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.conn() as c:
            c.executescript(SCHEMA)
            cols = {r["name"] for r in c.execute("PRAGMA table_info(proposals)")}
            if "stop_pct" not in cols:  # bases de datos creadas antes del stop por ATR
                c.execute("ALTER TABLE proposals ADD COLUMN stop_pct REAL")

    @contextmanager
    def conn(self):
        c = sqlite3.connect(self.path, timeout=30)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()

    # ---------------------------------------------------------- clave/valor
    def get(self, key: str, default=None):
        with self.conn() as c:
            row = c.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def set(self, key: str, value) -> None:
        with self.conn() as c:
            c.execute("INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))

    @property
    def paused(self) -> bool:
        return bool(self.get("paused", False))

    def set_paused(self, value: bool, reason: str = "") -> None:
        self.set("paused", bool(value))
        self.log("aviso" if value else "info", ("Bot detenido. " + reason).strip() if value else "Bot reanudado.")

    # ---------------------------------------------------------- eventos
    def log(self, level: str, message: str) -> None:
        with self.conn() as c:
            c.execute("INSERT INTO events(ts,level,message) VALUES(?,?,?)", (now_iso(), level, message))

    def events(self, limit: int = 100) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM events ORDER BY rowid DESC LIMIT ?", (limit,))]

    # ---------------------------------------------------------- propuestas
    def add_proposal(self, ticker, side, price, amount=None, units=None, confidence=None, reason="", risks="", checks=None, status="pendiente", stop_pct=None) -> int:
        with self.conn() as c:
            cur = c.execute(
                "INSERT INTO proposals(created,ticker,side,amount,units,price,confidence,reason,risks,checks,status,stop_pct) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (now_iso(), ticker, side, amount, units, price, confidence, reason, risks, json.dumps(checks or [], ensure_ascii=False), status, stop_pct),
            )
            return int(cur.lastrowid)

    def proposal(self, pid: int) -> dict | None:
        with self.conn() as c:
            row = c.execute("SELECT * FROM proposals WHERE id=?", (pid,)).fetchone()
        return self._prop(row) if row else None

    def proposals(self, status: str | None = None, limit: int = 200) -> list[dict]:
        with self.conn() as c:
            if status:
                rows = c.execute("SELECT * FROM proposals WHERE status=? ORDER BY id DESC LIMIT ?", (status, limit))
            else:
                rows = c.execute("SELECT * FROM proposals ORDER BY id DESC LIMIT ?", (limit,))
            return [self._prop(r) for r in rows]

    def update_proposal(self, pid: int, status: str, result: str = "", only_if: str | None = None) -> bool:
        """Cambia el estado. Con only_if, solo si el estado actual coincide (evita aprobar dos veces)."""
        with self.conn() as c:
            if only_if:
                cur = c.execute("UPDATE proposals SET status=?, decided=?, result=? WHERE id=? AND status=?", (status, now_iso(), result, pid, only_if))
            else:
                cur = c.execute("UPDATE proposals SET status=?, decided=?, result=? WHERE id=?", (status, now_iso(), result, pid))
            return cur.rowcount > 0

    @staticmethod
    def _prop(row) -> dict:
        d = dict(row)
        d["checks"] = json.loads(d.get("checks") or "[]")
        return d

    # ---------------------------------------------------------- estrategias
    def add_strategy(self, status, origin, params: dict, playbook: str, lessons=None, changelog="", diagnosis="", metrics=None, recommended=None) -> int:
        with self.conn() as c:
            cur = c.execute(
                "INSERT INTO strategies(created,status,origin,params,playbook,lessons,changelog,diagnosis,metrics,recommended) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (now_iso(), status, origin, json.dumps(params), playbook, json.dumps(lessons or [], ensure_ascii=False), changelog, diagnosis,
                 json.dumps(metrics or {}, ensure_ascii=False, default=str), None if recommended is None else int(recommended)),
            )
            return int(cur.lastrowid)

    def strategies(self, status: str | None = None) -> list[dict]:
        with self.conn() as c:
            q = "SELECT * FROM strategies" + (" WHERE status=?" if status else "") + " ORDER BY id DESC"
            rows = c.execute(q, (status,) if status else ())
            return [self._strat(r) for r in rows]

    def strategy(self, sid: int) -> dict | None:
        with self.conn() as c:
            row = c.execute("SELECT * FROM strategies WHERE id=?", (sid,)).fetchone()
        return self._strat(row) if row else None

    def set_strategy_status(self, sid: int, status: str) -> None:
        with self.conn() as c:
            c.execute("UPDATE strategies SET status=? WHERE id=?", (status, sid))

    def activate_strategy(self, sid: int) -> None:
        """Deja una sola estrategia activa (la anterior pasa a retirada)."""
        with self.conn() as c:
            c.execute("UPDATE strategies SET status='retirada' WHERE status='activa'")
            c.execute("UPDATE strategies SET status='activa' WHERE id=?", (sid,))

    @staticmethod
    def _strat(row) -> dict:
        d = dict(row)
        for k in ("params", "lessons", "metrics"):
            d[k] = json.loads(d.get(k) or ("[]" if k == "lessons" else "{}"))
        return d

    # ---------------------------------------------------------- diario de decisiones
    def add_decision(self, ticker, action, price, confidence=None, score=None, bench_price=None, strategy_id=None, proposal_id=None, features=None, reason="") -> int:
        with self.conn() as c:
            cur = c.execute(
                "INSERT INTO decisions(ts,ticker,action,confidence,score,price,bench_price,strategy_id,proposal_id,features,reason) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (now_iso(), ticker, action, confidence, score, price, bench_price, strategy_id, proposal_id, json.dumps(features or {}, ensure_ascii=False, default=str), reason),
            )
            return int(cur.lastrowid)

    def decisions(self, evaluated: bool | None = None, limit: int = 1000) -> list[dict]:
        with self.conn() as c:
            cond = "" if evaluated is None else (" WHERE evaluated IS NOT NULL" if evaluated else " WHERE evaluated IS NULL")
            rows = c.execute(f"SELECT * FROM decisions{cond} ORDER BY id DESC LIMIT ?", (limit,))
            out = []
            for r in rows:
                d = dict(r)
                d["features"] = json.loads(d.get("features") or "{}")
                out.append(d)
            return out

    def set_outcome(self, did: int, fwd_return: float, bench_return: float | None) -> None:
        with self.conn() as c:
            c.execute("UPDATE decisions SET fwd_return=?, bench_return=?, evaluated=? WHERE id=?", (fwd_return, bench_return, now_iso(), did))

    # ---------------------------------------------------------- operaciones y valor
    def add_trade(self, ticker, side, units, price, amount, fee=0.0, proposal_id=None, origin="aprobada") -> None:
        with self.conn() as c:
            c.execute(
                "INSERT INTO trades(ts,ticker,side,units,price,amount,fee,proposal_id,origin) VALUES(?,?,?,?,?,?,?,?,?)",
                (now_iso(), ticker, side, units, price, amount, fee, proposal_id, origin),
            )

    def trades(self, since: str | None = None, limit: int = 500) -> list[dict]:
        with self.conn() as c:
            if since:
                rows = c.execute("SELECT * FROM trades WHERE ts>=? ORDER BY id DESC LIMIT ?", (since, limit))
            else:
                rows = c.execute("SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(r) for r in rows]

    def add_equity(self, equity: float, cash: float, benchmark: float | None) -> None:
        with self.conn() as c:
            c.execute("INSERT INTO equity(ts,equity,cash,benchmark) VALUES(?,?,?,?)", (now_iso(), equity, cash, benchmark))

    def equity_history(self) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM equity ORDER BY ts")]
