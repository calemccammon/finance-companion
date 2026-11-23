package com.calemccammon.financecompanion

import androidx.a2ui.compose.runtime.A2uiMessageParser
import androidx.a2ui.compose.ui.A2uiMessageProcessor
import androidx.a2ui.model.processor.A2uiSurfaceModel
import androidx.a2ui.model.processor.processInput
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.calemccammon.financecompanion.catalog.FinanceCatalog
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** Spike for issue #3: asks the agent one question and passes taps back to it. */
class MainViewModel(
    private val agent: AgentClient = AgentClient(BuildConfig.AGENT_URL),
) : ViewModel() {
    private val parser = A2uiMessageParser()
    private val processor = A2uiMessageProcessor(catalogs = listOf(FinanceCatalog.create()))

    val surfaces: StateFlow<List<A2uiSurfaceModel>> = processor.activeSurfaces

    init {
        viewModelScope.launch(Dispatchers.Default) { processor.collectMessages() }
        // Taps and renderer errors go to the agent, and its answer is drawn.
        viewModelScope.launch(start = CoroutineStart.UNDISPATCHED) {
            processor.outboundEvents.collect { message ->
                launch { receive("action", message.toJson()) }
            }
        }
    }

    fun ask(question: String) {
        val json = buildJsonObject { put("text", question) }.toString()
        viewModelScope.launch { receive("ask", json) }
    }

    private suspend fun receive(
        path: String,
        json: String,
    ) {
        agent.post(path, json).collect { message -> processor.processInput(parser, message) }
    }
}
