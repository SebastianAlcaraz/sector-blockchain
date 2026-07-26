package com.aquelarre.hoja.model

import kotlin.random.Random

/**
 * Resultado de una tirada completa de creación de personaje: qué
 * categoría social y profesión han salido, cuánto dinero inicial le
 * corresponde y si ha tenido suerte con el bono extraordinario.
 *
 * Este objeto NO modifica todavía la hoja de personaje: es solo el
 * resultado de "tirar los dados". Aplicarlo (o no) a un HojaDePersonaje
 * concreto es una decisión de la pantalla que use este motor (así el
 * jugador puede volver a tirar antes de confirmar).
 */
data class ResultadoCreacion(
    val reino: Reino,
    val categoriaSocial: CategoriaSocial,
    val profesion: Profesion,
    val dineroInicial: Int,
    val puntosBonoPrimarias: Int
)

/**
 * Motor de creación de personaje de Aquelarre.
 *
 * Reglas implementadas aquí, tal y como se acordaron en la conversación
 * con el usuario (algunas son reglas de la mesa, no del manual — se
 * marca claramente cuál es cuál en cada función):
 *
 *  1. El REINO se elige libremente por el jugador (no hay función de
 *     tirada para él: se recibe como parámetro en generar()).
 *  2. La CATEGORÍA SOCIAL se tira a los dados.
 *  3. La PROFESIÓN se tira a los dados, solo entre las profesiones que
 *     acepten la categoría social obtenida en el paso 2.
 *  4. El DINERO INICIAL depende de la categoría social (ver
 *     CategoriaSocial.dineroBase / dineroEsAleatorio).
 *  5. Hay una probabilidad de 1 entre 100 de obtener un BONO
 *     EXTRAORDINARIO de hasta 3 puntos para las competencias/habilidades
 *     principales del personaje (regla de mesa pedida por el usuario, no
 *     es una regla oficial del manual).
 *
 * Diseño para poder depurar fácilmente: cada función de "tirada" recibe
 * un parámetro `dado` con un valor por defecto que usa números aleatorios
 * de verdad (kotlin.random.Random). Si quieres probar un caso concreto
 * (por ejemplo, forzar que salga Alta Nobleza, o forzar que el bono
 * extraordinario se active), puedes llamar a la función pasando tu propia
 * lambda `dado` que devuelva el número que quieras, sin tocar el resto
 * del código. Ejemplo:
 *
 *   // Fuerza la tirada de categoría social a que sea siempre "50"
 *   // (cae en Villanos con la tabla actual):
 *   CreacionPersonaje.tirarCategoriaSocial(dado = { 50 })
 */
object CreacionPersonaje {

    /**
     * Tira la categoría social del personaje.
     *
     * Se tira un número entero al azar entre 1 y 100 (ambos incluidos,
     * como una tirada de 1d100) y se mira en qué tramo cae.
     *
     * ⚠️ ADVERTENCIA IMPORTANTE: los tramos de abajo (1-1, 2-5, 6-20,
     * 21-60, 61-100) son un reparto INVENTADO por nosotros, no una tabla
     * copiada del manual (no hemos podido conseguir esa tabla real, ver
     * conversación). Está pensado para que la mayoría de personajes salgan
     * Campesinos o Villanos (como en la realidad histórica) y que la Alta
     * Nobleza sea rarísima. Si consigues la tabla real del libro, este es
     * el único sitio del código que hay que cambiar para corregirlo.
     *
     * @param dado función que "tira el dado": por defecto genera un
     *   entero aleatorio real entre 1 y 100. Se puede sustituir por una
     *   lambda fija para hacer pruebas/depuración (ver comentario de la
     *   clase).
     */
    fun tirarCategoriaSocial(dado: () -> Int = { Random.nextInt(1, 101) }): CategoriaSocial {
        val tirada = dado() // Debería venir un número entre 1 y 100.

        // El orden de las comparaciones importa: en cuanto la tirada es
        // menor o igual que el límite del tramo, esa es la categoría y no
        // se siguen comprobando los demás tramos.
        return when {
            tirada <= 1 -> CategoriaSocial.ALTA_NOBLEZA   // 1 caso de 100 (1%)
            tirada <= 5 -> CategoriaSocial.BAJA_NOBLEZA   // siguientes 4 casos (4%)
            tirada <= 20 -> CategoriaSocial.BURGUESIA     // siguientes 15 casos (15%)
            tirada <= 60 -> CategoriaSocial.VILLANOS      // siguientes 40 casos (40%)
            else -> CategoriaSocial.CAMPESINOS            // los 40 casos restantes (40%)
        }
    }

    /**
     * Tira la profesión del personaje, solo entre las que acepten la
     * categoría social que ya ha salido.
     *
     * Primero filtra la lista de profesiones disponibles (por defecto,
     * profesionesConocidas() — la lista provisional de Profesion.kt) para
     * quedarse solo con las que incluyen la categoriaSocial recibida.
     * Después tira un número al azar para elegir una de esas profesiones
     * candidatas.
     *
     * @param categoriaSocial la categoría social ya decidida (normalmente
     *   el resultado de tirarCategoriaSocial()).
     * @param profesionesDisponibles la lista completa de profesiones
     *   entre las que elegir. Se puede sustituir por otra lista (por
     *   ejemplo, una vez tengamos las 44 profesiones reales) sin tocar
     *   esta función.
     * @param dado función que "tira el dado" para elegir el índice dentro
     *   de la lista de candidatas. Por defecto genera un entero aleatorio
     *   real; se puede fijar para depuración.
     *
     * @throws IllegalArgumentException si no hay ninguna profesión
     *   disponible para esa categoría social (con la lista provisional
     *   actual esto no debería pasar nunca, porque cada categoría tiene
     *   al menos una profesión asignada; si pasara, es una señal de que
     *   falta añadir profesiones para esa categoría).
     */
    fun tirarProfesion(
        categoriaSocial: CategoriaSocial,
        profesionesDisponibles: List<Profesion> = profesionesConocidas(),
        dado: () -> Int = { Random.nextInt(0, Int.MAX_VALUE) }
    ): Profesion {
        // Nos quedamos solo con las profesiones cuyo conjunto de
        // categorías sociales contiene la categoría social del personaje.
        val candidatas = profesionesDisponibles.filter { categoriaSocial in it.categorias }

        require(candidatas.isNotEmpty()) {
            "No hay ninguna profesión cargada para la categoría social $categoriaSocial. " +
                "Revisa profesionesConocidas() en Profesion.kt y añade alguna profesión " +
                "que incluya esa categoría social."
        }

        // El operador % (módulo) convierte cualquier número aleatorio en
        // un índice válido dentro de la lista de candidatas, sea cual sea
        // el tamaño de esa lista.
        val indice = dado() % candidatas.size
        return candidatas[indice]
    }

    /**
     * Calcula el dinero inicial (en reales) para una categoría social.
     *
     * Regla pedida por el usuario:
     *  - Alta Nobleza, Baja Nobleza y Burguesía (dineroEsAleatorio = true
     *    en CategoriaSocial): el dinero inicial es un porcentaje aleatorio
     *    entre el 50% y el 100% (ambos incluidos) del dinero base de la
     *    categoría.
     *  - Villanos y Campesinos (dineroEsAleatorio = false): el dinero
     *    inicial es siempre el 100% del dinero base, sin aleatoriedad.
     *
     * @param dado función que "tira el dado" del porcentaje: por defecto
     *   genera un entero aleatorio real entre 50 y 100. Solo se usa
     *   cuando dineroEsAleatorio es true; si es false, ni se llama.
     */
    fun calcularDineroInicial(
        categoriaSocial: CategoriaSocial,
        dado: () -> Int = { Random.nextInt(50, 101) }
    ): Int {
        if (!categoriaSocial.dineroEsAleatorio) {
            // Villanos y Campesinos: dinero fijo, no hace falta tirar nada.
            return categoriaSocial.dineroBase
        }

        val porcentaje = dado() // Número entero entre 50 y 100.

        // Ejemplo con números concretos para que se entienda la fórmula:
        // si dineroBase = 2500 (Alta Nobleza) y el porcentaje tirado es 73,
        // el resultado es 2500 * 73 / 100 = 1825 reales.
        return categoriaSocial.dineroBase * porcentaje / 100
    }

    /**
     * Comprueba si se activa el bono extraordinario de creación de
     * personaje: una posibilidad de 1 entre 100 de conseguir puntos extra
     * para las habilidades/competencias principales.
     *
     * Esta es una regla de mesa que pidió el usuario, NO es una regla
     * oficial del manual de Aquelarre.
     *
     * Cómo funciona:
     *  1. Se tira un número entero al azar entre 1 y 100 (1d100).
     *  2. El bono se activa únicamente si ese número es exactamente 1
     *     (es decir, 1 posibilidad entre 100, un 1%).
     *  3. Si se activa, la cantidad de puntos de bono es "hasta 3 puntos"
     *     según pidió el usuario: lo interpretamos como un segundo dado,
     *     esta vez de 1 a 3 (1d3), para decidir si son 1, 2 o 3 puntos.
     *  4. Si no se activa, el resultado es 0 puntos.
     *
     * @param dadoActivacion dado que decide si se activa el bono (1-100
     *   por defecto). Se puede fijar a { 1 } para forzar que se active
     *   siempre durante las pruebas.
     * @param dadoCantidad dado que decide cuántos puntos da el bono si se
     *   activa (1-3 por defecto). Solo se usa si el bono se activa.
     * @return 0 si no se ha activado el bono; un número entre 1 y 3 si sí
     *   se ha activado.
     */
    fun comprobarBonoExtraordinario(
        dadoActivacion: () -> Int = { Random.nextInt(1, 101) },
        dadoCantidad: () -> Int = { Random.nextInt(1, 4) }
    ): Int {
        val tiradaActivacion = dadoActivacion() // Número entre 1 y 100.
        val seActiva = tiradaActivacion == 1    // Solo se activa con un 1 exacto: 1/100.

        return if (seActiva) dadoCantidad() else 0
    }

    /**
     * Ejecuta de golpe toda la fase "a dados" de la creación de
     * personaje: categoría social, profesión, dinero inicial y bono
     * extraordinario. El reino no se tira, se recibe ya elegido por el
     * jugador.
     *
     * Esta función es la que debería llamar la pantalla de creación de
     * personaje; las funciones sueltas de más arriba (tirarCategoriaSocial,
     * tirarProfesion, etc.) están pensadas para poder probarlas o
     * depurarlas una por una si algo no sale como se espera.
     */
    fun generar(reino: Reino): ResultadoCreacion {
        val categoriaSocial = tirarCategoriaSocial()
        val profesion = tirarProfesion(categoriaSocial)
        val dineroInicial = calcularDineroInicial(categoriaSocial)
        val puntosBonoPrimarias = comprobarBonoExtraordinario()

        return ResultadoCreacion(
            reino = reino,
            categoriaSocial = categoriaSocial,
            profesion = profesion,
            dineroInicial = dineroInicial,
            puntosBonoPrimarias = puntosBonoPrimarias
        )
    }

    /**
     * Convierte las 12 competencias de una profesión (4 principales + 8
     * secundarias, ver Profesion.kt) en una lista de Habilidad lista para
     * guardar en HojaDePersonaje.competenciasProfesion.
     *
     * Esto es lo que hace que "los puntos a repartir sean distintos según
     * la profesión": cada competencia saca su valorBase de una
     * característica concreta del personaje (Competencia.atributo), y las
     * principales multiplican esa característica ×3 mientras que las
     * secundarias se quedan en ×1. Como cada profesión elige atributos y
     * competencias distintas, dos personajes con las mismas
     * características pero profesiones distintas acaban con bases (y por
     * tanto con habilidades) completamente diferentes.
     *
     * Todas las competencias generadas empiezan con puntosInvertidos = 0:
     * el jugador reparte manualmente sus 100 puntos (+ el bono
     * extraordinario si le ha tocado) desde la pantalla.
     *
     * @param profesion la profesión ya elegida (tirada o, en el futuro,
     *   escogida a mano).
     * @param atributos las características ACTUALES del personaje: si el
     *   jugador cambia sus características después de generar las
     *   competencias, hay que volver a llamar a esta función para que las
     *   bases se recalculen (la pantalla ya lo hace así).
     */
    fun generarCompetencias(profesion: Profesion, atributos: Atributos): List<Habilidad> {
        val principales = profesion.competenciasPrimarias.map { competencia ->
            Habilidad(
                nombre = competencia.nombre,
                categoria = CategoriaHabilidad.PROFESIONAL,
                valorBase = competencia.atributo.valorEn(atributos) * 3, // Principal: característica × 3
                puntosInvertidos = 0,
                esPrimariaDeProfesion = true
            )
        }
        val secundarias = profesion.competenciasSecundarias.map { competencia ->
            Habilidad(
                nombre = competencia.nombre,
                categoria = CategoriaHabilidad.PROFESIONAL,
                valorBase = competencia.atributo.valorEn(atributos), // Secundaria: característica × 1
                puntosInvertidos = 0,
                esPrimariaDeProfesion = false
            )
        }
        return principales + secundarias
    }
}
