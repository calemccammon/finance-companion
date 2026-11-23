package com.calemccammon.financecompanion.core.testing

import com.calemccammon.financecompanion.core.domain.AgentUnavailableException
import com.calemccammon.financecompanion.core.domain.ConversationRepository
import com.calemccammon.financecompanion.core.domain.Exchange
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.update
import java.time.Instant

/**
 * The conversation in memory. A question is answered with whatever
 * [answers] holds for it; with nothing there, asking fails as if the agent
 * were down.
 */
class FakeConversationRepository : ConversationRepository {
    private val state = MutableStateFlow<List<Exchange>>(emptyList())

    override val exchanges: Flow<List<Exchange>> = state

    /** The A2UI messages that answer each question. */
    val answers = mutableMapOf<String, List<String>>()

    /** What [send] stores for the next client message, if anything. */
    var nextReply: List<String> = emptyList()

    /** Every client message sent, with its surface. */
    val sent = mutableListOf<Pair<String, String>>()

    /** While set, asking waits for it. */
    var gate: CompletableDeferred<Unit>? = null

    private var nextId = 1L

    override suspend fun ask(question: String) {
        gate?.await()
        val messages = answers[question] ?: throw AgentUnavailableException()
        state.update { it + Exchange(nextId++, question, Instant.EPOCH, surfaceOf(messages), messages) }
    }

    override suspend fun send(
        surfaceId: String,
        message: String,
    ) {
        sent += surfaceId to message
        val reply = nextReply
        state.update { all ->
            all.map {
                if (it.surfaceId ==
                    surfaceId
                ) {
                    it.copy(messages = it.messages + reply)
                } else {
                    it
                }
            }
        }
    }

    private fun surfaceOf(messages: List<String>): String? =
        messages.firstNotNullOfOrNull {
            Regex("\"createSurface\"\\s*:\\s*\\{\\s*\"surfaceId\"\\s*:\\s*\"([^\"]+)\"").find(it)?.groupValues?.get(1)
        }
}
