package com.calemccammon.financecompanion.core.data

import com.calemccammon.financecompanion.core.data.database.ConversationDao
import com.calemccammon.financecompanion.core.data.database.ExchangeEntity
import com.calemccammon.financecompanion.core.data.database.MessageEntity
import com.calemccammon.financecompanion.core.data.network.AgentClient
import com.calemccammon.financecompanion.core.data.network.AgentEvent
import com.calemccammon.financecompanion.core.domain.AgentUnavailableException
import com.calemccammon.financecompanion.core.domain.ConversationRepository
import com.calemccammon.financecompanion.core.domain.Exchange
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import java.io.IOException
import java.time.Clock
import java.time.Instant
import javax.inject.Inject

/**
 * The conversation with the database as its one source of truth: every
 * message the agent sends is written there as it arrives, and the screen
 * reads only the database.
 */
class OfflineFirstConversationRepository
    @Inject
    constructor(
        private val dao: ConversationDao,
        private val agent: AgentClient,
        private val clock: Clock,
    ) : ConversationRepository {
        override val exchanges: Flow<List<Exchange>> =
            dao.observe().map { rows ->
                rows.map { row ->
                    Exchange(
                        id = row.exchange.id,
                        question = row.exchange.question,
                        askedAt = Instant.ofEpochMilli(row.exchange.askedAt),
                        surfaceId = row.exchange.surfaceId,
                        messages = row.messages.sortedBy { it.id }.map { it.json },
                    )
                }
            }

        override suspend fun ask(question: String) {
            val exchange = dao.insert(ExchangeEntity(question = question, askedAt = clock.millis()))
            val body = buildJsonObject { put("text", question) }.toString()
            try {
                receive(agent.post("ask", body), exchange, asked = question)
            } catch (e: AgentUnavailableException) {
                // A question with no answer is not kept: the screen offers to ask again.
                dao.delete(exchange)
                throw e
            }
        }

        override suspend fun send(
            surfaceId: String,
            message: String,
        ) {
            val exchange = dao.exchangeFor(surfaceId) ?: return
            receive(agent.post("action", message), exchange)
        }

        /**
         * Stores what the agent sends under [exchange], until a question
         * starts a new one. The echo of [asked], the question just put to it,
         * starts nothing.
         */
        private suspend fun receive(
            events: Flow<AgentEvent>,
            exchange: Long,
            asked: String? = null,
        ) {
            var current = exchange
            var echo = asked
            try {
                events.collect { event ->
                    when (event) {
                        is AgentEvent.Question ->
                            if (event.text == echo) {
                                echo = null
                            } else {
                                current = dao.insert(ExchangeEntity(question = event.text, askedAt = clock.millis()))
                            }
                        is AgentEvent.Message -> {
                            createdSurface(event.json)?.let { dao.setSurface(current, it) }
                            dao.insert(MessageEntity(exchangeId = current, json = event.json))
                        }
                    }
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: IOException) {
                throw AgentUnavailableException(e)
            }
        }

        private fun createdSurface(json: String): String? =
            runCatching {
                Json
                    .parseToJsonElement(json)
                    .jsonObject["createSurface"]
                    ?.jsonObject
                    ?.get("surfaceId")
                    ?.jsonPrimitive
                    ?.content
            }.getOrNull()
    }
