# Aquelarre RPG — Hoja de Personaje (prototipo)

Proyecto Android nativo (Kotlin + Jetpack Compose) para un juego de rol
inspirado en la ambientación y mecánicas de *Aquelarre*. Es un proyecto
personal/fan, no afiliado a la editorial ni al autor original: no copia
texto ni arte del manual, solo se inspira en su estructura de juego
(características, habilidades, categorías sociales, etc.).

## Qué hay ahora mismo

Un único ejercicio funcional: **la hoja de personaje**.

- `model/CharacterSheet.kt`: modelo de datos (`HojaDePersonaje`,
  `Atributos`, `Habilidad`, `Arma`, `EstadisticasDerivadas`) y las fórmulas
  para calcular puntos de vida, Templanza (fuerza de voluntad ante el miedo;
  Aquelarre no usa "Cordura", eso es de La Llamada de Cthulhu), bonificador
  de combate, etc.
- `model/DefaultSkills.kt`: listado de habilidades de partida, agrupadas
  por categoría (Naturales, Sociales, Culturales, Artísticas, Profesionales,
  Combate).
- `ui/CharacterSheetScreen.kt`: pantalla Compose editable con creación por
  dados, identidad, características, estadísticas derivadas (se recalculan
  solas), lista de habilidades con puntos asignables, y trasfondo del
  personaje.
- `MainActivity.kt`: aloja la pantalla anterior con estado en memoria (aún
  no se persiste entre sesiones).
- `model/Reino.kt`: los 5 reinos de la Península Ibérica (Castilla, Aragón,
  Portugal, Navarra, Granada). Se elige libremente, no se tira a dados.
- `model/Profesion.kt`: modelo de profesión y una lista **provisional y sin
  verificar** de ~21 profesiones (el manual real tiene 44 — no hemos podido
  conseguir la lista completa, ver advertencia en el propio archivo).
- `model/CreacionPersonaje.kt`: motor de creación de personaje "a dados"
  (categoría social, profesión, dinero inicial, bono extraordinario de
  1/100). Todas las funciones están comentadas a fondo y aceptan un
  parámetro `dado` sustituible para poder depurarlas con valores fijos.

⚠️ Las fórmulas de Puntos de Vida y Templanza, la tabla de probabilidades de
categoría social, y la lista de profesiones son aproximaciones razonadas
(no transcripciones literales del manual): no hemos podido verificar el
texto exacto de tu edición del libro porque las páginas donde se citan
quedaron bloqueadas para las herramientas de este entorno. Si tienes el
manual a mano, compáralas y dime los valores exactos para ajustarlas.

## Descargar el APK sin instalar nada (desde el móvil)

Cada push a `android-game/**` dispara un workflow de GitHub Actions
(`.github/workflows/android-game-build.yml`) que compila un APK de
depuración en la nube:

⚠️ Si ya tenías instalada una versión del APK anterior a este cambio y
Android te da un error de "conflicto con un paquete" al instalar la
nueva: desinstala la app una vez (los datos de esa versión se perderán,
todavía no hay persistencia) y vuelve a instalar el nuevo APK. La causa
era que cada build de CI firmaba el APK con una clave de depuración
distinta y aleatoria; ahora el proyecto incluye un `debug.keystore` fijo
(`app/debug.keystore`) para que todas las versiones futuras se firmen
igual y las actualizaciones se instalen sin conflicto.

1. En GitHub, entra a la pestaña **Actions** del repo (funciona desde el
   navegador del móvil).
2. Abre la ejecución más reciente de "Android Game - Build APK".
3. Descarga el artefacto `aquelarre-rpg-debug-apk` (es un .zip con el
   `.apk` dentro).
4. Extrae el .zip en el móvil y toca el `.apk` para instalarlo (Android
   pedirá permiso para "instalar apps de origen desconocido" la primera
   vez — es normal en un APK de depuración sin firmar por Play Store).

## Cómo abrirlo en Android Studio (opcional, para desarrollar)

1. Instala [Android Studio](https://developer.android.com/studio) (última
   versión estable) en un PC/Mac.
2. `Abrir proyecto` → selecciona la carpeta `android-game/`.
3. El Gradle Wrapper (`gradlew`, `gradle/wrapper/`) ya está incluido en el
   repo, así que no hace falta generarlo.
4. Ejecuta en un emulador o en tu móvil con la depuración USB activada.

Este entorno remoto tampoco puede compilar el APK localmente (no tiene
Android SDK ni acceso a los servidores de Google para descargarlo), por
eso la compilación se delega a GitHub Actions.

## Próximos pasos posibles

- Completar `profesionesConocidas()` con las 44 profesiones reales del
  manual (bloqueante: falta conseguir el texto exacto).
- Decidir si el Clero es una categoría social aparte o se reparte entre las
  5 actuales.
- Que el Reino de origen filtre de verdad categorías/profesiones/etnias
  compatibles (de momento solo se guarda, no filtra nada).
- Aplicar el bono extraordinario de creación directamente a las
  competencias primarias de la profesión elegida (hace falta primero saber
  qué 4 competencias son primarias en cada profesión).
- Persistencia (Room o DataStore) para guardar personajes.
- Tirada de características (en vez de solo edición manual).
- Inventario y equipo con peso/capacidad de carga.
- Pantalla de combate.
