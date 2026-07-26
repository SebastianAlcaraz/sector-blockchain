package com.aquelarre.hoja.model

/**
 * Qué característica (de las 8 de Atributos) determina el valor base de
 * una competencia. Cada Competencia apunta a una de estas para saber de
 * dónde sacar su número de partida.
 */
enum class TipoAtributo {
    FUERZA,
    DESTREZA,
    AGILIDAD,
    CONSTITUCION,
    COMUNICACION,
    INSTRUCCION,
    ASPECTO,
    PODER;

    /** Lee el valor de este atributo concreto dentro de unos Atributos dados. */
    fun valorEn(atributos: Atributos): Int = when (this) {
        FUERZA -> atributos.fuerza
        DESTREZA -> atributos.destreza
        AGILIDAD -> atributos.agilidad
        CONSTITUCION -> atributos.constitucion
        COMUNICACION -> atributos.comunicacion
        INSTRUCCION -> atributos.instruccion
        ASPECTO -> atributos.aspecto
        PODER -> atributos.poder
    }
}

/**
 * Una competencia (habilidad) que pertenece a una profesión, junto con la
 * característica de la que depende su valor base.
 */
data class Competencia(
    val nombre: String,
    val atributo: TipoAtributo
)

/**
 * Una profesión disponible en Aquelarre.
 *
 * @param nombre nombre de la profesión, tal y como se muestra en la hoja
 *   de personaje.
 * @param categorias conjunto de categorías sociales desde las que se
 *   puede acceder a esta profesión. Una misma profesión puede estar
 *   disponible desde varias categorías sociales (por ejemplo, un Soldado
 *   puede salir tanto de la Baja Nobleza como de la Burguesía).
 * @param competenciasPrimarias las 4 competencias principales de la
 *   profesión. Su valor base es característica × 3.
 * @param competenciasSecundarias las 8 competencias secundarias de la
 *   profesión. Su valor base es característica × 1 (el valor tal cual).
 */
data class Profesion(
    val nombre: String,
    val categorias: Set<CategoriaSocial>,
    val competenciasPrimarias: List<Competencia>,
    val competenciasSecundarias: List<Competencia>
)

/**
 * ⚠️ LISTA PROVISIONAL Y SIN VERIFICAR — leer antes de usar en partida.
 *
 * El manual de Aquelarre define 44 profesiones oficiales, cada una con
 * sus propias 4 competencias primarias y 8 secundarias. No hemos podido
 * acceder al texto exacto del manual (ver conversación: las webs donde se
 * cita, incluida la 3ª edición en anyflip, quedaron bloqueadas por la
 * política de red de este entorno, comprobado con varias herramientas
 * distintas). Todo lo que hay aquí es:
 *
 *  1. Un subconjunto de ~21 nombres de profesión que aparecieron citados
 *     de forma repetida en foros, blogs y resúmenes de aficionados al
 *     juego (probablemente reales, pero no confirmados al 100%).
 *  2. Una asignación de categoría social hecha "a ojo" por nosotros según
 *     lógica histórica, NO copiada del manual.
 *  3. Un reparto de competencias primarias/secundarias INVENTADO por
 *     nosotros siguiendo el patrón real del manual (4 primarias base×3,
 *     8 secundarias base×1), pero con nombres y atributos elegidos por
 *     sentido común, no transcritos del libro.
 *
 * Faltan por tanto: unas 23 profesiones más hasta llegar a las 44 reales,
 * y hay que revisar si las competencias de cada una coinciden con el
 * libro real. En cuanto el usuario consiga fotos o texto del manual, hay
 * que sustituir esta función profesión a profesión; el resto del código
 * (CreacionPersonaje, la UI) ya está escrito para trabajar con cualquier
 * lista de Profesion que le pasemos, así que corregir esta lista no
 * debería romper nada más.
 */
fun profesionesConocidas(): List<Profesion> = listOf(
    Profesion(
        nombre = "Cortesano",
        categorias = setOf(CategoriaSocial.ALTA_NOBLEZA, CategoriaSocial.BAJA_NOBLEZA),
        competenciasPrimarias = listOf(
            Competencia("Etiqueta", TipoAtributo.COMUNICACION),
            Competencia("Oratoria", TipoAtributo.COMUNICACION),
            Competencia("Danzar", TipoAtributo.AGILIDAD),
            Competencia("Seducción", TipoAtributo.COMUNICACION)
        ),
        competenciasSecundarias = listOf(
            Competencia("Historia y leyendas", TipoAtributo.INSTRUCCION),
            Competencia("Montar", TipoAtributo.DESTREZA),
            Competencia("Cantar", TipoAtributo.COMUNICACION),
            Competencia("Camaradería", TipoAtributo.COMUNICACION),
            Competencia("Leer/Escribir", TipoAtributo.INSTRUCCION),
            Competencia("Idioma propio", TipoAtributo.INSTRUCCION),
            Competencia("Religión", TipoAtributo.INSTRUCCION),
            Competencia("Engañar", TipoAtributo.COMUNICACION)
        )
    ),
    Profesion(
        nombre = "Guerrero",
        categorias = setOf(CategoriaSocial.ALTA_NOBLEZA, CategoriaSocial.BAJA_NOBLEZA),
        competenciasPrimarias = listOf(
            Competencia("Arma cuerpo a cuerpo", TipoAtributo.DESTREZA),
            Competencia("Pelea (sin armas)", TipoAtributo.AGILIDAD),
            Competencia("Esquivar", TipoAtributo.AGILIDAD),
            Competencia("Montar", TipoAtributo.DESTREZA)
        ),
        competenciasSecundarias = listOf(
            Competencia("Correr", TipoAtributo.AGILIDAD),
            Competencia("Nadar", TipoAtributo.CONSTITUCION),
            Competencia("Resistir/Aguantar", TipoAtributo.CONSTITUCION),
            Competencia("Camaradería", TipoAtributo.COMUNICACION),
            Competencia("Arma a distancia", TipoAtributo.DESTREZA),
            Competencia("Trepar", TipoAtributo.AGILIDAD),
            Competencia("Rastrear", TipoAtributo.INSTRUCCION),
            Competencia("Notar/Buscar", TipoAtributo.INSTRUCCION)
        )
    ),
    Profesion(
        nombre = "Clérigo",
        categorias = setOf(CategoriaSocial.BAJA_NOBLEZA, CategoriaSocial.BURGUESIA),
        competenciasPrimarias = listOf(
            Competencia("Religión", TipoAtributo.INSTRUCCION),
            Competencia("Leer/Escribir", TipoAtributo.INSTRUCCION),
            Competencia("Idioma propio", TipoAtributo.INSTRUCCION),
            Competencia("Oratoria", TipoAtributo.COMUNICACION)
        ),
        competenciasSecundarias = listOf(
            Competencia("Historia y leyendas", TipoAtributo.INSTRUCCION),
            Competencia("Medicina", TipoAtributo.INSTRUCCION),
            Competencia("Camaradería", TipoAtributo.COMUNICACION),
            Competencia("Etiqueta", TipoAtributo.COMUNICACION),
            Competencia("Cantar", TipoAtributo.COMUNICACION),
            Competencia("Conocimiento Mágico", TipoAtributo.PODER),
            Competencia("Engañar", TipoAtributo.COMUNICACION),
            Competencia("Notar/Buscar", TipoAtributo.INSTRUCCION)
        )
    ),
    Profesion(
        nombre = "Monje",
        categorias = setOf(CategoriaSocial.BAJA_NOBLEZA, CategoriaSocial.BURGUESIA, CategoriaSocial.VILLANOS),
        competenciasPrimarias = listOf(
            Competencia("Religión", TipoAtributo.INSTRUCCION),
            Competencia("Leer/Escribir", TipoAtributo.INSTRUCCION),
            Competencia("Medicina", TipoAtributo.INSTRUCCION),
            Competencia("Idioma propio", TipoAtributo.INSTRUCCION)
        ),
        competenciasSecundarias = listOf(
            Competencia("Historia y leyendas", TipoAtributo.INSTRUCCION),
            Competencia("Cantar", TipoAtributo.COMUNICACION),
            Competencia("Camaradería", TipoAtributo.COMUNICACION),
            Competencia("Cocinar", TipoAtributo.COMUNICACION),
            Competencia("Artesanía", TipoAtributo.DESTREZA),
            Competencia("Rastrear", TipoAtributo.INSTRUCCION),
            Competencia("Resistir/Aguantar", TipoAtributo.CONSTITUCION),
            Competencia("Notar/Buscar", TipoAtributo.INSTRUCCION)
        )
    ),
    Profesion(
        nombre = "Comerciante",
        categorias = setOf(CategoriaSocial.BURGUESIA),
        competenciasPrimarias = listOf(
            Competencia("Comerciar", TipoAtributo.COMUNICACION),
            Competencia("Cálculo/Contabilidad", TipoAtributo.INSTRUCCION),
            Competencia("Oratoria", TipoAtributo.COMUNICACION),
            Competencia("Idioma extranjero", TipoAtributo.INSTRUCCION)
        ),
        competenciasSecundarias = listOf(
            Competencia("Camaradería", TipoAtributo.COMUNICACION),
            Competencia("Montar", TipoAtributo.DESTREZA),
            Competencia("Leer/Escribir", TipoAtributo.INSTRUCCION),
            Competencia("Etiqueta", TipoAtributo.COMUNICACION),
            Competencia("Engañar", TipoAtributo.COMUNICACION),
            Competencia("Notar/Buscar", TipoAtributo.INSTRUCCION),
            Competencia("Rastrear", TipoAtributo.INSTRUCCION),
            Competencia("Nadar", TipoAtributo.CONSTITUCION)
        )
    ),
    Profesion(
        nombre = "Cambista",
        categorias = setOf(CategoriaSocial.BURGUESIA),
        competenciasPrimarias = listOf(
            Competencia("Cálculo/Contabilidad", TipoAtributo.INSTRUCCION),
            Competencia("Comerciar", TipoAtributo.COMUNICACION),
            Competencia("Leer/Escribir", TipoAtributo.INSTRUCCION),
            Competencia("Engañar", TipoAtributo.COMUNICACION)
        ),
        competenciasSecundarias = listOf(
            Competencia("Idioma extranjero", TipoAtributo.INSTRUCCION),
            Competencia("Etiqueta", TipoAtributo.COMUNICACION),
            Competencia("Camaradería", TipoAtributo.COMUNICACION),
            Competencia("Notar/Buscar", TipoAtributo.INSTRUCCION),
            Competencia("Oratoria", TipoAtributo.COMUNICACION),
            Competencia("Religión", TipoAtributo.INSTRUCCION),
            Competencia("Historia y leyendas", TipoAtributo.INSTRUCCION),
            Competencia("Sigilo", TipoAtributo.DESTREZA)
        )
    ),
    Profesion(
        nombre = "Médico",
        categorias = setOf(CategoriaSocial.BURGUESIA),
        competenciasPrimarias = listOf(
            Competencia("Medicina", TipoAtributo.INSTRUCCION),
            Competencia("Leer/Escribir", TipoAtributo.INSTRUCCION),
            Competencia("Herbolaria", TipoAtributo.INSTRUCCION),
            Competencia("Notar/Buscar", TipoAtributo.INSTRUCCION)
        ),
        competenciasSecundarias = listOf(
            Competencia("Religión", TipoAtributo.INSTRUCCION),
            Competencia("Camaradería", TipoAtributo.COMUNICACION),
            Competencia("Etiqueta", TipoAtributo.COMUNICACION),
            Competencia("Comerciar", TipoAtributo.COMUNICACION),
            Competencia("Idioma extranjero", TipoAtributo.INSTRUCCION),
            Competencia("Alquimia", TipoAtributo.INSTRUCCION),
            Competencia("Oratoria", TipoAtributo.COMUNICACION),
            Competencia("Resistir/Aguantar", TipoAtributo.CONSTITUCION)
        )
    ),
    Profesion(
        nombre = "Alquimista",
        categorias = setOf(CategoriaSocial.BURGUESIA),
        competenciasPrimarias = listOf(
            Competencia("Alquimia", TipoAtributo.INSTRUCCION),
            Competencia("Leer/Escribir", TipoAtributo.INSTRUCCION),
            Competencia("Conocimiento Mágico", TipoAtributo.PODER),
            Competencia("Cálculo/Contabilidad", TipoAtributo.INSTRUCCION)
        ),
        competenciasSecundarias = listOf(
            Competencia("Herbolaria", TipoAtributo.INSTRUCCION),
            Competencia("Medicina", TipoAtributo.INSTRUCCION),
            Competencia("Religión", TipoAtributo.INSTRUCCION),
            Competencia("Idioma extranjero", TipoAtributo.INSTRUCCION),
            Competencia("Notar/Buscar", TipoAtributo.INSTRUCCION),
            Competencia("Artesanía", TipoAtributo.DESTREZA),
            Competencia("Comerciar", TipoAtributo.COMUNICACION),
            Competencia("Sigilo", TipoAtributo.DESTREZA)
        )
    ),
    Profesion(
        nombre = "Escriba",
        categorias = setOf(CategoriaSocial.BURGUESIA, CategoriaSocial.VILLANOS),
        competenciasPrimarias = listOf(
            Competencia("Leer/Escribir", TipoAtributo.INSTRUCCION),
            Competencia("Idioma propio", TipoAtributo.INSTRUCCION),
            Competencia("Cálculo/Contabilidad", TipoAtributo.INSTRUCCION),
            Competencia("Copiar/Calcar", TipoAtributo.DESTREZA)
        ),
        competenciasSecundarias = listOf(
            Competencia("Historia y leyendas", TipoAtributo.INSTRUCCION),
            Competencia("Religión", TipoAtributo.INSTRUCCION),
            Competencia("Etiqueta", TipoAtributo.COMUNICACION),
            Competencia("Comerciar", TipoAtributo.COMUNICACION),
            Competencia("Camaradería", TipoAtributo.COMUNICACION),
            Competencia("Notar/Buscar", TipoAtributo.INSTRUCCION),
            Competencia("Oratoria", TipoAtributo.COMUNICACION),
            Competencia("Idioma extranjero", TipoAtributo.INSTRUCCION)
        )
    ),
    Profesion(
        nombre = "Soldado",
        categorias = setOf(CategoriaSocial.BAJA_NOBLEZA, CategoriaSocial.BURGUESIA, CategoriaSocial.VILLANOS),
        competenciasPrimarias = listOf(
            Competencia("Arma cuerpo a cuerpo", TipoAtributo.DESTREZA),
            Competencia("Arma a distancia", TipoAtributo.DESTREZA),
            Competencia("Esquivar", TipoAtributo.AGILIDAD),
            Competencia("Resistir/Aguantar", TipoAtributo.CONSTITUCION)
        ),
        competenciasSecundarias = listOf(
            Competencia("Correr", TipoAtributo.AGILIDAD),
            Competencia("Pelea (sin armas)", TipoAtributo.AGILIDAD),
            Competencia("Camaradería", TipoAtributo.COMUNICACION),
            Competencia("Montar", TipoAtributo.DESTREZA),
            Competencia("Nadar", TipoAtributo.CONSTITUCION),
            Competencia("Trepar", TipoAtributo.AGILIDAD),
            Competencia("Notar/Buscar", TipoAtributo.INSTRUCCION),
            Competencia("Rastrear", TipoAtributo.INSTRUCCION)
        )
    ),
    Profesion(
        nombre = "Artesano",
        categorias = setOf(CategoriaSocial.VILLANOS),
        competenciasPrimarias = listOf(
            Competencia("Artesanía", TipoAtributo.DESTREZA),
            Competencia("Copiar/Calcar", TipoAtributo.DESTREZA),
            Competencia("Cálculo/Contabilidad", TipoAtributo.INSTRUCCION),
            Competencia("Comerciar", TipoAtributo.COMUNICACION)
        ),
        competenciasSecundarias = listOf(
            Competencia("Camaradería", TipoAtributo.COMUNICACION),
            Competencia("Etiqueta", TipoAtributo.COMUNICACION),
            Competencia("Leer/Escribir", TipoAtributo.INSTRUCCION),
            Competencia("Notar/Buscar", TipoAtributo.INSTRUCCION),
            Competencia("Sigilo", TipoAtributo.DESTREZA),
            Competencia("Resistir/Aguantar", TipoAtributo.CONSTITUCION),
            Competencia("Rastrear", TipoAtributo.INSTRUCCION),
            Competencia("Nadar", TipoAtributo.CONSTITUCION)
        )
    ),
    Profesion(
        nombre = "Marino",
        categorias = setOf(CategoriaSocial.VILLANOS),
        competenciasPrimarias = listOf(
            Competencia("Nadar", TipoAtributo.CONSTITUCION),
            Competencia("Orientación", TipoAtributo.INSTRUCCION),
            Competencia("Trepar", TipoAtributo.AGILIDAD),
            Competencia("Resistir/Aguantar", TipoAtributo.CONSTITUCION)
        ),
        competenciasSecundarias = listOf(
            Competencia("Correr", TipoAtributo.AGILIDAD),
            Competencia("Pelea (sin armas)", TipoAtributo.AGILIDAD),
            Competencia("Arma cuerpo a cuerpo", TipoAtributo.DESTREZA),
            Competencia("Camaradería", TipoAtributo.COMUNICACION),
            Competencia("Notar/Buscar", TipoAtributo.INSTRUCCION),
            Competencia("Rastrear", TipoAtributo.INSTRUCCION),
            Competencia("Idioma extranjero", TipoAtributo.INSTRUCCION),
            Competencia("Comerciar", TipoAtributo.COMUNICACION)
        )
    ),
    Profesion(
        nombre = "Pirata",
        categorias = setOf(CategoriaSocial.VILLANOS),
        competenciasPrimarias = listOf(
            Competencia("Arma cuerpo a cuerpo", TipoAtributo.DESTREZA),
            Competencia("Nadar", TipoAtributo.CONSTITUCION),
            Competencia("Trepar", TipoAtributo.AGILIDAD),
            Competencia("Intimidar", TipoAtributo.COMUNICACION)
        ),
        competenciasSecundarias = listOf(
            Competencia("Sigilo", TipoAtributo.DESTREZA),
            Competencia("Correr", TipoAtributo.AGILIDAD),
            Competencia("Pelea (sin armas)", TipoAtributo.AGILIDAD),
            Competencia("Resistir/Aguantar", TipoAtributo.CONSTITUCION),
            Competencia("Notar/Buscar", TipoAtributo.INSTRUCCION),
            Competencia("Rastrear", TipoAtributo.INSTRUCCION),
            Competencia("Engañar", TipoAtributo.COMUNICACION),
            Competencia("Comerciar", TipoAtributo.COMUNICACION)
        )
    ),
    Profesion(
        nombre = "Goliardo",
        categorias = setOf(CategoriaSocial.VILLANOS),
        competenciasPrimarias = listOf(
            Competencia("Cantar", TipoAtributo.COMUNICACION),
            Competencia("Tocar instrumento", TipoAtributo.DESTREZA),
            Competencia("Oratoria", TipoAtributo.COMUNICACION),
            Competencia("Danzar", TipoAtributo.AGILIDAD)
        ),
        competenciasSecundarias = listOf(
            Competencia("Historia y leyendas", TipoAtributo.INSTRUCCION),
            Competencia("Leer/Escribir", TipoAtributo.INSTRUCCION),
            Competencia("Camaradería", TipoAtributo.COMUNICACION),
            Competencia("Idioma propio", TipoAtributo.INSTRUCCION),
            Competencia("Seducción", TipoAtributo.COMUNICACION),
            Competencia("Engañar", TipoAtributo.COMUNICACION),
            Competencia("Notar/Buscar", TipoAtributo.INSTRUCCION),
            Competencia("Sigilo", TipoAtributo.DESTREZA)
        )
    ),
    Profesion(
        nombre = "Juglar",
        categorias = setOf(CategoriaSocial.VILLANOS, CategoriaSocial.CAMPESINOS),
        competenciasPrimarias = listOf(
            Competencia("Cantar", TipoAtributo.COMUNICACION),
            Competencia("Danzar", TipoAtributo.AGILIDAD),
            Competencia("Tocar instrumento", TipoAtributo.DESTREZA),
            Competencia("Oratoria", TipoAtributo.COMUNICACION)
        ),
        competenciasSecundarias = listOf(
            Competencia("Camaradería", TipoAtributo.COMUNICACION),
            Competencia("Seducción", TipoAtributo.COMUNICACION),
            Competencia("Historia y leyendas", TipoAtributo.INSTRUCCION),
            Competencia("Engañar", TipoAtributo.COMUNICACION),
            Competencia("Notar/Buscar", TipoAtributo.INSTRUCCION),
            Competencia("Sigilo", TipoAtributo.DESTREZA),
            Competencia("Correr", TipoAtributo.AGILIDAD),
            Competencia("Idioma extranjero", TipoAtributo.INSTRUCCION)
        )
    ),
    Profesion(
        nombre = "Cazador",
        categorias = setOf(CategoriaSocial.VILLANOS, CategoriaSocial.CAMPESINOS),
        competenciasPrimarias = listOf(
            Competencia("Arma a distancia", TipoAtributo.DESTREZA),
            Competencia("Rastrear", TipoAtributo.INSTRUCCION),
            Competencia("Sigilo", TipoAtributo.DESTREZA),
            Competencia("Notar/Buscar", TipoAtributo.INSTRUCCION)
        ),
        competenciasSecundarias = listOf(
            Competencia("Correr", TipoAtributo.AGILIDAD),
            Competencia("Trepar", TipoAtributo.AGILIDAD),
            Competencia("Nadar", TipoAtributo.CONSTITUCION),
            Competencia("Resistir/Aguantar", TipoAtributo.CONSTITUCION),
            Competencia("Pelea (sin armas)", TipoAtributo.AGILIDAD),
            Competencia("Camaradería", TipoAtributo.COMUNICACION),
            Competencia("Cocinar", TipoAtributo.COMUNICACION),
            Competencia("Montar", TipoAtributo.DESTREZA)
        )
    ),
    Profesion(
        nombre = "Ladrón",
        categorias = setOf(CategoriaSocial.VILLANOS, CategoriaSocial.CAMPESINOS),
        competenciasPrimarias = listOf(
            Competencia("Sigilo", TipoAtributo.DESTREZA),
            Competencia("Trepar", TipoAtributo.AGILIDAD),
            Competencia("Robar", TipoAtributo.DESTREZA),
            Competencia("Notar/Buscar", TipoAtributo.INSTRUCCION)
        ),
        competenciasSecundarias = listOf(
            Competencia("Correr", TipoAtributo.AGILIDAD),
            Competencia("Esquivar", TipoAtributo.AGILIDAD),
            Competencia("Engañar", TipoAtributo.COMUNICACION),
            Competencia("Camaradería", TipoAtributo.COMUNICACION),
            Competencia("Arma cuerpo a cuerpo", TipoAtributo.DESTREZA),
            Competencia("Rastrear", TipoAtributo.INSTRUCCION),
            Competencia("Nadar", TipoAtributo.CONSTITUCION),
            Competencia("Idioma extranjero", TipoAtributo.INSTRUCCION)
        )
    ),
    Profesion(
        nombre = "Bandido",
        categorias = setOf(CategoriaSocial.VILLANOS, CategoriaSocial.CAMPESINOS),
        competenciasPrimarias = listOf(
            Competencia("Arma cuerpo a cuerpo", TipoAtributo.DESTREZA),
            Competencia("Sigilo", TipoAtributo.DESTREZA),
            Competencia("Rastrear", TipoAtributo.INSTRUCCION),
            Competencia("Intimidar", TipoAtributo.COMUNICACION)
        ),
        competenciasSecundarias = listOf(
            Competencia("Correr", TipoAtributo.AGILIDAD),
            Competencia("Esquivar", TipoAtributo.AGILIDAD),
            Competencia("Trepar", TipoAtributo.AGILIDAD),
            Competencia("Resistir/Aguantar", TipoAtributo.CONSTITUCION),
            Competencia("Nadar", TipoAtributo.CONSTITUCION),
            Competencia("Notar/Buscar", TipoAtributo.INSTRUCCION),
            Competencia("Montar", TipoAtributo.DESTREZA),
            Competencia("Camaradería", TipoAtributo.COMUNICACION)
        )
    ),
    Profesion(
        nombre = "Pastor",
        categorias = setOf(CategoriaSocial.CAMPESINOS),
        competenciasPrimarias = listOf(
            Competencia("Rastrear", TipoAtributo.INSTRUCCION),
            Competencia("Resistir/Aguantar", TipoAtributo.CONSTITUCION),
            Competencia("Notar/Buscar", TipoAtributo.INSTRUCCION),
            Competencia("Cocinar", TipoAtributo.COMUNICACION)
        ),
        competenciasSecundarias = listOf(
            Competencia("Correr", TipoAtributo.AGILIDAD),
            Competencia("Trepar", TipoAtributo.AGILIDAD),
            Competencia("Nadar", TipoAtributo.CONSTITUCION),
            Competencia("Pelea (sin armas)", TipoAtributo.AGILIDAD),
            Competencia("Camaradería", TipoAtributo.COMUNICACION),
            Competencia("Religión", TipoAtributo.INSTRUCCION),
            Competencia("Arma a distancia", TipoAtributo.DESTREZA),
            Competencia("Artesanía", TipoAtributo.DESTREZA)
        )
    ),
    Profesion(
        nombre = "Siervo",
        categorias = setOf(CategoriaSocial.CAMPESINOS),
        competenciasPrimarias = listOf(
            Competencia("Resistir/Aguantar", TipoAtributo.CONSTITUCION),
            Competencia("Artesanía", TipoAtributo.DESTREZA),
            Competencia("Cocinar", TipoAtributo.COMUNICACION),
            Competencia("Camaradería", TipoAtributo.COMUNICACION)
        ),
        competenciasSecundarias = listOf(
            Competencia("Correr", TipoAtributo.AGILIDAD),
            Competencia("Nadar", TipoAtributo.CONSTITUCION),
            Competencia("Trepar", TipoAtributo.AGILIDAD),
            Competencia("Notar/Buscar", TipoAtributo.INSTRUCCION),
            Competencia("Rastrear", TipoAtributo.INSTRUCCION),
            Competencia("Religión", TipoAtributo.INSTRUCCION),
            Competencia("Comerciar", TipoAtributo.COMUNICACION),
            Competencia("Sigilo", TipoAtributo.DESTREZA)
        )
    ),
    Profesion(
        nombre = "Brujo",
        categorias = setOf(CategoriaSocial.CAMPESINOS, CategoriaSocial.VILLANOS),
        competenciasPrimarias = listOf(
            Competencia("Conocimiento Mágico", TipoAtributo.PODER),
            Competencia("Herbolaria", TipoAtributo.INSTRUCCION),
            Competencia("Percibir lo Irracional", TipoAtributo.PODER),
            Competencia("Sigilo", TipoAtributo.DESTREZA)
        ),
        competenciasSecundarias = listOf(
            Competencia("Rastrear", TipoAtributo.INSTRUCCION),
            Competencia("Notar/Buscar", TipoAtributo.INSTRUCCION),
            Competencia("Camaradería", TipoAtributo.COMUNICACION),
            Competencia("Engañar", TipoAtributo.COMUNICACION),
            Competencia("Resistir/Aguantar", TipoAtributo.CONSTITUCION),
            Competencia("Correr", TipoAtributo.AGILIDAD),
            Competencia("Trepar", TipoAtributo.AGILIDAD),
            Competencia("Nadar", TipoAtributo.CONSTITUCION)
        )
    )
)
