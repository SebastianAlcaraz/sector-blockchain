package com.aquelarre.hoja.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val AquelarreColorScheme = lightColorScheme(
    primary = BloodRed,
    onPrimary = ParchmentBackground,
    secondary = CandleGold,
    onSecondary = InkBrown,
    tertiary = NightPurple,
    background = ParchmentBackground,
    onBackground = InkBrown,
    surface = ParchmentSurface,
    onSurface = InkBrown
)

@Composable
fun AquelarreRPGTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = AquelarreColorScheme,
        typography = AquelarreTypography,
        content = content
    )
}
