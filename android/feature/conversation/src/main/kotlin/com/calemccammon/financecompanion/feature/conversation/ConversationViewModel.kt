package com.calemccammon.financecompanion.feature.conversation

import androidx.a2ui.compose.runtime.A2uiMessageParser
import androidx.a2ui.compose.ui.A2uiMessageProcessor
import androidx.a2ui.model.processor.A2uiSurfaceModel
import androidx.a2ui.model.processor.processInput
import androidx.a2ui.model.protocol.A2uiClientErrorMessage
import androidx.a2ui.model.protocol.A2uiClientEventMessage
import androidx.compose.runtime.Immutable
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.calemccammon.financecompanion.catalog.FinanceCatalog
import com.calemccammon.financecompanion.core.domain.AgentUnavailableException
import com.calemccammon.financecompanion.core.domain.ConversationRepository
import com.calemccammon.financecompanion.core.domain.Exchange
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.collections.immutable.ImmutableList
import kotlinx.collections.immutable.persistentListOf
import kotlinx.collections.immutable.toImmutableList
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

/** One question on screen, and the surface its answer is drawn on once there is one. */
@Immutable
data class ExchangeItem(
    val id: Long,
    val question: String,
    val surfaceId: String?,
)

@Immutable
data class ConversationState(
    val exchanges: ImmutableList<ExchangeItem> = persistentListOf(),
    /** A question is on its way to the agent. */
    val asking: Boolean = false,
    /** The question that could not be asked, to offer again. */
    val unanswered: String? = null,
)

/**
 * Draws the conversation from what the device holds.
 *
 * Every stored A2UI message is fed to the renderer once, in order; so on a
 * new launch the whole conversation is drawn again from the database, and as
 * an answer streams in, each message reaches the screen as it is stored. Taps
 * and renderer errors go back to the agent through the repository.
 */
@HiltViewModel
class ConversationViewModel
    internal constructor(
        private val repository: ConversationRepository,
        rendering: CoroutineDispatcher,
    ) : ViewModel() {
        @Inject
        constructor(repository: ConversationRepository) : this(repository, Dispatchers.Default)

        private val parser = A2uiMessageParser()
        private val processor = A2uiMessageProcessor(catalogs = listOf(FinanceCatalog.create()))

        /** How many of each exchange's messages the renderer has been given. */
        private val fed = mutableMapOf<Long, Int>()

        private val mutableState = MutableStateFlow(ConversationState())
        val state: StateFlow<ConversationState> = mutableState.asStateFlow()

        val surfaces: StateFlow<List<A2uiSurfaceModel>> = processor.activeSurfaces

        init {
            viewModelScope.launch(rendering) { processor.collectMessages() }
            viewModelScope.launch(start = CoroutineStart.UNDISPATCHED) {
                processor.outboundEvents.collect { message ->
                    val surfaceId =
                        when (message) {
                            is A2uiClientEventMessage -> message.surfaceId
                            is A2uiClientErrorMessage -> message.surfaceId
                        }
                    launch { send(surfaceId, message.toJson()) }
                }
            }
            viewModelScope.launch { repository.exchanges.collect(::show) }
        }

        fun ask(question: String) {
            val text = question.trim()
            if (text.isEmpty() || state.value.asking) return
            mutableState.update { it.copy(asking = true, unanswered = null) }
            viewModelScope.launch {
                try {
                    repository.ask(text)
                    mutableState.update { it.copy(asking = false) }
                } catch (_: AgentUnavailableException) {
                    mutableState.update { it.copy(asking = false, unanswered = text) }
                }
            }
        }

        fun retry() {
            state.value.unanswered?.let(::ask)
        }

        fun dismiss() = mutableState.update { it.copy(unanswered = null) }

        private suspend fun send(
            surfaceId: String,
            json: String,
        ) {
            try {
                repository.send(surfaceId, json)
            } catch (_: AgentUnavailableException) {
                // A tap the agent did not hear changes nothing on screen; the user can tap again.
            }
        }

        private fun show(exchanges: List<Exchange>) {
            for (exchange in exchanges) {
                val done = fed[exchange.id] ?: 0
                exchange.messages.drop(done).forEach { processor.processInput(parser, it) }
                fed[exchange.id] = exchange.messages.size
            }
            val items = exchanges.map { ExchangeItem(it.id, it.question, it.surfaceId) }.toImmutableList()
            mutableState.update { it.copy(exchanges = items) }
        }
    }
