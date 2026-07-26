package com.aquelarre.hoja.model

/**
 * Listado de partida de habilidades. Los valores base son orientativos para
 * el prototipo; en el manual varían según la característica asociada a cada
 * habilidad. Se puede ajustar libremente desde aquí sin tocar la UI.
 */
fun habilidadesPorDefecto(): List<Habilidad> = listOf(
    // Naturales
    Habilidad("Correr", CategoriaHabilidad.NATURAL, 15),
    Habilidad("Esquivar", CategoriaHabilidad.NATURAL, 10),
    Habilidad("Nadar", CategoriaHabilidad.NATURAL, 10),
    Habilidad("Notar/Buscar", CategoriaHabilidad.NATURAL, 10),
    Habilidad("Trepar", CategoriaHabilidad.NATURAL, 10),
    Habilidad("Ocultarse", CategoriaHabilidad.NATURAL, 5),
    Habilidad("Sigilo", CategoriaHabilidad.NATURAL, 5),

    // Sociales
    Habilidad("Camaradería", CategoriaHabilidad.SOCIAL, 5),
    Habilidad("Engañar", CategoriaHabilidad.SOCIAL, 5),
    Habilidad("Etiqueta", CategoriaHabilidad.SOCIAL, 5),
    Habilidad("Oratoria", CategoriaHabilidad.SOCIAL, 5),
    Habilidad("Seducción", CategoriaHabilidad.SOCIAL, 5),

    // Culturales
    Habilidad("Leer/Escribir", CategoriaHabilidad.CULTURAL, 0),
    Habilidad("Idioma propio", CategoriaHabilidad.CULTURAL, 25),
    Habilidad("Historia y leyendas", CategoriaHabilidad.CULTURAL, 5),
    Habilidad("Religión", CategoriaHabilidad.CULTURAL, 5),
    Habilidad("Medicina", CategoriaHabilidad.CULTURAL, 0),

    // Artísticas y de interior
    Habilidad("Cantar", CategoriaHabilidad.ARTISTICA, 5),
    Habilidad("Danzar", CategoriaHabilidad.ARTISTICA, 5),
    Habilidad("Cocinar", CategoriaHabilidad.ARTISTICA, 5),
    Habilidad("Tocar instrumento", CategoriaHabilidad.ARTISTICA, 0),

    // Nota: la categoría "Profesionales" (Artesanía, Comerciar, Montar,
    // Rastrear...) ya no vive aquí. Ahora esas habilidades salen de la
    // profesión del personaje, con un valor base propio según sus
    // características y un presupuesto de 100 puntos aparte: ver
    // Profesion.kt (competenciasPrimarias/competenciasSecundarias) y la
    // sección "Competencias de la profesión" en la pantalla.

    // Combate
    Habilidad("Arma cuerpo a cuerpo", CategoriaHabilidad.COMBATE, 15),
    Habilidad("Arma a distancia", CategoriaHabilidad.COMBATE, 5),
    Habilidad("Pelea (sin armas)", CategoriaHabilidad.COMBATE, 15)
)
