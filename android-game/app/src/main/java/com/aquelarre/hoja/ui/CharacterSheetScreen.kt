package com.aquelarre.hoja.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.aquelarre.hoja.model.CategoriaHabilidad
import com.aquelarre.hoja.model.CategoriaSocial
import com.aquelarre.hoja.model.CreacionPersonaje
import com.aquelarre.hoja.model.Habilidad
import com.aquelarre.hoja.model.HojaDePersonaje
import com.aquelarre.hoja.model.Reino
import com.aquelarre.hoja.model.ResultadoCreacion

@Composable
fun CharacterSheetScreen(
    character: HojaDePersonaje,
    onCharacterChange: (HojaDePersonaje) -> Unit
) {
    val derivadas = character.calcularDerivadas()

    LazyColumn(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item {
            Text(
                text = "Hoja de Personaje",
                style = MaterialTheme.typography.titleLarge
            )
        }

        item {
            // Esta sección va ANTES de Identidad a propósito: sus
            // resultados (categoría social, profesión y dinero) rellenan
            // los campos de la sección de Identidad justo debajo.
            CreacionPorDadosSection(character, onCharacterChange)
        }

        item {
            IdentidadSection(character, onCharacterChange)
        }

        item {
            AtributosSection(character, onCharacterChange)
        }

        item {
            // Va después de Características a propósito: las bases de
            // estas competencias dependen de los atributos de arriba.
            CompetenciasProfesionSection(character, onCharacterChange)
        }

        item {
            DerivadasSection(derivadas)
        }

        item {
            Text("Habilidades", style = MaterialTheme.typography.titleMedium)
        }

        items(CategoriaHabilidad.entries.toList()) { categoria ->
            val habilidadesDeCategoria = character.habilidades.filter { it.categoria == categoria }
            if (habilidadesDeCategoria.isNotEmpty()) {
                HabilidadesCategoriaSection(
                    categoria = categoria,
                    habilidades = habilidadesDeCategoria,
                    onPuntosChange = { habilidad, nuevosPuntos ->
                        val actualizadas = character.habilidades.map {
                            if (it === habilidad) it.copy(puntosInvertidos = nuevosPuntos) else it
                        }
                        onCharacterChange(character.copy(habilidades = actualizadas))
                    }
                )
            }
        }

        item {
            TrasfondoSection(character, onCharacterChange)
        }
    }
}

@Composable
private fun SectionCard(title: String, content: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(text = title, style = MaterialTheme.typography.titleMedium)
            HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
            content()
        }
    }
}

/**
 * Sección de "creación por dados": el jugador elige el Reino de origen
 * (no se tira, se elige libremente) y luego puede tirar tantas veces
 * como quiera la categoría social + profesión + dinero inicial + bono
 * extraordinario, usando el motor CreacionPersonaje. El resultado de la
 * tirada se muestra en pantalla pero NO se aplica a la hoja de personaje
 * hasta que el jugador pulsa "Aplicar al personaje" — así se puede volver
 * a tirar si el resultado no convence, sin perder lo que ya hubiera en la
 * hoja.
 */
@Composable
private fun CreacionPorDadosSection(
    character: HojaDePersonaje,
    onCharacterChange: (HojaDePersonaje) -> Unit
) {
    // `resultado` guarda la última tirada mientras el jugador decide si
    // la aplica o no. Al ser un estado de Compose (remember + mutableStateOf),
    // cada vez que cambia se vuelve a dibujar esta sección automáticamente.
    var resultado by remember { mutableStateOf<ResultadoCreacion?>(null) }

    SectionCard(title = "Creación por dados") {
        Text(
            text = "Elige el reino de origen y tira los dados para obtener " +
                "categoría social, profesión y dinero inicial.",
            style = MaterialTheme.typography.bodyMedium
        )

        // --- Selector de Reino: aquí SÍ se elige, no se tira ---
        var reinoExpandido by remember { mutableStateOf(false) }
        Box(modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
            OutlinedTextField(
                value = character.reino.etiqueta,
                onValueChange = {},
                readOnly = true,
                label = { Text("Reino de origen") },
                trailingIcon = {
                    IconButton(onClick = { reinoExpandido = true }) {
                        Text("▾", style = MaterialTheme.typography.titleMedium)
                    }
                },
                modifier = Modifier.fillMaxWidth()
            )
            DropdownMenu(
                expanded = reinoExpandido,
                onDismissRequest = { reinoExpandido = false },
                modifier = Modifier.fillMaxWidth(0.9f)
            ) {
                Reino.entries.forEach { reino ->
                    DropdownMenuItem(
                        text = { Text(reino.etiqueta) },
                        onClick = {
                            // Guardamos el reino elegido directamente en el
                            // personaje: no hace falta tirar dados para esto.
                            onCharacterChange(character.copy(reino = reino))
                            reinoExpandido = false
                        }
                    )
                }
            }
        }

        // Botón "Tirar": llama al motor CreacionPersonaje.generar(), que
        // internamente tira categoría social, profesión, dinero y el bono
        // extraordinario de 1/100. El resultado se guarda en `resultado`
        // para mostrarlo, pero la hoja de personaje todavía no cambia.
        Button(
            onClick = { resultado = CreacionPersonaje.generar(character.reino) },
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 8.dp)
        ) {
            Text("Tirar categoría social y profesión")
        }

        // Si ya hay un resultado de una tirada anterior, lo mostramos con
        // un botón para confirmarlo y volcarlo a la hoja de personaje.
        val resultadoActual = resultado
        if (resultadoActual != null) {
            Column(modifier = Modifier.padding(top = 8.dp)) {
                DerivadaRow("Categoría social", resultadoActual.categoriaSocial.etiqueta)
                DerivadaRow("Profesión", resultadoActual.profesion.nombre)
                DerivadaRow("Dinero inicial", "${resultadoActual.dineroInicial} reales")

                // El bono extraordinario solo se muestra cuando ha salido
                // (puntosBonoPrimarias > 0); si no ha salido, no se enseña
                // esta fila para no confundir con un "0" sin contexto.
                if (resultadoActual.puntosBonoPrimarias > 0) {
                    DerivadaRow(
                        "¡Bono extraordinario!",
                        "+${resultadoActual.puntosBonoPrimarias} puntos en habilidades principales"
                    )
                }

                Button(
                    onClick = {
                        // Aquí es donde el resultado de la tirada se copia
                        // de verdad a la hoja de personaje. El dinero se
                        // guarda como texto (p.ej. "1825 reales") porque el
                        // campo `dinero` de HojaDePersonaje es de tipo
                        // String, pensado para anotaciones libres.
                        //
                        // Además generamos las 12 competencias (4
                        // principales + 8 secundarias) de la nueva
                        // profesión a partir de las características
                        // ACTUALES del personaje, y sustituimos por
                        // completo las competencias de profesión que
                        // hubiera antes: si repites la tirada, empiezas de
                        // cero con la profesión nueva, no se mezclan.
                        onCharacterChange(
                            character.copy(
                                categoriaSocial = resultadoActual.categoriaSocial,
                                profesion = resultadoActual.profesion.nombre,
                                dinero = "${resultadoActual.dineroInicial} reales",
                                competenciasProfesion = CreacionPersonaje.generarCompetencias(
                                    profesion = resultadoActual.profesion,
                                    atributos = character.atributos
                                ),
                                puntosBonoDisponibles = resultadoActual.puntosBonoPrimarias
                            )
                        )
                        // Limpiamos el resultado mostrado: ya está aplicado,
                        // así que no tiene sentido seguir viendo el botón
                        // de "Aplicar" hasta la siguiente tirada.
                        resultado = null
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 8.dp)
                ) {
                    Text("Aplicar al personaje")
                }
            }
        }
    }
}

@Composable
private fun IdentidadSection(
    character: HojaDePersonaje,
    onCharacterChange: (HojaDePersonaje) -> Unit
) {
    SectionCard(title = "Identidad") {
        OutlinedTextField(
            value = character.nombre,
            onValueChange = { onCharacterChange(character.copy(nombre = it)) },
            label = { Text("Nombre") },
            modifier = Modifier.fillMaxWidth()
        )

        var expanded by remember { mutableStateOf(false) }
        Box(modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
            OutlinedTextField(
                value = character.categoriaSocial.etiqueta,
                onValueChange = {},
                readOnly = true,
                label = { Text("Categoría social") },
                trailingIcon = {
                    IconButton(onClick = { expanded = true }) {
                        Text("▾", style = MaterialTheme.typography.titleMedium)
                    }
                },
                modifier = Modifier.fillMaxWidth()
            )
            DropdownMenu(
                expanded = expanded,
                onDismissRequest = { expanded = false },
                modifier = Modifier.fillMaxWidth(0.9f)
            ) {
                CategoriaSocial.entries.forEach { categoria ->
                    DropdownMenuItem(
                        text = { Text(categoria.etiqueta) },
                        onClick = {
                            onCharacterChange(character.copy(categoriaSocial = categoria))
                            expanded = false
                        }
                    )
                }
            }
        }

        OutlinedTextField(
            value = character.profesion,
            onValueChange = { onCharacterChange(character.copy(profesion = it)) },
            label = { Text("Profesión") },
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 8.dp)
        )

        Row(modifier = Modifier.padding(top = 8.dp)) {
            OutlinedTextField(
                value = character.genero,
                onValueChange = { onCharacterChange(character.copy(genero = it)) },
                label = { Text("Género") },
                modifier = Modifier.weight(1f)
            )
            OutlinedTextField(
                value = character.edad.toString(),
                onValueChange = { texto ->
                    onCharacterChange(character.copy(edad = texto.toIntOrNull() ?: character.edad))
                },
                label = { Text("Edad") },
                keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier
                    .weight(1f)
                    .padding(start = 8.dp)
            )
        }

        Row(modifier = Modifier.padding(top = 8.dp)) {
            OutlinedTextField(
                value = character.signoZodiacal,
                onValueChange = { onCharacterChange(character.copy(signoZodiacal = it)) },
                label = { Text("Signo zodiacal") },
                modifier = Modifier.weight(1f)
            )
            OutlinedTextField(
                value = character.estatura,
                onValueChange = { onCharacterChange(character.copy(estatura = it)) },
                label = { Text("Estatura") },
                modifier = Modifier
                    .weight(1f)
                    .padding(start = 8.dp)
            )
            OutlinedTextField(
                value = character.peso,
                onValueChange = { onCharacterChange(character.copy(peso = it)) },
                label = { Text("Peso") },
                modifier = Modifier
                    .weight(1f)
                    .padding(start = 8.dp)
            )
        }
    }
}

@Composable
private fun AtributosSection(
    character: HojaDePersonaje,
    onCharacterChange: (HojaDePersonaje) -> Unit
) {
    val a = character.atributos
    SectionCard(title = "Características") {
        val filas = listOf(
            Triple("Fuerza", a.fuerza) { v: Int -> onCharacterChange(character.copy(atributos = a.copy(fuerza = v))) },
            Triple("Destreza", a.destreza) { v: Int -> onCharacterChange(character.copy(atributos = a.copy(destreza = v))) },
            Triple("Agilidad", a.agilidad) { v: Int -> onCharacterChange(character.copy(atributos = a.copy(agilidad = v))) },
            Triple("Constitución", a.constitucion) { v: Int -> onCharacterChange(character.copy(atributos = a.copy(constitucion = v))) },
            Triple("Comunicación", a.comunicacion) { v: Int -> onCharacterChange(character.copy(atributos = a.copy(comunicacion = v))) },
            Triple("Instrucción", a.instruccion) { v: Int -> onCharacterChange(character.copy(atributos = a.copy(instruccion = v))) },
            Triple("Aspecto físico", a.aspecto) { v: Int -> onCharacterChange(character.copy(atributos = a.copy(aspecto = v))) },
            Triple("Poder", a.poder) { v: Int -> onCharacterChange(character.copy(atributos = a.copy(poder = v))) }
        )

        filas.chunked(2).forEach { par ->
            Row(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                par.forEach { (nombre, valor, onChange) ->
                    AttributeField(
                        nombre = nombre,
                        valor = valor,
                        onValorChange = onChange,
                        modifier = Modifier.weight(1f)
                    )
                    if (par.size == 2 && nombre != par.last().first) {
                        androidx.compose.foundation.layout.Spacer(modifier = Modifier.width(8.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun AttributeField(
    nombre: String,
    valor: Int,
    onValorChange: (Int) -> Unit,
    modifier: Modifier = Modifier
) {
    OutlinedTextField(
        value = valor.toString(),
        onValueChange = { texto -> texto.toIntOrNull()?.let(onValorChange) },
        label = { Text(nombre) },
        keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = KeyboardType.Number),
        modifier = modifier
    )
}

@Composable
private fun DerivadasSection(derivadas: com.aquelarre.hoja.model.EstadisticasDerivadas) {
    SectionCard(title = "Estadísticas derivadas") {
        DerivadaRow("Puntos de vida", derivadas.puntosDeVida.toString())
        DerivadaRow("Templanza", derivadas.templanza.toString())
        DerivadaRow("Bonificador de combate", derivadas.bonificadorCombate.toString())
        DerivadaRow("Bonificador al daño", derivadas.bonificadorDano)
        DerivadaRow("Resistencia al dolor", derivadas.resistenciaAlDolor.toString())
        DerivadaRow("Capacidad de carga", "${derivadas.capacidadDeCarga} libras")
    }
}

@Composable
private fun DerivadaRow(etiqueta: String, valor: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 2.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(etiqueta, style = MaterialTheme.typography.bodyMedium)
        Text(valor, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun HabilidadesCategoriaSection(
    categoria: CategoriaHabilidad,
    habilidades: List<Habilidad>,
    onPuntosChange: (Habilidad, Int) -> Unit
) {
    SectionCard(title = categoria.etiqueta) {
        habilidades.forEach { habilidad ->
            HabilidadRow(
                habilidad = habilidad,
                onDecrementar = {
                    if (habilidad.puntosInvertidos > 0) {
                        onPuntosChange(habilidad, habilidad.puntosInvertidos - 5)
                    }
                },
                onIncrementar = { onPuntosChange(habilidad, habilidad.puntosInvertidos + 5) }
            )
        }
    }
}

/**
 * Sección de las 12 competencias (4 principales + 8 secundarias) de la
 * profesión aplicada al personaje. No se muestra nada si todavía no se ha
 * aplicado ninguna profesión (competenciasProfesion vacía).
 *
 * Presupuesto de puntos, tal y como se acordó con el usuario:
 *  - Hay 100 puntos "normales" para repartir entre las 12 competencias
 *    (principales y secundarias indistintamente).
 *  - Si salió el bono extraordinario de creación (puntosBonoDisponibles >
 *    0), esos puntos de más SOLO se pueden gastar en las 4 competencias
 *    PRINCIPALES, nunca en las secundarias.
 *  - Ninguna competencia puede superar base×5 (tope que aparece citado en
 *    varios resúmenes de las reglas reales).
 *
 * Cómo se aplica esto en el código de abajo: en vez de llevar dos
 * "montones" de puntos separados, miramos el total ya gastado
 * (puntosInvertidos sumados de las 12 competencias) y comparamos contra
 * dos límites distintos según si el botón "+" que se ha pulsado es de una
 * competencia principal o secundaria:
 *  - Botón "+" de una SECUNDARIA: solo funciona si el total gastado
 *    todavía no llega a 100 (así nunca se puede colar en la parte que
 *    corresponde al bono).
 *  - Botón "+" de una PRINCIPAL: funciona si el total gastado no llega a
 *    100 + puntosBonoDisponibles (puede usar tanto el fondo común de 100
 *    como el bono).
 */
@Composable
private fun CompetenciasProfesionSection(
    character: HojaDePersonaje,
    onCharacterChange: (HojaDePersonaje) -> Unit
) {
    if (character.competenciasProfesion.isEmpty()) return

    val totalInvertido = character.competenciasProfesion.sumOf { it.puntosInvertidos }
    val limitePrincipales = 100 + character.puntosBonoDisponibles
    val limiteSecundarias = 100

    fun actualizarCompetencia(habilidad: Habilidad, nuevosPuntos: Int) {
        val actualizadas = character.competenciasProfesion.map {
            if (it === habilidad) it.copy(puntosInvertidos = nuevosPuntos) else it
        }
        onCharacterChange(character.copy(competenciasProfesion = actualizadas))
    }

    SectionCard(title = "Competencias de la profesión (${character.profesion})") {
        Text(
            text = if (character.puntosBonoDisponibles > 0) {
                "Puntos repartidos: $totalInvertido / 100 " +
                    "(+${character.puntosBonoDisponibles} de bono, solo en principales)"
            } else {
                "Puntos repartidos: $totalInvertido / 100"
            },
            style = MaterialTheme.typography.bodyMedium
        )

        val principales = character.competenciasProfesion.filter { it.esPrimariaDeProfesion }
        val secundarias = character.competenciasProfesion.filterNot { it.esPrimariaDeProfesion }

        Text(
            text = "Principales",
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.padding(top = 8.dp)
        )
        principales.forEach { habilidad ->
            HabilidadRow(
                habilidad = habilidad,
                onDecrementar = {
                    if (habilidad.puntosInvertidos > 0) {
                        actualizarCompetencia(habilidad, habilidad.puntosInvertidos - 5)
                    }
                },
                onIncrementar = {
                    val cabeEnElTope = habilidad.puntosInvertidos + 5 <= habilidad.valorBase * 5
                    val quedaPresupuesto = totalInvertido + 5 <= limitePrincipales
                    if (cabeEnElTope && quedaPresupuesto) {
                        actualizarCompetencia(habilidad, habilidad.puntosInvertidos + 5)
                    }
                }
            )
        }

        Text(
            text = "Secundarias",
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.padding(top = 8.dp)
        )
        secundarias.forEach { habilidad ->
            HabilidadRow(
                habilidad = habilidad,
                onDecrementar = {
                    if (habilidad.puntosInvertidos > 0) {
                        actualizarCompetencia(habilidad, habilidad.puntosInvertidos - 5)
                    }
                },
                onIncrementar = {
                    val cabeEnElTope = habilidad.puntosInvertidos + 5 <= habilidad.valorBase * 5
                    // Las secundarias nunca tocan el bono: su tope de
                    // presupuesto es siempre 100, aunque haya bono activo.
                    val quedaPresupuesto = totalInvertido + 5 <= limiteSecundarias
                    if (cabeEnElTope && quedaPresupuesto) {
                        actualizarCompetencia(habilidad, habilidad.puntosInvertidos + 5)
                    }
                }
            )
        }
    }
}

/** Fila reutilizable de "nombre (total) [-] puntos [+]" para una habilidad. */
@Composable
private fun HabilidadRow(
    habilidad: Habilidad,
    onDecrementar: () -> Unit,
    onIncrementar: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            text = "${habilidad.nombre} (${habilidad.total})",
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.weight(1f)
        )
        IconButton(onClick = onDecrementar) {
            Text("−", style = MaterialTheme.typography.titleMedium)
        }
        Text(
            text = habilidad.puntosInvertidos.toString(),
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.width(24.dp)
        )
        IconButton(onClick = onIncrementar) {
            Text("+", style = MaterialTheme.typography.titleMedium)
        }
    }
}

@Composable
private fun TrasfondoSection(
    character: HojaDePersonaje,
    onCharacterChange: (HojaDePersonaje) -> Unit
) {
    SectionCard(title = "Trasfondo") {
        OutlinedTextField(
            value = character.trasfondo,
            onValueChange = { onCharacterChange(character.copy(trasfondo = it)) },
            label = { Text("Historia y notas del personaje") },
            minLines = 4,
            modifier = Modifier.fillMaxWidth()
        )
    }
}
