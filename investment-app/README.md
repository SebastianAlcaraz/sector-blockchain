# Asistente de inversión

Aplicación web (Python + Streamlit) para analizar y seguir inversiones en **acciones, ETF,
materias primas, criptomonedas, índices y divisas**, con datos gratuitos de Yahoo Finance.

> ⚠️ Herramienta educativa y de análisis. **No es asesoramiento financiero.**

## Funciones

| Sección | Qué hace |
|---|---|
| **Panorama de mercado** | Precio, variación diaria/mensual/anual, volatilidad y una lectura técnica (-100 a +100) de decenas de activos. Ranking de mejores y peores. |
| **Análisis de un activo** | Gráfico con medias móviles 50/200, Bollinger, RSI y MACD; rentabilidad anual, volatilidad, Sharpe y máxima caída; lectura técnica explicada en lenguaje claro. |
| **Comparar activos** | Evolución en base 100, tabla de rentabilidad/riesgo y matriz de correlación para diversificar. |
| **Mi cartera** | Registra tus posiciones, ve ganancias/pérdidas, distribución por clase de activo, alertas de concentración y cuánto comprar/vender para rebalancear. |
| **Simulador** | Compara con datos históricos aportar cada mes (DCA) frente a invertir todo de golpe. |
| **Guía rápida** | Cómo escribir los símbolos y glosario de términos. |

Hay un **modo demo** con precios simulados para probar la app sin conexión.

## Instalación y uso

Requiere Python 3.10 o superior.

```bash
cd investment-app
python -m venv .venv
source .venv/bin/activate        # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Se abrirá en el navegador en <http://localhost:8501>.

Tu cartera se guarda localmente en `data/cartera.json` (excluido de git).

## Símbolos

Se usan los de Yahoo Finance: `AAPL` (acción), `SAN.MC` (Bolsa de Madrid), `GGAL.BA` (Buenos Aires),
`GC=F` (oro), `CL=F` (petróleo), `BTC-USD` (bitcoin), `^GSPC` (S&P 500), `EURUSD=X` (euro/dólar).

## Estructura

```
app.py               Interfaz Streamlit
invest/catalog.py    Catálogo de activos por clase
invest/data.py       Descarga de precios (Yahoo) y fuente demo
invest/indicators.py SMA, EMA, RSI, MACD, Bollinger
invest/analysis.py   Métricas de riesgo/rentabilidad y lectura técnica
invest/portfolio.py  Valoración, distribución y rebalanceo
invest/simulator.py  Simulación DCA / inversión única
tests/               Pruebas (pytest)
```

Pruebas: `python -m pytest tests`
