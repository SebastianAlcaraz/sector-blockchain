"""Catálogo de activos de ejemplo, agrupados por clase.

Los símbolos siguen la convención de Yahoo Finance:
  - Acciones/ETF: símbolo normal (AAPL, SPY)
  - Materias primas: contratos de futuros con sufijo "=F" (GC=F = oro)
  - Criptomonedas: par contra dólar (BTC-USD)
  - Índices: prefijo "^" (^GSPC = S&P 500)
  - Divisas: par con sufijo "=X" (EURUSD=X)
"""

CATALOG: dict[str, dict[str, str]] = {
    "Acciones": {
        "AAPL": "Apple",
        "MSFT": "Microsoft",
        "NVDA": "NVIDIA",
        "GOOGL": "Alphabet (Google)",
        "AMZN": "Amazon",
        "META": "Meta Platforms",
        "TSLA": "Tesla",
        "JPM": "JPMorgan Chase",
        "KO": "Coca-Cola",
        "JNJ": "Johnson & Johnson",
        "SAN.MC": "Banco Santander",
        "ITX.MC": "Inditex",
        "MELI": "MercadoLibre",
        "YPF": "YPF",
    },
    "ETF": {
        "SPY": "S&P 500 (SPDR)",
        "QQQ": "Nasdaq 100 (Invesco)",
        "VT": "Mercado mundial (Vanguard)",
        "VWO": "Mercados emergentes (Vanguard)",
        "AGG": "Bonos EE. UU. (iShares)",
        "GLD": "Oro físico (SPDR)",
        "VNQ": "Inmobiliario EE. UU. (Vanguard)",
    },
    "Materias primas": {
        "GC=F": "Oro",
        "SI=F": "Plata",
        "HG=F": "Cobre",
        "PL=F": "Platino",
        "CL=F": "Petróleo WTI",
        "BZ=F": "Petróleo Brent",
        "NG=F": "Gas natural",
        "ZC=F": "Maíz",
        "ZW=F": "Trigo",
        "ZS=F": "Soja",
        "KC=F": "Café",
        "SB=F": "Azúcar",
    },
    "Criptomonedas": {
        "BTC-USD": "Bitcoin",
        "ETH-USD": "Ethereum",
        "SOL-USD": "Solana",
    },
    "Índices": {
        "^GSPC": "S&P 500",
        "^IXIC": "Nasdaq Composite",
        "^DJI": "Dow Jones",
        "^IBEX": "IBEX 35",
        "^MERV": "Merval",
        "^STOXX50E": "Euro Stoxx 50",
    },
    "Divisas": {
        "EURUSD=X": "Euro / Dólar",
        "USDMXN=X": "Dólar / Peso mexicano",
        "USDARS=X": "Dólar / Peso argentino",
    },
}


def all_assets() -> dict[str, str]:
    """Devuelve {símbolo: nombre} con todos los activos del catálogo."""
    out: dict[str, str] = {}
    for group in CATALOG.values():
        out.update(group)
    return out


def asset_class(ticker: str) -> str:
    """Clase de activo de un símbolo; si no está en el catálogo se deduce por su formato."""
    for cls, group in CATALOG.items():
        if ticker in group:
            return cls
    if ticker.endswith("=F"):
        return "Materias primas"
    if ticker.endswith("-USD"):
        return "Criptomonedas"
    if ticker.startswith("^"):
        return "Índices"
    if ticker.endswith("=X"):
        return "Divisas"
    return "Acciones"


def label(ticker: str) -> str:
    """Etiqueta legible: 'Oro (GC=F)'."""
    name = all_assets().get(ticker)
    return f"{name} ({ticker})" if name else ticker
