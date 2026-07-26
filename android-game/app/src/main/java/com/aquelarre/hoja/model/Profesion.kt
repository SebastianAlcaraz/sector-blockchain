package com.aquelarre.hoja.model

/**
 * Una profesión disponible en Aquelarre.
 *
 * @param nombre nombre de la profesión, tal y como se muestra en la hoja
 *   de personaje.
 * @param categorias conjunto de categorías sociales desde las que se
 *   puede acceder a esta profesión. Una misma profesión puede estar
 *   disponible desde varias categorías sociales (por ejemplo, un Soldado
 *   puede salir tanto de la Baja Nobleza como de la Burguesía).
 */
data class Profesion(
    val nombre: String,
    val categorias: Set<CategoriaSocial>
)

/**
 * ⚠️ LISTA PROVISIONAL Y SIN VERIFICAR — leer antes de usar en partida.
 *
 * El manual de Aquelarre define 44 profesiones oficiales, pero no hemos
 * podido acceder al texto exacto del manual: las páginas de Scribd,
 * PDFCoffee, Wikipedia y varios blogs donde se citan quedaron bloqueadas
 * para las herramientas de este entorno al investigar el tema (ver
 * conversación). Todo lo que hay aquí es:
 *
 *  1. Un subconjunto de ~21 nombres de profesión que aparecieron citados
 *     de forma repetida en foros, blogs y resúmenes de aficionados al
 *     juego (probablemente reales, pero no confirmados al 100%).
 *  2. Una asignación de categoría social hecha "a ojo" por nosotros según
 *     lógica histórica (un Pastor es de Campesinos, un Cortesano es de
 *     Nobleza, etc.), NO copiada del manual.
 *
 * Faltan por tanto: unas 23 profesiones más hasta llegar a las 44 reales,
 * y hay que revisar si la categoría social asignada a cada una coincide
 * con el libro. Cuando el usuario consiga el texto exacto (foto o cita
 * del manual), esta es la única función que hay que actualizar: el resto
 * del código (CreacionPersonaje, la UI) ya está escrito para trabajar con
 * cualquier lista de Profesion que le pasemos, así que ampliar esta lista
 * no debería romper nada más.
 */
fun profesionesConocidas(): List<Profesion> = listOf(
    // --- Nobleza (alta y baja) ---
    Profesion("Cortesano", setOf(CategoriaSocial.ALTA_NOBLEZA, CategoriaSocial.BAJA_NOBLEZA)),
    Profesion("Guerrero", setOf(CategoriaSocial.ALTA_NOBLEZA, CategoriaSocial.BAJA_NOBLEZA)),

    // --- Clero: repartido "a ojo" entre Baja Nobleza y Burguesía hasta
    // que se aclare si el manual trata el Clero como categoría aparte ---
    Profesion("Clérigo", setOf(CategoriaSocial.BAJA_NOBLEZA, CategoriaSocial.BURGUESIA)),
    Profesion("Monje", setOf(CategoriaSocial.BAJA_NOBLEZA, CategoriaSocial.BURGUESIA, CategoriaSocial.VILLANOS)),

    // --- Burguesía (oficios urbanos "de dinero" o cualificados) ---
    Profesion("Comerciante", setOf(CategoriaSocial.BURGUESIA)),
    Profesion("Cambista", setOf(CategoriaSocial.BURGUESIA)),
    Profesion("Médico", setOf(CategoriaSocial.BURGUESIA)),
    Profesion("Alquimista", setOf(CategoriaSocial.BURGUESIA)),
    Profesion("Escriba", setOf(CategoriaSocial.BURGUESIA, CategoriaSocial.VILLANOS)),
    Profesion("Soldado", setOf(CategoriaSocial.BAJA_NOBLEZA, CategoriaSocial.BURGUESIA, CategoriaSocial.VILLANOS)),

    // --- Villanos (oficios urbanos comunes, gente libre de ciudad/villa) ---
    Profesion("Artesano", setOf(CategoriaSocial.VILLANOS)),
    Profesion("Marino", setOf(CategoriaSocial.VILLANOS)),
    Profesion("Pirata", setOf(CategoriaSocial.VILLANOS)),
    Profesion("Goliardo", setOf(CategoriaSocial.VILLANOS)),
    Profesion("Juglar", setOf(CategoriaSocial.VILLANOS, CategoriaSocial.CAMPESINOS)),
    Profesion("Cazador", setOf(CategoriaSocial.VILLANOS, CategoriaSocial.CAMPESINOS)),
    Profesion("Ladrón", setOf(CategoriaSocial.VILLANOS, CategoriaSocial.CAMPESINOS)),
    Profesion("Bandido", setOf(CategoriaSocial.VILLANOS, CategoriaSocial.CAMPESINOS)),

    // --- Campesinos (oficios rurales, la mayoría de la población) ---
    Profesion("Pastor", setOf(CategoriaSocial.CAMPESINOS)),
    Profesion("Siervo", setOf(CategoriaSocial.CAMPESINOS)),
    Profesion("Brujo", setOf(CategoriaSocial.CAMPESINOS, CategoriaSocial.VILLANOS))
)
