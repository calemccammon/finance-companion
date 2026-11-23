package com.calemccammon.financecompanion.catalog

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

/** The app's Material 3 theme, light or dark as the system is, from one green seed. */
@Composable
fun FinanceTheme(
    dark: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(colorScheme = if (dark) darkColors else lightColors, content = content)
}

private val lightColors =
    lightColorScheme(
        primary = Color(0xFF2F6A3C),
        onPrimary = Color(0xFFFFFFFF),
        primaryContainer = Color(0xFFB2F1B7),
        onPrimaryContainer = Color(0xFF145127),
        secondary = Color(0xFF516351),
        secondaryContainer = Color(0xFFD4E8D1),
        onSecondaryContainer = Color(0xFF3A4B3A),
        surface = Color(0xFFF7FBF2),
        onSurface = Color(0xFF181D17),
        surfaceVariant = Color(0xFFDDE5DA),
        onSurfaceVariant = Color(0xFF414941),
        surfaceContainer = Color(0xFFEBEFE6),
        surfaceContainerHigh = Color(0xFFE5EAE1),
        surfaceContainerHighest = Color(0xFFE0E4DB),
        background = Color(0xFFF7FBF2),
        onBackground = Color(0xFF181D17),
        error = Color(0xFFBA1A1A),
    )

private val darkColors =
    darkColorScheme(
        primary = Color(0xFF96D59C),
        onPrimary = Color(0xFF003914),
        primaryContainer = Color(0xFF145127),
        onPrimaryContainer = Color(0xFFB2F1B7),
        secondary = Color(0xFFB8CCB6),
        secondaryContainer = Color(0xFF3A4B3A),
        onSecondaryContainer = Color(0xFFD4E8D1),
        surface = Color(0xFF101510),
        onSurface = Color(0xFFDFE4DB),
        surfaceVariant = Color(0xFF414941),
        onSurfaceVariant = Color(0xFFC1C9BE),
        surfaceContainer = Color(0xFF1C211B),
        surfaceContainerHigh = Color(0xFF262B25),
        surfaceContainerHighest = Color(0xFF313630),
        background = Color(0xFF101510),
        onBackground = Color(0xFFDFE4DB),
        error = Color(0xFFFFB4AB),
    )
