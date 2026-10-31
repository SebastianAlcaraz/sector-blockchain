"""Asistente de inversión: acciones, ETF, materias primas, cripto, índices y divisas.

Ejecutar con:  streamlit run app.py
"""

import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from invest import analysis, news, portfolio, sentiment, simulator
from invest.catalog import CATALOG, all_assets, asset_class, label
from invest.data import DemoSource, YahooSource
from invest.indicators import bollinger, macd, rsi, sma
from invest.trading import config as bot_config
from invest.trading.broker import BrokerError
from invest.trading.engine import Engine

APP_DIR = Path(__file__).parent
PORTFOLIO_FILE = APP_DIR / "data" / "cartera.json"

# Paleta categórica validada (orden fijo; el color sigue al activo, no a su posición).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
UP, DOWN, MUTED = "#1baf7a", "#e34948", "#8a8984"
PERIODS = {"1 mes": "1mo", "3 meses": "3mo", "6 meses": "6mo", "1 año": "1y", "2 años": "2y", "5 años": "5y", "10 años": "10y"}

st.set_page_config(page_title="Asistente de inversión", page_icon="📈", layout="wide")


def require_password() -> None:
    """Si existe APP_PASSWORD, pide la contraseña antes de mostrar nada (la web puede aprobar operaciones)."""
    import hmac

    expected = os.environ.get("APP_PASSWORD", "")
    if not expected or st.session_state.get("auth_ok"):
        return
    st.title("📈 Asistente de inversión")
    pwd = st.text_input("Contraseña", type="password")
    if pwd:
        if hmac.compare_digest(pwd.encode(), expected.encode()):
            st.session_state.auth_ok = True
            st.rerun()
        st.error("Contraseña incorrecta.")
    st.stop()


require_password()


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


@st.cache_data(ttl=900, show_spinner="Buscando noticias…")
def load_news(source_name: str, ticker: str, limit: int = 20) -> list[news.NewsItem]:
    if source_name == DemoSource.name:
        return news.demo_news(ticker, all_assets().get(ticker, ticker), limit)
    return news.yahoo_news(ticker, limit)


@st.cache_data(ttl=600, show_spinner="Leyendo la comunidad de eToro…")
def load_etoro_posts(ticker: str) -> list[news.NewsItem]:
    return news.EToroClient().instrument_posts(ticker)


@st.cache_data(ttl=1800, show_spinner="Analizando el sentimiento…")
def analyze_texts(analyzer_name: str, texts: tuple[str, ...], context: str) -> tuple[list[sentiment.Scored], str, str]:
    """Devuelve (puntuaciones, resumen, analizador usado). Si Claude falla, usa el diccionario."""
    if analyzer_name == sentiment.ClaudeAnalyzer.name:
        try:
            scored, summary = sentiment.ClaudeAnalyzer().score_many(list(texts), context)
            return scored, summary, analyzer_name
        except Exception as exc:  # sin clave, sin red, límite de uso…
            scored, _ = sentiment.LexiconAnalyzer().score_many(list(texts))
            return scored, f"No se pudo usar Claude ({type(exc).__name__}); se usó el diccionario.", sentiment.LexiconAnalyzer.name
    scored, summary = sentiment.LexiconAnalyzer().score_many(list(texts))
    return scored, summary, analyzer_name


def news_sentiment(ticker: str, limit: int = 20):
    """Noticias de un activo con su sentimiento. Devuelve (items, puntuaciones, agregado, resumen, analizador)."""
    try:
        items = load_news(SOURCE, ticker, limit)
    except Exception as exc:
        st.error(f"No se pudieron descargar las noticias: {exc}")
        return [], [], sentiment.aggregate([]), "", ANALYZER
    if not items:
        return [], [], sentiment.aggregate([]), "", ANALYZER
    scored, summary, used = analyze_texts(ANALYZER, tuple(i.text for i in items), label(ticker))
    return items, scored, sentiment.aggregate(scored, [i.published for i in items]), summary, used


SENT_ICON = {"Positivo": "🟢", "Neutral": "⚪", "Negativo": "🔴"}


def sentiment_header(agg: sentiment.Aggregate, what: str = "noticias") -> None:
    c = st.columns(4)
    c[0].metric("Sentimiento", agg.label, f"{agg.score:+.2f}", delta_color="normal" if agg.label != "Neutral" else "off")
    c[1].metric("🟢 Positivas", agg.positive)
    c[2].metric("⚪ Neutrales", agg.neutral)
    c[3].metric("🔴 Negativas", agg.negative)
    st.caption(f"Puntuación de −1 a +1 calculada sobre {agg.total} {what}; las más recientes pesan más.")


def render_items(items: list[news.NewsItem], scored: list[sentiment.Scored]) -> None:
    for item, sc in zip(items, scored):
        when = item.published.strftime("%d/%m/%Y %H:%M") if item.published else ""
        title = f"[{item.title}]({item.url})" if item.url else item.title
        meta = " · ".join(x for x in [item.source, when] if x)
        st.markdown(f"{SENT_ICON[sc.label]} **{title}**  \n<span style='opacity:.7;font-size:.85em'>{meta} · {sc.label} ({sc.score:+.2f}) — {sc.reason}</span>", unsafe_allow_html=True)


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
    ["Panorama de mercado", "Análisis de un activo", "Noticias y sentimiento", "Comparar activos", "Mi cartera", "Simulador de aportaciones", "Bot de inversión", "Guía rápida"],
)
SOURCE = st.sidebar.radio(
    "Fuente de datos",
    [YahooSource.name, DemoSource.name],
    help="Yahoo Finance da cotizaciones reales (con ~15 min de retraso). El modo demo usa precios simulados y funciona sin conexión.",
)
if SOURCE == DemoSource.name:
    st.sidebar.info("Estás viendo **precios y noticias simulados**. No los uses para decidir.")
ANALYZER = st.sidebar.radio(
    "Análisis de sentimiento",
    [sentiment.LexiconAnalyzer.name, sentiment.ClaudeAnalyzer.name],
    help=(
        "El diccionario es gratis y funciona sin conexión, pero es aproximado. "
        "La IA (Claude) entiende el contexto y redacta un resumen; necesita la variable ANTHROPIC_API_KEY "
        "y cada análisis tiene un pequeño coste en tu cuenta de Anthropic (se reutiliza durante 30 min)."
    ),
)
if ANALYZER == sentiment.ClaudeAnalyzer.name and not os.environ.get("ANTHROPIC_API_KEY"):
    st.sidebar.warning("No encuentro ANTHROPIC_API_KEY. Si falla, se usará el diccionario.")
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
        items, _, agg, _, _ = news_sentiment(ticker, 15)
        if items:
            st.markdown(f"**Sentimiento de noticias:** {agg.label} ({agg.score:+.2f}) en {agg.total} titulares. Detalle en *Noticias y sentimiento*.")
    with right:
        st.subheader("Caídas desde máximos")
        dd = analysis.drawdown(close)
        f2 = go.Figure(go.Scatter(x=dd.index, y=dd, fill="tozeroy", line=dict(color=DOWN, width=1.5), name="Caída", hovertemplate="%{y:.1%}<extra></extra>"))
        f2.update_yaxes(tickformat=".0%")
        st.plotly_chart(style_chart(f2, 300), use_container_width=True)


def page_news() -> None:
    st.header("Noticias y sentimiento")
    st.caption("Titulares recientes clasificados como positivos, neutrales o negativos para el precio del activo.")
    mode = st.radio("Ver", ["Un activo", "Toda mi cartera"], horizontal=True)

    if mode == "Toda mi cartera":
        positions = portfolio.load_positions(PORTFOLIO_FILE)
        if positions.empty:
            st.info("No tienes una cartera guardada. Ve a *Mi cartera*, añade tus posiciones y pulsa Guardar.")
            return
        rows = []
        for t in positions["ticker"]:
            items, scored, agg, _, _ = news_sentiment(t, 15)
            rows.append({"Activo": label(t), "Sentimiento": agg.label, "Puntuación": agg.score, "Positivas": agg.positive, "Neutrales": agg.neutral, "Negativas": agg.negative, "Titular más reciente": items[0].title if items else "—"})
        table = pd.DataFrame(rows).sort_values("Puntuación")
        st.dataframe(
            table,
            hide_index=True,
            use_container_width=True,
            column_config={"Puntuación": st.column_config.ProgressColumn(min_value=-1, max_value=1, format="%+.2f")},
        )
        neg = table[table["Sentimiento"] == "Bajista"]
        if not neg.empty:
            st.warning("Noticias con tono negativo en: " + ", ".join(neg["Activo"]) + ". Revisa los titulares antes de decidir.")
        return

    ticker = ticker_picker("news")
    if not ticker:
        return
    items, scored, agg, summary, used = news_sentiment(ticker)
    if not items:
        st.info("No hay noticias recientes para este activo.")
    else:
        sentiment_header(agg)
        if summary:
            st.info(summary)
        st.caption(f"Analizado con: {used}.")
        render_items(items, scored)

    st.subheader("Comunidad de eToro")
    if not news.EToroClient.configured():
        st.caption(
            "Para ver qué opina la comunidad de eToro sobre este activo, crea tus claves en el portal de "
            "desarrolladores de eToro y define las variables de entorno ETORO_API_KEY y ETORO_USER_KEY antes de abrir la app. "
            "Función experimental."
        )
        return
    try:
        posts = load_etoro_posts(ticker)
    except news.EToroError as exc:
        st.warning(str(exc))
        return
    if not posts:
        st.info("No hay publicaciones recientes en eToro sobre este activo.")
        return
    p_scored, p_summary, p_used = analyze_texts(ANALYZER, tuple(p.text for p in posts), label(ticker) + " (opiniones de inversores)")
    sentiment_header(sentiment.aggregate(p_scored, [p.published for p in posts]), "publicaciones")
    if p_summary:
        st.info(p_summary)
    st.caption("Son opiniones de usuarios, no noticias: úsalas como termómetro del ánimo, no como señal de compra o venta.")
    render_items(posts, p_scored)


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


def local_time(iso: str | None) -> str:
    if not iso:
        return "—"
    from datetime import datetime

    return datetime.fromisoformat(iso).astimezone().strftime("%d/%m/%Y %H:%M")


STATUS_ICON = {"pendiente": "🕒", "ejecutada": "✅", "rechazada": "✖️", "caducada": "⌛", "fallida": "⚠️", "descartada": "🚫", "aprobada": "…"}


def page_bot() -> None:
    st.header("Bot de inversión")
    engine = Engine()
    cfg = engine.cfg
    store = engine.store
    st.caption(
        f"Modo: **{bot_config.MODES[cfg.modo]}** · Asesor: **{bot_config.ADVISORS[cfg.asesor]}** · "
        f"Aprobación: **{'tú apruebas cada operación' if cfg.requiere_aprobacion else 'automática'}**. "
        "La IA propone; unas reglas de riesgo fijas filtran cada propuesta antes de llegar aquí. "
        f"Datos del bot: **{'Yahoo Finance' if cfg.fuente_datos == 'yahoo' else 'simulados'}** (se cambia en Configuración, abajo)."
    )

    paused = store.paused
    c1, c2, c3 = st.columns([1.2, 1.2, 3])
    if paused:
        c1.error("⏸ Detenido")
        if c2.button("▶ Reanudar bot", type="primary"):
            store.set_paused(False)
            st.rerun()
    else:
        c1.success("● Activo")
        if c2.button("⏹ Detener bot (emergencia)"):
            store.set_paused(True, "Detenido desde la web.")
            st.rerun()
    with c3:
        cost_note = " Usa la IA de Claude: tiene un pequeño coste." if cfg.asesor == "claude" else ""
        if st.button("🔎 Analizar el mercado ahora", help="Normalmente lo hace el temporizador de la Raspberry." + cost_note):
            with st.spinner("Estudiando el mercado…"):
                result = engine.run_cycle()
            if result.get("ok"):
                st.success("Análisis completado." if not result.get("paused") else "El bot está detenido: solo se actualizó el valor de la cartera.")
            else:
                st.error(f"El análisis falló: {result.get('error')}")

    try:
        positions = engine.broker.positions()
        cash = engine.broker.cash()
    except BrokerError as exc:
        st.error(f"No se pudo conectar con el bróker: {exc}")
        positions, cash = {}, 0.0

    tickers = list(positions) + [cfg.referencia]
    try:
        prices, _ = engine.prices(tickers)
    except Exception:
        prices = {}
    equity = cash + sum(p.units * prices.get(t, p.avg_price) for t, p in positions.items())
    hist = pd.DataFrame(store.equity_history())

    k = st.columns(4)
    k[0].metric("Valor de la cartera", money(equity))
    k[1].metric("Efectivo", money(cash), help=f"{pct(cash / equity)} de la cartera" if equity else None)
    if cfg.modo == "simulacion":
        k[2].metric("Resultado", money(equity - cfg.capital_inicial), pct(equity / cfg.capital_inicial - 1, True))
    if len(hist) >= 2 and hist["benchmark"].notna().sum() >= 2:
        b = hist.dropna(subset=["benchmark"])
        bot_ret = equity / hist["equity"].iloc[0] - 1
        ref_ret = b["benchmark"].iloc[-1] / b["benchmark"].iloc[0] - 1
        k[3].metric(f"Frente a {cfg.referencia}", pct(bot_ret - ref_ret, True), help=f"Bot {pct(bot_ret, True)} · {cfg.referencia} {pct(ref_ret, True)} desde el primer registro")

    # ---------------------------------------------------------- propuestas pendientes
    pending = store.proposals("pendiente")
    st.subheader(f"Propuestas pendientes ({len(pending)})")
    if not pending:
        st.caption("No hay nada que aprobar ahora mismo.")
    for p in pending:
        with st.container(border=True):
            side = "🟢 Comprar" if p["side"] == "comprar" else "🔴 Vender"
            st.markdown(f"**{side} {label(p['ticker'])}** · {money(p['amount'])} a ~{money(p['price'])} · confianza {p['confidence']:.0%}")
            st.markdown(f"**Motivo:** {p['reason']}")
            if p["risks"]:
                st.markdown(f"**Riesgos:** {p['risks']}")
            if p["checks"]:
                st.caption("Control de riesgo: " + " ".join(p["checks"]))
            st.caption(f"Propuesta el {local_time(p['created'])}; caduca a las {cfg.caducidad_propuesta_horas:g} h.")
            a, r, _ = st.columns([1, 1, 4])
            if a.button("Aprobar", key=f"ok{p['id']}", type="primary"):
                with st.spinner("Comprobando precio y ejecutando…"):
                    ok, msg = engine.approve(p["id"])
                (st.success if ok else st.error)(msg)
                st.rerun() if ok else None
            if r.button("Rechazar", key=f"no{p['id']}"):
                engine.reject(p["id"])
                st.rerun()

    last = store.get("last_cycle")
    if last:
        st.subheader("Último análisis")
        st.caption(f"{local_time(last['ts'])} · {last['asesor']} · {last['propuestas']} propuesta(s)")
        st.info(last["resumen"])

    # ---------------------------------------------------------- cartera del bot
    left, right = st.columns(2)
    with left:
        st.subheader("Posiciones del bot")
        if positions:
            rows = [{"Activo": label(t), "Unidades": p.units, "Precio medio": p.avg_price, "Precio actual": prices.get(t), "Stop-loss": p.stop_price,
                     "Ganancia %": (prices.get(t, p.avg_price) / p.avg_price - 1)} for t, p in positions.items()]
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True, column_config={
                "Unidades": st.column_config.NumberColumn(format="%.6g"), "Precio medio": st.column_config.NumberColumn(format="%.2f"),
                "Precio actual": st.column_config.NumberColumn(format="%.2f"), "Stop-loss": st.column_config.NumberColumn(format="%.2f"),
                "Ganancia %": st.column_config.NumberColumn(format="percent")})
        else:
            st.caption("Sin posiciones abiertas.")
    with right:
        st.subheader(f"Evolución frente a {cfg.referencia}")
        if len(hist) >= 2:
            hist["ts"] = pd.to_datetime(hist["ts"])
            fig = go.Figure(go.Scatter(x=hist["ts"], y=100 * hist["equity"] / hist["equity"].iloc[0], name="Bot", line=dict(color=SERIES[0], width=2)))
            b = hist.dropna(subset=["benchmark"])
            if len(b) >= 2:
                fig.add_trace(go.Scatter(x=b["ts"], y=100 * b["benchmark"] / b["benchmark"].iloc[0], name=f"{cfg.referencia} (comprar y mantener)", line=dict(color=SERIES[1], width=2)))
            st.plotly_chart(style_chart(fig, 300), use_container_width=True)
        else:
            st.caption("Aparecerá cuando haya al menos dos análisis.")

    t1, t2, t3 = st.tabs(["Historial de propuestas", "Operaciones", "Registro"])
    with t1:
        props = store.proposals()
        if props:
            st.dataframe(pd.DataFrame([{"": STATUS_ICON.get(p["status"], ""), "Fecha": local_time(p["created"]), "Activo": p["ticker"], "Acción": p["side"],
                                        "Importe": p["amount"], "Confianza": p["confidence"], "Estado": p["status"],
                                        "Motivo / resultado": p["result"] or (" ".join(p["checks"]) if p["status"] == "descartada" else p["reason"])} for p in props]),
                         hide_index=True, use_container_width=True, column_config={"Importe": st.column_config.NumberColumn(format="%.2f"), "Confianza": st.column_config.NumberColumn(format="percent")})
        else:
            st.caption("Todavía no hay propuestas.")
    with t2:
        trades = store.trades()
        if trades:
            st.dataframe(pd.DataFrame([{"Fecha": local_time(t["ts"]), "Activo": t["ticker"], "Acción": t["side"], "Unidades": t["units"], "Precio": t["price"],
                                        "Importe": t["amount"], "Coste": t["fee"], "Origen": t["origin"]} for t in trades]), hide_index=True, use_container_width=True)
        else:
            st.caption("Todavía no hay operaciones.")
    with t3:
        for ev in store.events(50):
            icon = {"error": "🔴", "aviso": "🟠"}.get(ev["level"], "⚪")
            st.markdown(f"{icon} `{local_time(ev['ts'])}` {ev['message']}")

    # ---------------------------------------------------------- configuración
    with st.expander("⚙️ Configuración del bot"):
        with st.form("bot_cfg"):
            a, b, c = st.columns(3)
            modo = a.selectbox("Modo", list(bot_config.MODES), index=list(bot_config.MODES).index(cfg.modo), format_func=bot_config.MODES.get)
            asesor = b.selectbox("Asesor", list(bot_config.ADVISORS), index=list(bot_config.ADVISORS).index(cfg.asesor), format_func=bot_config.ADVISORS.get)
            fuente = c.selectbox("Datos de mercado", ["yahoo", "demo"], index=["yahoo", "demo"].index(cfg.fuente_datos), format_func={"yahoo": "Yahoo Finance (reales)", "demo": "Simulados"}.get)
            options = sorted(set(all_assets()) | set(cfg.lista_activos))
            lista = st.multiselect("Activos que el bot puede operar", options, default=cfg.lista_activos, format_func=label)
            a, b, c, d = st.columns(4)
            max_op = a.number_input("Máx. por operación (%)", 0.5, 50.0, float(cfg.max_operacion_pct), 0.5)
            max_pos = b.number_input("Máx. por activo (%)", 1.0, 100.0, float(cfg.max_posicion_pct), 1.0)
            min_liq = c.number_input("Liquidez mínima (%)", 0.0, 90.0, float(cfg.min_liquidez_pct), 1.0)
            stop = d.number_input("Stop-loss (%)", 1.0, 50.0, float(cfg.stop_loss_pct), 0.5)
            a, b, c, d = st.columns(4)
            p_dia = a.number_input("Pérdida máx. diaria (%)", 0.5, 50.0, float(cfg.max_perdida_diaria_pct), 0.5)
            p_sem = b.number_input("Pérdida máx. semanal (%)", 0.5, 50.0, float(cfg.max_perdida_semanal_pct), 0.5)
            ops = c.number_input("Operaciones máx. al día", 1, 50, int(cfg.max_operaciones_dia))
            conf = d.number_input("Confianza mínima", 0.0, 1.0, float(cfg.confianza_minima), 0.05)
            a, b = st.columns(2)
            capital = a.number_input("Capital inicial de la simulación", 100.0, 10_000_000.0, float(cfg.capital_inicial), 100.0)
            aprobacion = b.checkbox("Pedir mi aprobación para cada operación", value=cfg.requiere_aprobacion)
            sl_auto = b.checkbox("Vender automáticamente si salta el stop-loss", value=cfg.stop_loss_automatico)
            if st.form_submit_button("Guardar configuración", type="primary"):
                new = bot_config.BotConfig(**{**cfg.__dict__, "modo": modo, "asesor": asesor, "fuente_datos": fuente, "lista_activos": lista,
                    "max_operacion_pct": max_op, "max_posicion_pct": max_pos, "min_liquidez_pct": min_liq, "stop_loss_pct": stop,
                    "max_perdida_diaria_pct": p_dia, "max_perdida_semanal_pct": p_sem, "max_operaciones_dia": int(ops), "confianza_minima": conf,
                    "capital_inicial": capital, "requiere_aprobacion": aprobacion, "stop_loss_automatico": sl_auto})
                errors = engine.save_config(new)
                if errors:
                    st.error(" ".join(errors))
                else:
                    st.success("Configuración guardada.")
                    st.rerun()
        if not cfg.requiere_aprobacion:
            st.warning("El bot opera sin pedir aprobación. Revisa los límites de riesgo.")
        if cfg.modo == "simulacion":
            confirm = st.checkbox("Quiero borrar la simulación y empezar de cero")
            if st.button("Reiniciar simulación", disabled=not confirm):
                engine.reset_simulation()
                st.rerun()


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
6. *Noticias y sentimiento*: titulares recientes de un activo o de toda tu cartera, clasificados como positivos, neutrales o negativos.

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
- **Sentimiento**: tono de las noticias u opiniones sobre un activo, de −1 (muy negativo) a +1 (muy positivo). Es un dato complementario: las noticias suelen reflejarse en el precio muy rápido.
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
    "Noticias y sentimiento": page_news,
    "Comparar activos": page_compare,
    "Mi cartera": page_portfolio,
    "Simulador de aportaciones": page_simulator,
    "Bot de inversión": page_bot,
    "Guía rápida": page_guide,
}[page]()
