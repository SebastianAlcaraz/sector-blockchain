package com.aquelarre.hoja.model

/**
 * Categoría social del personaje. Determina el punto de partida de dinero,
 * profesiones disponibles y algunos modificadores de habilidades.
 */
enum class CategoriaSocial(val etiqueta: String) {
    CLERO("Clero"),
    NOBLEZA("Nobleza"),
    PUEBLO("Pueblo llano"),
    HAMPA_Y_MARGINADOS("Hampa y marginados"),
    JUDIOS_Y_MORISCOS("Judíos y moriscos"),
    EXTRANJEROS("Extranjeros")
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
    val categoriaSocial: CategoriaSocial = CategoriaSocial.PUEBLO,
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
