"""Asistente de inversión: acciones, ETF, materias primas, cripto, índices y divisas.

Ejecutar con:  streamlit run app.py
"""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from invest import analysis, portfolio, simulator
from invest.catalog import CATALOG, all_assets, asset_class, label
from invest.data import DemoSource, YahooSource
from invest.indicators import bollinger, macd, rsi, sma

APP_DIR = Path(__file__).parent
PORTFOLIO_FILE = APP_DIR / "data" / "cartera.json"

# Paleta categórica validada (orden fijo; el color sigue al activo, no a su posición).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
UP, DOWN, MUTED = "#1baf7a", "#e34948", "#8a8984"
PERIODS = {"1 mes": "1mo", "3 meses": "3mo", "6 meses": "6mo", "1 año": "1y", "2 años": "2y", "5 años": "5y", "10 años": "10y"}

st.set_page_config(page_title="Asistente de inversión", page_icon="📈", layout="wide")


# ---------------------------------------------------------------- utilidades
def pct(x: float, signed: bool = False) -> str:
    if x is None or pd.isna(x):
        return "—"
    return f"{x:+.2%}" if signed else f"{x:.2%}"


def money(x: float) -> str:
    return "—" if x is None or pd.isna(x) else f"{x:,.2f}"


def style_chart(fig: go.Figure, height: int = 420) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        colorway=SERIES,
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridwidth=0.5)
    return fig


@st.cache_data(ttl=900, show_spinner="Descargando cotizaciones…")
def load_closes(source_name: str, tickers: tuple[str, ...], period: str) -> pd.DataFrame:
    source = DemoSource() if source_name == DemoSource.name else YahooSource()
    return source.closes(list(tickers), period)


def get_closes(tickers: list[str], period: str) -> pd.DataFrame:
    try:
        df = load_closes(SOURCE, tuple(tickers), period)
    except Exception as exc:  # red caída, símbolo raro, límite de Yahoo…
        st.error(f"No se pudieron descargar los datos: {exc}")
        return pd.DataFrame()
    missing = [t for t in tickers if t not in df.columns]
    if missing:
        st.warning("Sin datos para: " + ", ".join(missing) + ". Comprueba el símbolo o prueba con el modo demo.")
    return df


def ticker_picker(key: str, default: str = "AAPL") -> str:
    assets = all_assets()
    options = list(assets) + ["Otro…"]
    choice = st.selectbox("Activo", options, index=options.index(default), format_func=lambda t: t if t == "Otro…" else label(t), key=key)
    if choice == "Otro…":
        choice = st.text_input("Símbolo de Yahoo Finance (p. ej. BABA, ^N225, GGAL.BA)", key=key + "_custom").strip().upper()
    return choice


# ---------------------------------------------------------------- barra lateral
st.sidebar.title("📈 Asistente de inversión")
page = st.sidebar.radio(
    "Sección",
    ["Panorama de mercado", "Análisis de un activo", "Comparar activos", "Mi cartera", "Simulador de aportaciones", "Guía rápida"],
)
SOURCE = st.sidebar.radio(
    "Fuente de datos",
    [YahooSource.name, DemoSource.name],
    help="Yahoo Finance da cotizaciones reales (con ~15 min de retraso). El modo demo usa precios simulados y funciona sin conexión.",
)
if SOURCE == DemoSource.name:
    st.sidebar.info("Estás viendo **precios simulados**. No los uses para decidir.")
st.sidebar.caption(
    "⚠️ Herramienta educativa y de análisis. No es asesoramiento financiero: "
    "invertir conlleva riesgo de pérdida. Contrasta siempre la información."
)


# ---------------------------------------------------------------- páginas
def page_market() -> None:
    st.header("Panorama de mercado")
    classes = st.multiselect("Clases de activo", list(CATALOG), default=["Acciones", "Materias primas", "Criptomonedas", "Índices"])
    tickers = [t for c in classes for t in CATALOG[c]]
    if not tickers:
        st.info("Elige al menos una clase de activo.")
        return
    closes = get_closes(tickers, "1y")
    if closes.empty:
        return

    rows = []
    for t in closes.columns:
        s = closes[t].dropna()
        if len(s) < 2:
            continue
        look = analysis.technical_outlook(s)

        def change(days: int) -> float:
            past = s[s.index <= s.index[-1] - pd.Timedelta(days=days)]
            return s.iloc[-1] / past.iloc[-1] - 1 if len(past) else float("nan")

        rows.append(
            {
                "Activo": all_assets().get(t, t),
                "Símbolo": t,
                "Clase": asset_class(t),
                "Precio": s.iloc[-1],
                "1 día": s.iloc[-1] / s.iloc[-2] - 1,
                "1 mes": change(30),
                "1 año": s.iloc[-1] / s.iloc[0] - 1,
                "Volatilidad": analysis.annual_volatility(s),
                "Lectura técnica": look.verdict,
                "Puntuación": look.score,
            }
        )
    table = pd.DataFrame(rows)
    st.caption("La *lectura técnica* combina medias móviles, MACD y RSI en una puntuación de -100 a +100. Es orientativa.")
    st.dataframe(
        table,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Precio": st.column_config.NumberColumn(format="%.2f"),
            "1 día": st.column_config.NumberColumn(format="percent"),
            "1 mes": st.column_config.NumberColumn(format="percent"),
            "1 año": st.column_config.NumberColumn(format="percent"),
            "Volatilidad": st.column_config.NumberColumn(format="percent"),
            "Puntuación": st.column_config.ProgressColumn(min_value=-100, max_value=100, format="%d"),
        },
    )

    st.subheader("Mejores y peores del último año")
    ranked = table.dropna(subset=["1 año"]).sort_values("1 año")
    shown = pd.concat([ranked.head(5), ranked.tail(5)]).drop_duplicates("Símbolo")
    fig = go.Figure(
        go.Bar(
            x=shown["1 año"],
            y=shown["Activo"],
            orientation="h",
            marker_color=[UP if v >= 0 else DOWN for v in shown["1 año"]],
            hovertemplate="%{y}: %{x:+.1%}<extra></extra>",
        )
    )
    fig.update_xaxes(tickformat="+.0%")
    st.plotly_chart(style_chart(fig, 380).update_layout(hovermode="closest"), use_container_width=True)


def page_asset() -> None:
    st.header("Análisis de un activo")
    c1, c2, c3 = st.columns([3, 2, 2])
    with c1:
        ticker = ticker_picker("asset")
    with c2:
        period = PERIODS[st.select_slider("Periodo", list(PERIODS), value="2 años")]
    with c3:
        rf = st.number_input("Tasa libre de riesgo anual (%)", 0.0, 20.0, 4.0, 0.25) / 100
    if not ticker:
        return
    closes = get_closes([ticker], period)
    if ticker not in closes:
        return
    close = closes[ticker].dropna()

    m = analysis.summary(close, rf)
    cols = st.columns(6)
    cols[0].metric("Último precio", money(close.iloc[-1]), pct(close.iloc[-1] / close.iloc[-2] - 1, True) if len(close) > 1 else None)
    cols[1].metric("Rentabilidad del periodo", pct(m["Rentabilidad total"], True))
    cols[2].metric("Rentabilidad anual", pct(m["Rentabilidad anual (CAGR)"], True))
    cols[3].metric("Volatilidad anual", pct(m["Volatilidad anual"]))
    cols[4].metric("Sharpe", "—" if pd.isna(m["Sharpe"]) else f"{m['Sharpe']:.2f}")
    cols[5].metric("Máxima caída", pct(m["Máxima caída"]))

    show_bb = st.toggle("Mostrar bandas de Bollinger", value=False)
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.04)
    fig.add_trace(go.Scatter(x=close.index, y=close, name="Precio", line=dict(color=SERIES[0], width=2)), 1, 1)
    fig.add_trace(go.Scatter(x=close.index, y=sma(close, 50), name="Media 50", line=dict(color=SERIES[1], width=1.5)), 1, 1)
    fig.add_trace(go.Scatter(x=close.index, y=sma(close, 200), name="Media 200", line=dict(color=SERIES[6], width=1.5)), 1, 1)
    if show_bb:
        bb = bollinger(close)
        fig.add_trace(go.Scatter(x=close.index, y=bb["upper"], name="Bollinger sup.", line=dict(color=MUTED, width=1, dash="dot")), 1, 1)
        fig.add_trace(go.Scatter(x=close.index, y=bb["lower"], name="Bollinger inf.", line=dict(color=MUTED, width=1, dash="dot")), 1, 1)
    r = rsi(close)
    fig.add_trace(go.Scatter(x=close.index, y=r, name="RSI", line=dict(color=SERIES[2], width=1.5)), 2, 1)
    fig.add_hline(y=70, line=dict(color=MUTED, width=1, dash="dash"), row=2, col=1)
    fig.add_hline(y=30, line=dict(color=MUTED, width=1, dash="dash"), row=2, col=1)
    md = macd(close)
    fig.add_trace(go.Bar(x=close.index, y=md["hist"], name="Histograma MACD", marker_color=[UP if v >= 0 else DOWN for v in md["hist"].fillna(0)]), 3, 1)
    fig.add_trace(go.Scatter(x=close.index, y=md["macd"], name="MACD", line=dict(color=SERIES[0], width=1.5)), 3, 1)
    fig.add_trace(go.Scatter(x=close.index, y=md["signal"], name="Señal", line=dict(color=SERIES[1], width=1.5)), 3, 1)
    fig.update_yaxes(title_text="Precio", row=1, col=1)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)
    fig.update_yaxes(title_text="MACD", row=3, col=1)
    st.plotly_chart(style_chart(fig, 680), use_container_width=True)

    left, right = st.columns(2)
    with left:
        look = analysis.technical_outlook(close)
        st.subheader(f"Lectura técnica: {look.verdict} ({look.score:+d})")
        for reason in look.reasons:
            st.markdown(f"- {reason}")
        st.caption("Basada solo en el precio pasado. No predice el futuro ni tiene en cuenta noticias o fundamentales.")
    with right:
        st.subheader("Caídas desde máximos")
        dd = analysis.drawdown(close)
        f2 = go.Figure(go.Scatter(x=dd.index, y=dd, fill="tozeroy", line=dict(color=DOWN, width=1.5), name="Caída", hovertemplate="%{y:.1%}<extra></extra>"))
        f2.update_yaxes(tickformat=".0%")
        st.plotly_chart(style_chart(f2, 300), use_container_width=True)


def page_compare() -> None:
    st.header("Comparar activos")
    assets = all_assets()
    c1, c2 = st.columns([4, 2])
    with c1:
        tickers = st.multiselect("Activos (hasta 8)", list(assets), default=["SPY", "GC=F", "BTC-USD", "CL=F"], format_func=label, max_selections=8)
        extra = st.text_input("Otros símbolos separados por comas (opcional)")
        tickers += [t.strip().upper() for t in extra.split(",") if t.strip()][: 8 - len(tickers)]
    with c2:
        period = PERIODS[st.select_slider("Periodo", list(PERIODS), value="1 año", key="cmp_period")]
    if len(tickers) < 2:
        st.info("Elige al menos dos activos.")
        return
    closes = get_closes(tickers, period)
    if closes.shape[1] < 2:
        return
    # El color sigue al activo según su posición en la selección del usuario.
    colors = {t: SERIES[i % len(SERIES)] for i, t in enumerate(tickers)}

    st.subheader("Evolución (base 100)")
    norm = closes.apply(lambda s: 100 * s / s.dropna().iloc[0])
    fig = go.Figure()
    for t in norm.columns:
        fig.add_trace(go.Scatter(x=norm.index, y=norm[t], name=label(t), line=dict(color=colors[t], width=2)))
    st.plotly_chart(style_chart(fig), use_container_width=True)

    st.subheader("Rentabilidad y riesgo")
    metrics = pd.DataFrame({label(t): analysis.summary(closes[t]) for t in closes.columns}).T
    st.dataframe(
        metrics,
        use_container_width=True,
        column_config={k: st.column_config.NumberColumn(format="percent") for k in metrics.columns if k != "Sharpe"}
        | {"Sharpe": st.column_config.NumberColumn(format="%.2f")},
    )

    st.subheader("Correlación de rentabilidades diarias")
    st.caption("Cerca de +1: se mueven juntos. Cerca de 0: independientes. Negativa: tienden a moverse en sentido contrario. Combinar activos poco correlacionados reduce el riesgo de la cartera.")
    corr = analysis.correlation_matrix(closes)
    names = [label(t) for t in corr.columns]
    heat = go.Figure(
        go.Heatmap(
            z=corr.values,
            x=names,
            y=names,
            zmin=-1,
            zmax=1,
            colorscale=[[0, "#2a78d6"], [0.5, "#e8e7e3"], [1, "#e34948"]],
            text=corr.round(2).values,
            texttemplate="%{text}",
            hovertemplate="%{y} / %{x}: %{z:.2f}<extra></extra>",
        )
    )
    st.plotly_chart(style_chart(heat, 460).update_layout(hovermode="closest"), use_container_width=True)


def page_portfolio() -> None:
    st.header("Mi cartera")
    if "positions" not in st.session_state:
        st.session_state.positions = portfolio.load_positions(PORTFOLIO_FILE)

    st.caption(
        "Añade tus posiciones: símbolo de Yahoo Finance, cantidad y precio medio de compra. "
        f"Se guardan en `{PORTFOLIO_FILE.relative_to(APP_DIR)}` en tu equipo."
    )
    edited = st.data_editor(
        st.session_state.positions,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "ticker": st.column_config.TextColumn("Símbolo", help="Ej.: AAPL, GC=F, BTC-USD"),
            "cantidad": st.column_config.NumberColumn("Cantidad", min_value=0.0, format="%.6g"),
            "precio_medio": st.column_config.NumberColumn("Precio medio", min_value=0.0, format="%.4f"),
        },
        key="positions_editor",
    )
    b1, b2, _ = st.columns([1, 1, 4])
    if b1.button("💾 Guardar cartera", type="primary"):
        portfolio.save_positions(edited, PORTFOLIO_FILE)
        st.session_state.positions = portfolio.clean_positions(edited)
        st.success("Cartera guardada.")
    if b2.button("Cargar ejemplo"):
        st.session_state.positions = pd.DataFrame(
            [
                {"ticker": "SPY", "cantidad": 10, "precio_medio": 450},
                {"ticker": "AAPL", "cantidad": 15, "precio_medio": 170},
                {"ticker": "GC=F", "cantidad": 1, "precio_medio": 2000},
                {"ticker": "BTC-USD", "cantidad": 0.05, "precio_medio": 40000},
                {"ticker": "AGG", "cantidad": 20, "precio_medio": 98},
            ]
        )
        st.session_state.pop("positions_editor", None)
        st.rerun()

    positions = portfolio.clean_positions(edited)
    if positions.empty:
        st.info("Tu cartera está vacía. Añade filas en la tabla o pulsa «Cargar ejemplo».")
        return
    closes = get_closes(positions["ticker"].tolist(), "1y")
    if closes.empty:
        return
    prices = {t: float(closes[t].dropna().iloc[-1]) for t in closes.columns if closes[t].notna().any()}
    valued = portfolio.valuate(positions, prices)

    total_val, total_cost = valued["valor"].sum(), valued["coste"].sum()
    k = st.columns(3)
    k[0].metric("Valor actual", money(total_val))
    k[1].metric("Invertido", money(total_cost))
    k[2].metric("Ganancia / pérdida", money(total_val - total_cost), pct((total_val - total_cost) / total_cost, True) if total_cost else None)
    st.caption("Los importes se muestran en la moneda de cotización de cada activo; si mezclas monedas, los totales son aproximados.")

    st.dataframe(
        valued[["ticker", "clase", "cantidad", "precio_medio", "precio_actual", "coste", "valor", "ganancia", "ganancia_pct", "peso"]],
        hide_index=True,
        use_container_width=True,
        column_config={
            "ticker": "Símbolo",
            "clase": "Clase",
            "cantidad": st.column_config.NumberColumn("Cantidad", format="%.6g"),
            "precio_medio": st.column_config.NumberColumn("Precio medio", format="%.2f"),
            "precio_actual": st.column_config.NumberColumn("Precio actual", format="%.2f"),
            "coste": st.column_config.NumberColumn("Coste", format="%.2f"),
            "valor": st.column_config.NumberColumn("Valor", format="%.2f"),
            "ganancia": st.column_config.NumberColumn("Ganancia", format="%.2f"),
            "ganancia_pct": st.column_config.NumberColumn("Ganancia %", format="percent"),
            "peso": st.column_config.NumberColumn("Peso", format="percent"),
        },
    )

    left, right = st.columns(2)
    with left:
        st.subheader("Distribución por clase")
        alloc = portfolio.allocation_by_class(valued)
        fig = go.Figure(go.Bar(x=alloc.values, y=alloc.index, orientation="h", marker_color=SERIES[0], hovertemplate="%{y}: %{x:.1%}<extra></extra>"))
        fig.update_xaxes(tickformat=".0%")
        st.plotly_chart(style_chart(fig, 300).update_layout(hovermode="closest"), use_container_width=True)
        top = valued["peso"].max()
        if top > 0.4:
            st.warning(f"Concentración alta: {valued.loc[valued['peso'].idxmax(), 'ticker']} pesa {top:.0%} de la cartera.")
    with right:
        st.subheader("Valor histórico (posiciones actuales)")
        qty = valued.set_index("ticker")["cantidad"]
        hist = (closes[qty.index.intersection(closes.columns)] * qty).sum(axis=1)
        f2 = go.Figure(go.Scatter(x=hist.index, y=hist, line=dict(color=SERIES[0], width=2), name="Valor"))
        st.plotly_chart(style_chart(f2, 300), use_container_width=True)

    st.subheader("Rebalanceo")
    st.caption("Indica la distribución objetivo por clase de activo; la app calcula cuánto comprar (+) o vender (−) de cada clase.")
    classes = sorted(set(valued["clase"]) | {"Acciones", "ETF", "Materias primas", "Criptomonedas"})
    current = portfolio.allocation_by_class(valued)
    cols = st.columns(len(classes))
    targets = {}
    for col, cls in zip(cols, classes):
        targets[cls] = col.number_input(cls, 0, 100, int(round(100 * current.get(cls, 0.0))), 5, key=f"tgt_{cls}") / 100
    total_target = sum(targets.values())
    if abs(total_target - 1) > 1e-6:
        st.warning(f"Los objetivos suman {total_target:.0%}; deben sumar 100 %.")
    else:
        reb = portfolio.rebalance(valued, targets)
        st.dataframe(
            reb,
            hide_index=True,
            use_container_width=True,
            column_config={
                "clase": "Clase",
                "peso_actual": st.column_config.NumberColumn("Peso actual", format="percent"),
                "peso_objetivo": st.column_config.NumberColumn("Peso objetivo", format="percent"),
                "ajuste": st.column_config.NumberColumn("Comprar (+) / vender (−)", format="%.2f"),
            },
        )


def page_simulator() -> None:
    st.header("Simulador de aportaciones")
    st.caption("¿Qué habría pasado si hubieras invertido en el pasado? Compara aportar cada mes (DCA) con invertir todo de golpe.")
    c1, c2, c3 = st.columns(3)
    with c1:
        ticker = ticker_picker("sim", default="SPY")
    with c2:
        period = PERIODS[st.select_slider("Periodo", list(PERIODS), value="5 años", key="sim_period")]
    with c3:
        monthly = st.number_input("Aportación mensual", 10.0, 1_000_000.0, 200.0, 10.0)
    if not ticker:
        return
    closes = get_closes([ticker], period)
    if ticker not in closes:
        return
    close = closes[ticker].dropna()
    d = simulator.dca(close, monthly)
    ls = simulator.lump_sum(close, d.invested)

    k = st.columns(4)
    k[0].metric("Total aportado", money(d.invested))
    k[1].metric("Resultado con DCA", money(d.final_value), pct(d.profit_pct, True))
    k[2].metric("Resultado invirtiendo todo al inicio", money(ls.final_value), pct(ls.profit_pct, True))
    k[3].metric("Diferencia", money(d.final_value - ls.final_value))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d.history.index, y=d.history["valor"], name="Valor con DCA", line=dict(color=SERIES[0], width=2)))
    fig.add_trace(go.Scatter(x=ls.history.index, y=ls.history["valor"], name="Valor invirtiendo todo al inicio", line=dict(color=SERIES[1], width=2)))
    fig.add_trace(go.Scatter(x=d.history.index, y=d.history["aportado"], name="Dinero aportado (DCA)", line=dict(color=MUTED, width=1.5, dash="dash")))
    st.plotly_chart(style_chart(fig), use_container_width=True)
    st.caption("Rentabilidades pasadas no garantizan rentabilidades futuras. No incluye comisiones, impuestos ni tipo de cambio.")


def page_guide() -> None:
    st.header("Guía rápida")
    st.markdown(
        """
**Cómo usar la app**
1. *Panorama de mercado*: vistazo general de acciones, materias primas, cripto e índices.
2. *Análisis de un activo*: gráfico con medias móviles, RSI y MACD, métricas de riesgo y una lectura técnica explicada.
3. *Comparar activos*: rentabilidad, riesgo y correlación para diversificar mejor.
4. *Mi cartera*: registra lo que tienes, mira tu ganancia y cómo rebalancear.
5. *Simulador*: prueba con datos históricos aportar cada mes frente a invertir de golpe.

**Símbolos (Yahoo Finance)**
| Tipo | Ejemplos |
|---|---|
| Acciones EE. UU. | `AAPL`, `MSFT`, `KO` |
| Acciones de otros mercados | `SAN.MC` (Madrid), `GGAL.BA` (Buenos Aires), `WALMEX.MX` (México) |
| Materias primas (futuros) | `GC=F` oro, `SI=F` plata, `CL=F` petróleo, `ZW=F` trigo |
| Criptomonedas | `BTC-USD`, `ETH-USD` |
| Índices | `^GSPC` S&P 500, `^IBEX`, `^MERV` |
| Divisas | `EURUSD=X`, `USDMXN=X` |

**Glosario**
- **CAGR**: rentabilidad anual compuesta media del periodo.
- **Volatilidad**: cuánto oscila el precio; más volatilidad = más riesgo.
- **Sharpe**: rentabilidad extra por unidad de riesgo. > 1 suele considerarse bueno.
- **Máxima caída (drawdown)**: la peor caída desde un máximo; mide cuánto dolor habrías aguantado.
- **Media móvil 50/200**: precio medio de las últimas 50/200 sesiones; indica la tendencia.
- **RSI**: de 0 a 100; > 70 sobrecompra, < 30 sobreventa.
- **MACD**: diferencia entre dos medias exponenciales; mide el impulso.
- **DCA**: invertir una cantidad fija periódicamente, sin intentar adivinar el mejor momento.

**Principios básicos**
- Diversifica entre clases de activo y regiones; evita que una sola posición pese demasiado.
- Invierte a largo plazo solo dinero que no vayas a necesitar pronto y ten un fondo de emergencia.
- Las materias primas se suelen invertir mediante ETF (p. ej. `GLD` para oro) en lugar de futuros, que tienen vencimientos y apalancamiento.
- Vigila comisiones e impuestos: reducen mucho la rentabilidad con el tiempo.
"""
    )
    st.warning("Esta aplicación no es asesoramiento financiero. Consulta con un profesional antes de tomar decisiones importantes.")


{
    "Panorama de mercado": page_market,
    "Análisis de un activo": page_asset,
    "Comparar activos": page_compare,
    "Mi cartera": page_portfolio,
    "Simulador de aportaciones": page_simulator,
    "Guía rápida": page_guide,
}[page]()
