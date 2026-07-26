package com.aquelarre.hoja

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import com.aquelarre.hoja.model.HojaDePersonaje
import com.aquelarre.hoja.model.habilidadesPorDefecto
import com.aquelarre.hoja.ui.CharacterSheetScreen
import com.aquelarre.hoja.ui.theme.AquelarreRPGTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            AquelarreRPGTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    var character by remember {
                        mutableStateOf(HojaDePersonaje(habilidades = habilidadesPorDefecto()))
                    }
                    CharacterSheetScreen(
                        character = character,
                        onCharacterChange = { character = it }
                    )
                }
            }
        }
    }
}
