# Asistente de inversión: resumen del proyecto

*Estado a 3 de noviembre de 2026.*

> Herramienta personal de análisis e inversión con un bot que opera **solo con dinero virtual**.
> No es asesoramiento financiero.

- **Código:** repositorio `sebastianalcaraz/sector-blockchain`, rama `claude/investment-app-sl48gt`, carpeta `investment-app/`.
- **Versión web para probar sin instalar:** <https://claude.ai/artifact/TEAi2rxcrWbskK5SWcEV4L> (precios simulados).

---

## 1. Qué es

Una aplicación web en Python (Streamlit) que se instala en un equipo pequeño encendido todo el día, como un mini PC o una Raspberry Pi. Tiene dos partes:

1. **Herramientas de consulta** para ti: mercado, análisis de activos, noticias, comparación, cartera y simulador.
2. **Un bot de inversión** que estudia el mercado cada pocas horas, decide y **opera solo en la cuenta demo de eToro**. Aprende de sus resultados y propone mejoras de su estrategia cada semana.

## 2. Cómo se llegó hasta aquí

| # | Petición | Resultado |
|---|---|---|
| 1 | Una app para invertir en acciones, materias primas, etc. | App web con 6 secciones y datos de Yahoo Finance; modo demo con precios simulados |
| 2 | Verla aquí | Versión web de un solo archivo (enlace arriba), con precios simulados |
| 3 | ¿Se puede usar eToro? ¿Qué datos da? | Análisis de la API pública de eToro: precios, cartera, órdenes, noticias, comunidad, copy trading |
| 4 | Noticias y sentimiento | Sección nueva: titulares clasificados como positivos, neutrales o negativos, con diccionario financiero o con Claude |
| 5 | Instalarlo en una Raspberry que opere con Claude | Bot con control de riesgo fijo, simulación, aprobación en la web e instalación automática |
| 6 | Que aprenda y corrija su estrategia | Diario de decisiones, revisión semanal y validación con datos no usados para ajustarla |
| 7 | Usar la suscripción de Claude en lugar de la API | Dos conexiones intercambiables: suscripción (Claude Code) o API, con respaldo automático |
| 8 | ¿Mini PC o Raspberry? | Recomendado un mini PC Intel N150, 16 GB y SSD; instalador y guía paso a paso |
| 9 | Varias fuentes de noticias, precios de eToro, que el bot decida solo, siempre en demo | Noticias de Yahoo, Google News (es/en) y eToro; precios de eToro con Yahoo de respaldo; bot autónomo en demo |

## 3. Secciones de la web

| Sección | Para qué sirve |
|---|---|
| Panorama de mercado | Precio, variaciones, volatilidad y lectura técnica (−100 a +100) de decenas de activos |
| Análisis de un activo | Gráfico con medias de 50 y 200 sesiones, Bollinger, RSI y MACD; rentabilidad, volatilidad, Sharpe y máxima caída; explicación de las señales |
| Noticias y sentimiento | Titulares de varias fuentes sin duplicados, con su tono; resumen por IA; opinión de la comunidad de eToro |
| Comparar activos | Evolución desde una base 100, tabla de rentabilidad y riesgo, y correlaciones |
| Mi cartera | Tus posiciones reales, ganancias, reparto por clase, avisos de concentración y rebalanceo |
| Simulador | Aportar cada mes frente a invertir todo al inicio, con datos históricos |
| Bot de inversión | Estado, cartera del bot, operaciones, registro, estrategia y aprendizaje, configuración |
| Guía rápida | Símbolos y glosario |

La web pide una **contraseña**, que genera el instalador.

## 4. De dónde salen los datos

| Qué | Fuentes | Si falla |
|---|---|---|
| Precios | **eToro**: velas diarias y precio en directo | Se completan con **Yahoo Finance** |
| Noticias | **Yahoo Finance**, **Google News** en español e inglés, **eToro** | Las demás fuentes siguen funcionando |
| Opinión de inversores | Comunidad de **eToro** | Se omite |

**Todas las señales se calculan en tu equipo** a partir de esos datos, con fórmulas conocidas:

- **Medias de 50 y 200 sesiones:** la tendencia.
- **RSI de 14 días:** sobrecompra por encima de 70, sobreventa por debajo de 30.
- **MACD (12/26/9):** el impulso.
- **Rendimiento:** a 1 semana, 1 mes, 3 meses y 1 año.
- **Volatilidad anual y caída desde máximos:** el riesgo.
- **Sentimiento de noticias:** de −1 a +1. Las noticias recientes pesan más.

Ninguna señal se compra ni se copia de un servicio externo.

## 5. El bot

### Un ciclo

Cada 4 horas en días laborables, y una vez al día el fin de semana:

1. **Estudio técnico** de todo el catálogo: unas 36 acciones, ETF, materias primas y criptomonedas.
2. **Preselección** de los 12 mejores candidatos según la estrategia, más lo que ya tiene en cartera.
3. **Estudio a fondo** de los preseleccionados: noticias de varias fuentes, comunidad de eToro y análisis de **Claude**, con motivo, riesgos y confianza.
4. **Control de riesgo** con reglas fijas que la IA no puede saltarse.
5. **Ejecución automática** en la cuenta demo, sin pedir aprobación. Se puede activar la aprobación manual.

### Límites de riesgo (configurables en la web)

| Regla | Valor por defecto |
|---|---|
| Máximo por operación | 5 % de la cartera |
| Máximo por activo | 20 % |
| Liquidez mínima | 10 % en efectivo |
| Stop-loss en cada compra | 8 % |
| Pérdida diaria máxima | 3 % (deja de comprar ese día) |
| Pérdida semanal máxima | 6 % (el bot se detiene) |
| Operaciones al día | 4 |
| Confianza mínima de la IA | 0,6 |
| Apalancamiento | No permitido |

Hay además un **botón de parada de emergencia**.

### Solo dinero virtual

- Opera en la **cuenta demo de eToro**. Sin claves de eToro, usa la **simulación local** (10.000 € ficticios).
- **No existe ningún modo de dinero real en el programa.** Una prueba automática lo comprueba: todas las direcciones de compra y venta son de la cuenta demo.
- Pasar a dinero real requiere **una orden expresa** y un cambio de código.

### Aprendizaje (cada domingo)

1. Evalúa cada decisión pasada a 14 días. Una compra acierta si el activo batió al S&P 500; una venta acierta si el activo lo hizo peor.
2. Claude (o un optimizador sin IA) propone una **estrategia candidata**: pesos de las señales, umbrales, manual y lecciones.
3. La candidata se prueba con **el 30 % más reciente del histórico**, que no se usó para ajustarla. Solo se recomienda si no empeora, no aumenta la peor caída y hace suficientes operaciones. También avisa si parece sobreajustada.
4. Tú decides si se adopta, y puedes volver a cualquier versión anterior.

La estrategia **no puede tocar los límites de riesgo**.

## 6. Conexión con Claude

| | Suscripción (Claude Code) | API de Anthropic |
|---|---|---|
| Necesitas | Plan Pro, Max o Ultra + Claude Code instalado | Clave `ANTHROPIC_API_KEY` con saldo |
| Coste | Sin coste extra; gasta los límites de tu plan | Pago por uso |
| Si se agota | El ciclo usa las reglas de la estrategia | Igual |

- Elegida: **suscripción Pro**, con la API como alternativa. Se cambia en la web.
- Al usar la suscripción, el bot quita la clave de API del entorno para que nunca se cobre por API por error.
- Probado con una llamada real a Claude Code: la respuesta llegó en el formato esperado.
- Normas: Anthropic indica que los límites de los planes suponen un "uso normal e individual". Es uso personal con el programa oficial, pero la API es la vía sin ninguna duda.
- Con el plan Pro, el modelo **Sonnet** gasta menos límite que **Opus**.

## 7. Equipo recomendado

**Mini PC** con Intel N100/N150, **16 GB de RAM** y SSD de 256–512 GB, con **Ubuntu Server 24.04 LTS**.

| Modelo | Notas |
|---|---|
| GMKtec NucBox G3 Plus (N150) | Buena relación calidad-precio; una reseña lo sitúa en ~179–239 € en España (agosto de 2026) |
| Beelink Mini S13 (N150, 16/500 GB) | Tienda oficial en AliExpress con 96 % de valoraciones positivas |
| Beelink EQ14 (N150) | Más completo; 199–399 € según la fuente |

Compra en la **tienda oficial** de la marca, elige la opción de **16 GB**, prefiere envío desde la UE y que tenga **red por cable**.

Alternativa: **Raspberry Pi 5 de 8 GB** con SSD NVMe, fuente oficial y ventilador.

## 8. Instalación (resumen)

Guía completa: `investment-app/deploy/linux/GUIA-MINIPC.md`.

```bash
sudo timedatectl set-timezone Europe/Madrid
git clone -b claude/investment-app-sl48gt https://github.com/sebastianalcaraz/sector-blockchain.git
cd sector-blockchain/investment-app
bash deploy/linux/install.sh                    # genera la contraseña de la web; ofrece instalar Claude Code
~/.local/bin/claude setup-token                 # token de tu suscripción (dura 1 año)
nano ~/.config/asistente-inversion/env          # CLAUDE_CODE_OAUTH_TOKEN, ETORO_API_KEY, ETORO_USER_KEY
sudo systemctl restart asistente-web
```

Después abre `http://IP-del-equipo:8501`, ve a **Bot de inversión → Configuración** y pulsa **Probar la conexión con Claude**.

Para acceder desde fuera de casa, usa **Tailscale**. No abras puertos en el router.

## 9. Qué está probado y qué no

**Probado:**
- 63 pruebas automáticas: indicadores, cartera, riesgo, motor del bot, aprendizaje, conexión con Claude, fuentes de noticias y precios, bot autónomo y ausencia de modo real.
- Todas las secciones de la web en el navegador, en modo demo.
- Un ciclo autónomo completo: el bot eligió activos del catálogo y los compró con su stop-loss.
- Una llamada real a Claude Code con la suscripción.

**Sin probar:**
- **eToro con una cuenta real:** precios, noticias, comunidad y órdenes en la cuenta demo. Está hecho según su documentación pública; el formato de las órdenes y de la cartera demo está sin confirmar.
- **Yahoo Finance y Google News reales:** el entorno de desarrollo los bloquea. En el mini PC funcionarán con normalidad.
- **El instalador en un equipo real:** solo está revisada su sintaxis.

## 10. Próximos pasos

1. Comprar el mini PC e instalarlo con la guía.
2. Crear las claves de la API de eToro (cuenta verificada) y el token de Claude.
3. Pulsar **Analizar el mercado ahora** y revisar el **Registro**. Si eToro da errores, enviar el mensaje (sin las claves) para ajustarlo.
4. Dejarlo **varias semanas** en la cuenta demo y comparar con el S&P 500 en la gráfica del bot.
5. Solo si lo supera de forma consistente, valorar dinero real con una cantidad pequeña, previa orden expresa.

## 11. Estructura del código

```
investment-app/
├── app.py                 Interfaz web (Streamlit)
├── invest/
│   ├── catalog.py         Catálogo de activos
│   ├── data.py            Precios: eToro, Yahoo, demo y respaldo
│   ├── indicators.py      SMA, EMA, RSI, MACD, Bollinger
│   ├── analysis.py        Métricas y lectura técnica
│   ├── news.py            Noticias (Yahoo, Google News, eToro) y cliente de eToro
│   ├── sentiment.py       Sentimiento: diccionario y Claude
│   ├── llm.py             Conexión con Claude: API o suscripción
│   ├── portfolio.py       Cartera y rebalanceo
│   ├── simulator.py       Simulador de aportaciones
│   └── trading/           Bot: estrategia, backtest, aprendizaje, riesgo, brókers, motor
├── deploy/linux/          Instalador, guía del mini PC y servicios del sistema
├── web/index.html         Versión web de un solo archivo
├── docs/                  Este resumen
└── tests/                 63 pruebas automáticas
```
