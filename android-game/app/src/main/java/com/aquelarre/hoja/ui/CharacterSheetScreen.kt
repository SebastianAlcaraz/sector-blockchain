package com.aquelarre.hoja.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenu
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
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
import com.aquelarre.hoja.model.Habilidad
import com.aquelarre.hoja.model.HojaDePersonaje

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
            IdentidadSection(character, onCharacterChange)
        }

        item {
            AtributosSection(character, onCharacterChange)
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
private fun SectionCard(title: String, content: @Composable Column.() -> Unit) {
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

@OptIn(ExperimentalMaterial3Api::class)
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
        ExposedDropdownMenuBox(
            expanded = expanded,
            onExpandedChange = { expanded = it },
            modifier = Modifier.padding(top = 8.dp)
        ) {
            OutlinedTextField(
                value = character.categoriaSocial.etiqueta,
                onValueChange = {},
                readOnly = true,
                label = { Text("Categoría social") },
                trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
                modifier = Modifier
                    .fillMaxWidth()
                    .menuAnchor(MenuAnchorType.PrimaryNotEditable)
            )
            ExposedDropdownMenu(
                expanded = expanded,
                onDismissRequest = { expanded = false }
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
                IconButton(onClick = {
                    if (habilidad.puntosInvertidos > 0) {
                        onPuntosChange(habilidad, habilidad.puntosInvertidos - 5)
                    }
                }) {
                    Text("−", style = MaterialTheme.typography.titleMedium)
                }
                Text(
                    text = habilidad.puntosInvertidos.toString(),
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.width(24.dp)
                )
                IconButton(onClick = {
                    onPuntosChange(habilidad, habilidad.puntosInvertidos + 5)
                }) {
                    Text("+", style = MaterialTheme.typography.titleMedium)
                }
            }
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
