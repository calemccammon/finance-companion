package com.calemccammon.financecompanion

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.calemccammon.financecompanion.catalog.FinanceTheme
import com.calemccammon.financecompanion.feature.conversation.ConversationRoute
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        setContent {
            FinanceTheme {
                ConversationRoute()
            }
        }
    }
}
