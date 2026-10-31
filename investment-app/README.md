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

### Aprendizaje: la estrategia se crea y se corrige

La estrategia tiene dos partes:
- **Parámetros numéricos**: cuánto pesa cada señal (tendencia, impulso, RSI, rendimiento a 3 meses y noticias), los umbrales de compra
  y venta, el tamaño de cada compra y los días mínimos en cartera. Se pueden probar con datos históricos.
- **Manual en texto**: los principios que la IA sigue al analizar, más las lecciones aprendidas.

Cada domingo (o con el botón *Revisar la estrategia ahora*):
1. **Evalúa** cada decisión pasada, también las de mantener, las rechazadas y las descartadas, a 14 días. Una compra acierta
   si el activo batió al índice de referencia; una venta acierta si el activo lo hizo peor que el índice.
2. **Diagnostica** qué tipos de decisión y qué niveles de puntuación funcionaron.
3. **Propone** una estrategia candidata:
   - con *IA (Claude)*: Claude revisa los datos y cambia parámetros, manual y lecciones;
   - sin IA: un optimizador prueba variaciones de los parámetros.
4. **Valida** la candidata con datos históricos que no se usaron para ajustarla (el 30 % más reciente). Se recomienda
   solo si rinde igual o mejor que la actual, no aumenta la peor caída y hace suficientes operaciones. También avisa si
   parece sobreajustada.
5. **Tú decides** si se adopta. Puedes volver a cualquier versión anterior.

Los parámetros tienen rangos máximos, y los límites de riesgo no forman parte de la estrategia: el aprendizaje no puede tocarlos.
Las pruebas históricas solo usan señales técnicas, porque no hay noticias históricas disponibles.

Ejecutar a mano:
- un ciclo: `python -m invest.trading`;
- el estado: `python -m invest.trading --estado`;
- la revisión de la estrategia: `python -m invest.trading --revisar`.

### Conexión con Claude: suscripción o API

El bot puede usar Claude por dos vías. Se elige en *Bot de inversión → Configuración → Conexión con Claude*, y el botón
*Probar la conexión con Claude* comprueba que funciona.

| | Suscripción (Claude Code) | API de Anthropic |
|---|---|---|
| Qué necesitas | Plan Pro, Max o Ultra + Claude Code instalado | Clave `ANTHROPIC_API_KEY` con saldo |
| Coste | Sin coste extra: gasta los límites de tu plan (compartidos con tu uso de Claude) | Pago por uso |
| Si se agota | Ese ciclo usa las reglas de la estrategia (respaldo) | Igual, si se queda sin saldo |

Configurar la suscripción en el equipo del bot:
```bash
curl -fsSL https://claude.ai/install.sh | bash     # instala Claude Code (o acepta en el instalador)
~/.local/bin/claude setup-token                     # abre el inicio de sesión y muestra un token (dura un año)
nano ~/.config/asistente-inversion/env              # pégalo en CLAUDE_CODE_OAUTH_TOKEN=
sudo systemctl restart asistente-web
```

Detalles:
- El bot llama al programa oficial `claude` sin herramientas, solo para analizar el texto que le envía.
- Le quita la `ANTHROPIC_API_KEY` al llamarlo, para que nunca cobre por API cuando eliges la suscripción.
  Puedes tener las dos configuradas y cambiar desde la web.
- Con el plan Pro los límites son más ajustados: el modelo *Sonnet* gasta menos que *Opus*.
- Renueva el token antes de que caduque, al año.
- Anthropic indica que los límites de los planes suponen un "uso normal e individual" de Claude Code. Es un uso personal,
  pero si quieres total seguridad sobre las condiciones, usa la API.

## Instalación en un mini PC o una Raspberry Pi

Equipos recomendados:
- **Mini PC** (recomendado): Intel N100/N150, 16 GB de RAM, SSD, con **Ubuntu Server 24.04 LTS** o Debian 12+.
  Guía paso a paso desde cero: [`deploy/linux/GUIA-MINIPC.md`](deploy/linux/GUIA-MINIPC.md).
- **Raspberry Pi 5** de 8 GB (o Pi 4 de 4 GB como mínimo) con **Raspberry Pi OS de 64 bits** y disco SSD (mejor que tarjeta SD).

```bash
sudo timedatectl set-timezone Europe/Madrid      # tu zona horaria
git clone -b claude/investment-app-sl48gt https://github.com/sebastianalcaraz/sector-blockchain.git
cd sector-blockchain/investment-app
bash deploy/linux/install.sh
nano ~/.config/asistente-inversion/env           # añade CLAUDE_CODE_OAUTH_TOKEN o ANTHROPIC_API_KEY (y las de eToro si las tienes)
sudo systemctl restart asistente-web
```

El instalador:
- crea el entorno de Python;
- genera una contraseña para la web;
- deja la web funcionando en `http://<ip-del-equipo>:8501`;
- programa el bot cada 4 horas en días laborables y una vez al día los fines de semana;
- programa la revisión de la estrategia cada domingo.

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
invest/llm.py        Conexión con Claude: API o suscripción (Claude Code), intercambiables
invest/trading/      Bot: estudio de mercado, asesores, riesgo, brókers, motor y almacenamiento
deploy/linux/        Instalador, guía del mini PC y servicios systemd (mini PC o Raspberry Pi)
tests/               Pruebas (pytest)
```

Pruebas: `python -m pytest tests`

## Versión web (sin instalación)

`web/index.html` es una versión de un solo archivo que se abre directamente en el navegador.
Usa **precios simulados** (no se conecta a Yahoo Finance) y guarda la cartera en el propio navegador.
Sirve para practicar y explorar las funciones; para datos reales usa la app de Streamlit.
