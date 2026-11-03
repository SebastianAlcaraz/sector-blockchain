"""Brókers: dónde se ejecutan las órdenes.

- PaperBroker: simulación local con dinero ficticio (precios reales, aplica un coste por operación).
- EToroDemoBroker: cuenta DEMO de eToro. EXPERIMENTAL y solo demo: no existe ninguna clase
  que opere con dinero real, a propósito.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..news import EToroClient, EToroError, to_etoro_symbol
from .store import Store


@dataclass
class Position:
    units: float
    avg_price: float
    stop_price: float | None = None
    position_ids: tuple = ()  # identificadores en eToro (si aplica)


@dataclass
class Fill:
    units: float
    price: float
    amount: float
    fee: float


class BrokerError(RuntimeError):
    pass


class PaperBroker:
    name = "Simulación local"

    def __init__(self, store: Store, initial_cash: float, spread_pct: float = 0.15):
        self.store = store
        self.spread = spread_pct / 100
        if store.get("paper_cash") is None:
            store.set("paper_cash", float(initial_cash))
            store.set("paper_positions", {})
            store.log("info", f"Simulación iniciada con {initial_cash:,.2f} de capital ficticio.")

    def cash(self) -> float:
        return float(self.store.get("paper_cash", 0.0))

    def positions(self) -> dict[str, Position]:
        raw = self.store.get("paper_positions", {}) or {}
        return {t: Position(p["units"], p["avg_price"], p.get("stop_price")) for t, p in raw.items() if p["units"] > 1e-12}

    def _save(self, cash: float, positions: dict[str, Position]) -> None:
        self.store.set("paper_cash", cash)
        self.store.set("paper_positions", {t: {"units": p.units, "avg_price": p.avg_price, "stop_price": p.stop_price} for t, p in positions.items() if p.units > 1e-12})

    def buy(self, ticker: str, amount: float, price: float, stop_price: float | None = None) -> Fill:
        cash = self.cash()
        if amount > cash + 1e-9:
            raise BrokerError(f"Efectivo insuficiente: hay {cash:,.2f} y se necesitan {amount:,.2f}.")
        fill_price = price * (1 + self.spread / 2)
        units = amount / fill_price
        fee = amount - units * price
        positions = self.positions()
        old = positions.get(ticker)
        if old:
            total_units = old.units + units
            avg = (old.units * old.avg_price + units * fill_price) / total_units
            positions[ticker] = Position(total_units, avg, stop_price or old.stop_price)
        else:
            positions[ticker] = Position(units, fill_price, stop_price)
        self._save(cash - amount, positions)
        return Fill(units, fill_price, amount, fee)

    def sell(self, ticker: str, units: float, price: float) -> Fill:
        positions = self.positions()
        pos = positions.get(ticker)
        if not pos or pos.units <= 0:
            raise BrokerError(f"No hay posición en {ticker}.")
        units = min(units, pos.units)
        fill_price = price * (1 - self.spread / 2)
        amount = units * fill_price
        fee = units * price - amount
        pos.units -= units
        if pos.units <= 1e-9:
            positions.pop(ticker)
        self._save(self.cash() + amount, positions)
        return Fill(units, fill_price, amount, fee)

    def equity(self, prices: dict[str, float]) -> float:
        return self.cash() + sum(p.units * prices.get(t, p.avg_price) for t, p in self.positions().items())


class EToroDemoBroker:
    """Cuenta demo de eToro a través de la API pública.

    SIN PROBAR con una cuenta real: las rutas y los nombres de campos proceden de la documentación
    pública y pueden necesitar ajustes. Todas las rutas contienen '/demo/' y se comprueba antes
    de cada llamada, para que nunca se pueda operar con la cuenta real por error.
    """

    name = "eToro (demo)"
    PORTFOLIO_PATH = "/trading/info/demo/portfolio"
    OPEN_BY_AMOUNT_PATH = "/trading/execution/demo/market-open-orders/by-amount"
    CLOSE_PATH = "/trading/execution/demo/market-close-orders/positions/{position_id}"

    def __init__(self, client: EToroClient | None = None, universe: list[str] | None = None):
        self.client = client or EToroClient()
        if not EToroClient.configured() and client is None:
            raise BrokerError("Faltan las claves de eToro (ETORO_API_KEY y ETORO_USER_KEY).")
        self._ids: dict[str, int] = {t: v["instrumentId"] for t, v in self.client.cache.items() if v}
        self._symbols: dict[int, str] = {i: t for t, i in self._ids.items()}
        self.universe = universe or []

    def _call(self, method: str, path: str, body: dict | None = None):
        if "/demo/" not in path:
            raise BrokerError("Bloqueado: el bot solo puede operar en la cuenta demo de eToro.")
        try:
            return self.client._request(method, path, body=body)
        except EToroError as e:
            raise BrokerError(str(e)) from e

    def instrument_id(self, ticker: str) -> int:
        if ticker not in self._ids:
            try:
                iid = self.client.find_instrument_id(to_etoro_symbol(ticker))
            except EToroError as e:
                raise BrokerError(str(e)) from e
            if iid is None:
                raise BrokerError(f"eToro no reconoce el activo {ticker}.")
            self._ids[ticker] = iid
            self._symbols[iid] = ticker
        return self._ids[ticker]

    def _portfolio(self) -> dict:
        data = self._call("GET", self.PORTFOLIO_PATH)
        if isinstance(data, dict) and isinstance(data.get("clientPortfolio"), dict):
            data = data["clientPortfolio"]
        if not isinstance(data, dict):
            raise BrokerError("eToro devolvió una cartera con un formato inesperado.")
        return data

    def cash(self) -> float:
        p = self._portfolio()
        for key in ("credit", "availableCash", "cash", "balance"):
            if isinstance(p.get(key), (int, float)):
                return float(p[key])
        raise BrokerError("No se encontró el efectivo disponible en la respuesta de eToro.")

    def positions(self) -> dict[str, Position]:
        out: dict[str, Position] = {}
        raw_positions = self._portfolio().get("positions", []) or []
        # Traduce identificadores de eToro a símbolos: resuelve los activos del universo que falten.
        unknown = {r.get("instrumentID") or r.get("instrumentId") for r in raw_positions} - set(self._symbols)
        for t in self.universe:
            if not unknown:
                break
            if t not in self._ids:
                try:
                    iid = self.instrument_id(t)
                    unknown.discard(iid)
                except BrokerError:
                    continue
        for raw in raw_positions:
            if raw.get("mirrorID") or raw.get("mirrorId"):
                continue  # posiciones de copy trading: no las gestiona el bot
            iid = raw.get("instrumentID") or raw.get("instrumentId")
            ticker = self._symbols.get(iid, f"eToro:{iid}")
            units = float(raw.get("units") or raw.get("amount", 0) / max(float(raw.get("openRate") or 1), 1e-9))
            rate = float(raw.get("openRate") or 0)
            stop = None if raw.get("isNoStopLoss") else raw.get("stopLossRate")
            pid = raw.get("positionID") or raw.get("positionId")
            if ticker in out:
                old = out[ticker]
                total = old.units + units
                out[ticker] = Position(total, (old.units * old.avg_price + units * rate) / total, old.stop_price, old.position_ids + (pid,))
            else:
                out[ticker] = Position(units, rate, float(stop) if stop else None, (pid,))
        return out

    def buy(self, ticker: str, amount: float, price: float, stop_price: float | None = None) -> Fill:
        body = {"InstrumentID": self.instrument_id(ticker), "IsBuy": True, "Leverage": 1, "Amount": round(amount, 2)}
        if stop_price:
            body["StopLossRate"] = round(stop_price, 6)
        self._call("POST", self.OPEN_BY_AMOUNT_PATH, body)
        return Fill(amount / price, price, amount, 0.0)

    def sell(self, ticker: str, units: float, price: float) -> Fill:
        pos = self.positions().get(ticker)
        if not pos:
            raise BrokerError(f"No hay posición en {ticker} en la cuenta demo.")
        # eToro cierra posiciones completas: se cierran las necesarias hasta cubrir las unidades pedidas.
        for pid in pos.position_ids:
            self._call("POST", self.CLOSE_PATH.format(position_id=pid), {})
        closed = pos.units
        return Fill(closed, price, closed * price, 0.0)

    def equity(self, prices: dict[str, float]) -> float:
        return self.cash() + sum(p.units * prices.get(t, p.avg_price) for t, p in self.positions().items())
