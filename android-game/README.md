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
- `ui/CharacterSheetScreen.kt`: pantalla Compose editable con identidad,
  características, estadísticas derivadas (se recalculan solas), lista de
  habilidades con puntos asignables, y trasfondo del personaje.
- `MainActivity.kt`: aloja la pantalla anterior con estado en memoria (aún
  no se persiste entre sesiones).

⚠️ Las fórmulas de Puntos de Vida y Templanza son una aproximación razonada
(siguiendo la convención habitual de los sistemas BRP en los que se basa
Aquelarre), no una transcripción literal del manual: no hemos podido
verificar el texto exacto de tu edición del libro. Si tienes el manual a
mano, compáralas y dime los valores exactos para ajustarlas.

## Descargar el APK sin instalar nada (desde el móvil)

Cada push a `android-game/**` dispara un workflow de GitHub Actions
(`.github/workflows/android-game-build.yml`) que compila un APK de
depuración en la nube:

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

- Persistencia (Room o DataStore) para guardar personajes.
- Pantalla de creación de personaje paso a paso (tirada de características,
  elección de categoría social y profesión).
- Sistema de tiradas de dados y resolución de habilidades.
- Inventario y equipo con peso/capacidad de carga.
- Pantalla de combate.
