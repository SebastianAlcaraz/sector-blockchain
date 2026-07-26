package com.aquelarre.hoja.model

/**
 * Reino de origen del personaje, dentro de la Península Ibérica de la
 * Baja Edad Media (siglos XIII-XIV), que es donde se ambienta Aquelarre.
 *
 * A diferencia de la categoría social y la profesión (que se tiran a
 * dados, ver CreacionPersonaje.kt), el REINO lo elige libremente el
 * jugador. La idea, tal y como la planteó el usuario, es que el reino
 * elegido condicione el resto de la creación del personaje (por ejemplo:
 * en el futuro, qué categorías sociales, profesiones o etnias/religiones
 * son compatibles con ese reino). De momento este campo solo se guarda en
 * la hoja de personaje; el filtrado real todavía no está implementado
 * (es el siguiente paso pendiente).
 *
 * Estos cinco reinos son los que aparecieron citados de forma consistente
 * en varias fuentes independientes al investigar el tema; no es una
 * transcripción literal del manual, pero coinciden con la geografía
 * histórica real de la época, así que la confianza en esta lista es alta.
 */
enum class Reino(val etiqueta: String) {
    CASTILLA("Corona de Castilla"),
    ARAGON("Corona de Aragón"),
    PORTUGAL("Reino de Portugal"),
    NAVARRA("Reino de Navarra"),
    GRANADA("Reino de Granada")
}
