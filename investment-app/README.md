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
| **Noticias y sentimiento** | Titulares recientes de un activo o de toda tu cartera, clasificados como positivos, neutrales o negativos, con una puntuación global (las noticias recientes pesan más). Opcionalmente, opiniones de la comunidad de eToro. |
| **Simulador** | Compara con datos históricos aportar cada mes (DCA) frente a invertir todo de golpe. |
| **Bot de inversión** | Estudia el mercado cada pocas horas (con la IA de Claude o con reglas técnicas), propone compras y ventas, las filtra con límites de riesgo fijos y espera tu aprobación desde la web. Simulación local o cuenta demo de eToro. |
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

## Noticias y sentimiento

- **Noticias**: de Yahoo Finance (gratis, sin clave). En modo demo se usan titulares simulados.
- **Análisis de sentimiento**, a elegir en la barra lateral:
  - *Diccionario financiero* (por defecto): gratis y sin conexión, con palabras clave en español e inglés. Es aproximado.
  - *IA (Claude)*: entiende el contexto y redacta un resumen. Necesita una clave de la API de Anthropic
    y cada análisis tiene un pequeño coste (los resultados se reutilizan durante 30 minutos):
    ```bash
    export ANTHROPIC_API_KEY="tu-clave"      # En Windows: set ANTHROPIC_API_KEY=tu-clave
    ```
- **Comunidad de eToro** (experimental): si defines tus claves de la API de eToro, la sección muestra
  y analiza lo que publican los inversores sobre el activo.
  ```bash
  export ETORO_API_KEY="tu-clave-de-aplicacion"
  export ETORO_USER_KEY="tu-clave-de-usuario"
  ```
  Esta integración se ha escrito a partir de la documentación pública de eToro y todavía no se ha
  probado con una cuenta real; las rutas están en `invest/news.py` (clase `EToroClient`) por si hay que ajustarlas.

Nunca guardes las claves dentro del código ni las subas al repositorio.

## Bot de inversión

```
Temporizador (cada ~4 h) → estudio de mercado → la IA propone → control de riesgo → tú apruebas en la web → bróker
```

- **Estudio de mercado**: precios, medias móviles, RSI, MACD, volatilidad, caídas, noticias con su sentimiento y tu posición en cada activo.
- **Asesor**: *IA (Claude)* razona cada propuesta (motivo, riesgos y confianza); *Reglas técnicas* es la alternativa gratuita sin IA.
- **Control de riesgo** (reglas fijas que la IA no puede saltarse): solo activos de tu lista; máximo por operación (5 %) y por activo (20 %);
  liquidez mínima (10 %); stop-loss en cada compra (8 %); límites de pérdida diaria (3 %) y semanal (6 %, detiene el bot);
  máximo de operaciones al día; confianza mínima; sin apalancamiento. Todo se ajusta en la web.
- **Aprobación**: cada propuesta espera a que pulses *Aprobar* o *Rechazar*. Caduca a las 6 h, y si el precio se ha movido
  más de un 2 % desde la propuesta no se ejecuta.
- **Botón de parada de emergencia**: detiene análisis y compras. Los stop-loss siguen protegiendo las posiciones.
- **Modos**:
  - *Simulación local* (por defecto): precios reales, dinero ficticio, con coste por operación simulado.
  - *Cuenta demo de eToro* (experimental, sin probar con una cuenta real): necesita las claves de eToro. El código
    solo permite rutas de la cuenta demo; no hay ninguna opción para operar con dinero real.
- La web compara el resultado del bot con comprar y mantener el índice de referencia (SPY por defecto).
  Si tras semanas de simulación el bot no lo supera, no merece la pena seguir.

Ejecutar un ciclo a mano: `python -m invest.trading` (o `python -m invest.trading --estado`).

## Instalación en una Raspberry Pi

Requisitos: Raspberry Pi 4 (4 GB) o Pi 5 con **Raspberry Pi OS de 64 bits**; mejor con disco SSD que con tarjeta SD.

```bash
sudo timedatectl set-timezone Europe/Madrid      # tu zona horaria
git clone <este repositorio> && cd sector-blockchain/investment-app
bash deploy/raspberry/install.sh
nano ~/.config/asistente-inversion/env           # añade ANTHROPIC_API_KEY (y las de eToro si las tienes)
sudo systemctl restart asistente-web
```

El instalador:
- crea el entorno de Python;
- genera una contraseña para la web;
- deja la web funcionando en `http://<ip-de-la-raspberry>:8501`;
- programa el bot cada 4 horas en días laborables y una vez al día los fines de semana.

Seguridad:
- No abras el puerto 8501 en el router. Para entrar desde fuera de casa usa una VPN como [Tailscale](https://tailscale.com).
- Las claves viven solo en `~/.config/asistente-inversion/env`, con permisos 600.

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
invest/news.py       Noticias (Yahoo, demo) y cliente experimental de eToro
invest/sentiment.py  Sentimiento: diccionario financiero y análisis con Claude
invest/trading/      Bot: estudio de mercado, asesores, riesgo, brókers, motor y almacenamiento
deploy/raspberry/    Instalador y servicios systemd para la Raspberry Pi
tests/               Pruebas (pytest)
```

Pruebas: `python -m pytest tests`

## Versión web (sin instalación)

`web/index.html` es una versión de un solo archivo que se abre directamente en el navegador.
Usa **precios simulados** (no se conecta a Yahoo Finance) y guarda la cartera en el propio navegador.
Sirve para practicar y explorar las funciones; para datos reales usa la app de Streamlit.
