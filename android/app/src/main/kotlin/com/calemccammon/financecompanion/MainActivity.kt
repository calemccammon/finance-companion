package com.calemccammon.financecompanion

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.a2ui.A2uiSurface
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle

class MainActivity : ComponentActivity() {
    private val viewModel: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        if (savedInstanceState == null) viewModel.ask("How is Apple doing?")

        setContent {
            MaterialTheme {
                Surface(Modifier.fillMaxSize()) {
                    val surfaces by viewModel.surfaces.collectAsStateWithLifecycle()
                    Column(Modifier.safeDrawingPadding().padding(16.dp)) {
                        surfaces.forEach { surface -> key(surface.id) { A2uiSurface(surface) } }
                    }
                }
            }
        }
    }
}
