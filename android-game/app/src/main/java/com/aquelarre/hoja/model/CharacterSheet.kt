package com.aquelarre.hoja.model

/**
 * Categoría social del personaje.
 *
 * Elegida por el usuario tras investigar varias fuentes (no tenemos el
 * texto exacto del manual, ver conversación): son las 5 categorías
 * "económicas" que aparecieron citadas de forma repetida en foros y
 * resúmenes de aficionados a Aquelarre, con el dinero de partida (en
 * reales) que se menciona para cada una.
 *
 * NOTA PENDIENTE: no sabemos todavía si el Clero es una categoría social
 * aparte en el manual real, o si el clero se reparte entre estas 5 (p.ej.
 * un cura de pueblo como Baja Nobleza o Burguesía). Mientras no se aclare,
 * las profesiones religiosas (Clérigo, Monje...) se han repartido "a
 * ojo" en Profesion.kt.
 *
 * @param etiqueta texto legible para mostrar en la interfaz.
 * @param dineroBase reales de partida que indica (según nuestras fuentes)
 *   el manual para esta categoría social.
 * @param dineroEsAleatorio si es true, el dinero inicial real no es fijo:
 *   hay que tirar un porcentaje aleatorio de dineroBase (ver
 *   CreacionPersonaje.calcularDineroInicial). Así lo pidió el usuario para
 *   Alta Nobleza, Baja Nobleza y Burguesía. Si es false (Villanos y
 *   Campesinos), el dinero inicial es siempre dineroBase completo.
 */
enum class CategoriaSocial(
    val etiqueta: String,
    val dineroBase: Int,
    val dineroEsAleatorio: Boolean
) {
    ALTA_NOBLEZA("Alta Nobleza", 2500, true),
    BAJA_NOBLEZA("Baja Nobleza", 1300, true),
    BURGUESIA("Burguesía", 1500, true),
    VILLANOS("Villanos", 200, false),
    CAMPESINOS("Campesinos", 100, false)
}

enum class CategoriaHabilidad(val etiqueta: String) {
    NATURAL("Naturales"),
    SOCIAL("Sociales"),
    CULTURAL("Culturales"),
    ARTISTICA("Artísticas y de interior"),
    PROFESIONAL("Profesionales"),
    COMBATE("Combate")
}

/**
 * Las 8 características clásicas de Aquelarre. El rango habitual es 0-20,
 * generado con 3d6 y ajustado por categoría social y profesión.
 */
data class Atributos(
    val fuerza: Int = 10,
    val destreza: Int = 10,
    val agilidad: Int = 10,
    val constitucion: Int = 10,
    val comunicacion: Int = 10,
    val instruccion: Int = 10,
    val aspecto: Int = 10,
    val poder: Int = 10
)

data class Habilidad(
    val nombre: String,
    val categoria: CategoriaHabilidad,
    val valorBase: Int,
    val puntosInvertidos: Int = 0
) {
    val total: Int get() = valorBase + puntosInvertidos
}

data class Arma(
    val nombre: String,
    val dano: String,
    val bonificadorAtaque: Int = 0,
    val alcance: String = "Cuerpo a cuerpo"
)

/**
 * Estadísticas derivadas de los atributos base.
 *
 * Aquelarre no tiene una característica de "Cordura" al estilo La Llamada de
 * Cthulhu: la fuerza de voluntad frente al miedo se llama Templanza. Aun así,
 * las fórmulas exactas de Puntos de Vida y Templanza varían algo entre
 * ediciones del manual (1990, 2ª ed., 3ª ed. 2015, La Tentación 2023) y no
 * hemos podido verificarlas página a página, así que son una aproximación
 * razonada siguiendo la convención habitual de los sistemas BRP en los que
 * se basa Aquelarre: conviene contrastarlas con tu ejemplar del manual.
 */
data class EstadisticasDerivadas(
    val puntosDeVida: Int,
    val templanza: Int,
    val bonificadorCombate: Int,
    val bonificadorDano: String,
    val resistenciaAlDolor: Int,
    val capacidadDeCarga: Int
)

data class HojaDePersonaje(
    val nombre: String = "",
    // El reino de origen se elige libremente (no se tira a dados) y
    // condiciona el resto de la creación del personaje: ver Reino.kt y
    // CreacionPersonaje.kt para cómo se usa.
    val reino: Reino = Reino.CASTILLA,
    val categoriaSocial: CategoriaSocial = CategoriaSocial.CAMPESINOS,
    val profesion: String = "",
    val genero: String = "",
    val edad: Int = 20,
    val signoZodiacal: String = "",
    val estatura: String = "",
    val peso: String = "",
    val atributos: Atributos = Atributos(),
    val habilidades: List<Habilidad> = emptyList(),
    val armas: List<Arma> = emptyList(),
    val dinero: String = "",
    val posesiones: List<String> = emptyList(),
    val trasfondo: String = ""
) {
    fun calcularDerivadas(): EstadisticasDerivadas {
        val a = atributos
        return EstadisticasDerivadas(
            // Sin Talla/Tamaño en Aquelarre (personajes siempre humanos), la
            // vida sale de la robustez física: media de Fuerza y Constitución,
            // redondeada hacia arriba, como en el resto de la familia BRP.
            puntosDeVida = kotlin.math.ceil((a.fuerza + a.constitucion) / 2.0).toInt(),
            // Templanza = fuerza de voluntad ante el miedo y lo sobrenatural:
            // suma de Poder (fortaleza espiritual), Constitución (aguante) e
            // Instrucción (capacidad de razonar el horror), sin promediar.
            templanza = a.poder + a.constitucion + a.instruccion,
            bonificadorCombate = (a.fuerza + a.destreza - 20) / 2,
            bonificadorDano = danoPorFuerza(a.fuerza),
            resistenciaAlDolor = a.constitucion,
            capacidadDeCarga = a.fuerza * 4
        )
    }

    private fun danoPorFuerza(fuerza: Int): String = when {
        fuerza <= 5 -> "-1d6"
        fuerza <= 9 -> "-1d4"
        fuerza <= 12 -> "+0"
        fuerza <= 15 -> "+1d4"
        fuerza <= 18 -> "+1d6"
        else -> "+2d6"
    }
}
