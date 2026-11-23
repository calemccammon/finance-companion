package com.calemccammon.financecompanion.core.domain

import kotlinx.coroutines.flow.Flow
import java.time.Instant

/**
 * One question and the agent's answer to it: the A2UI messages, as JSON, in
 * the order they arrived. Drawing them again in that order draws the answer
 * as it last stood.
 */
data class Exchange(
    val id: Long,
    val question: String,
    val askedAt: Instant,
    /** The surface the answer is drawn on, once the agent has created it. */
    val surfaceId: String?,
    val messages: List<String>,
)

/**
 * The conversation with the agent, kept on the device.
 *
 * Nothing the agent sends is handed to the caller: it is stored as it
 * arrives, and [exchanges] emits again. So the screen reads one place, and
 * the conversation is all there after the app is closed.
 */
interface ConversationRepository {
    /** Every exchange, oldest first. */
    val exchanges: Flow<List<Exchange>>

    /** Asks the agent [question]. Fails with [AgentUnavailableException], keeping nothing. */
    suspend fun ask(question: String)

    /**
     * Sends an A2UI client message (an `action` or an `error`) about [surfaceId].
     * What comes back is stored under the exchange that drew the surface, or
     * under a new exchange when the agent answers with a new question.
     * Fails with [AgentUnavailableException].
     */
    suspend fun send(
        surfaceId: String,
        message: String,
    )
}

/** The agent could not be reached, or broke off its answer. */
class AgentUnavailableException(
    cause: Throwable? = null,
) : Exception("The agent could not be reached", cause)
