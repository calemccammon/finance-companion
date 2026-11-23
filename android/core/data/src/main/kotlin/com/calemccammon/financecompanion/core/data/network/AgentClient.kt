package com.calemccammon.financecompanion.core.data.network

import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.sse.EventSource
import okhttp3.sse.EventSourceListener
import okhttp3.sse.EventSources
import java.io.IOException

/** What the agent sends while answering. */
sealed interface AgentEvent {
    /** The question being answered: sent first, so an answer begun by a tap can be named. */
    data class Question(
        val text: String,
    ) : AgentEvent

    /** One A2UI message, as JSON. */
    data class Message(
        val json: String,
    ) : AgentEvent
}

/**
 * Talks to the agent. Each request is a POST whose answer arrives on the same
 * response as Server-Sent Events: `question` events and A2UI messages.
 */
class AgentClient(
    private val baseUrl: String,
    private val client: OkHttpClient,
) {
    fun post(
        path: String,
        json: String,
    ): Flow<AgentEvent> =
        callbackFlow {
            val request =
                Request
                    .Builder()
                    .url(baseUrl.trimEnd('/') + "/" + path)
                    .header("Accept", "text/event-stream")
                    .post(json.toRequestBody(JSON))
                    .build()
            val listener =
                object : EventSourceListener() {
                    override fun onEvent(
                        eventSource: EventSource,
                        id: String?,
                        type: String?,
                        data: String,
                    ) {
                        val event =
                            if (type == "question") {
                                AgentEvent.Question(Json.parseToJsonElement(data).jsonPrimitive.content)
                            } else {
                                AgentEvent.Message(data)
                            }
                        trySend(event)
                    }

                    override fun onClosed(eventSource: EventSource) {
                        close()
                    }

                    override fun onFailure(
                        eventSource: EventSource,
                        t: Throwable?,
                        response: Response?,
                    ) {
                        close(t ?: IOException("The agent answered HTTP ${response?.code}"))
                    }
                }
            val source = EventSources.createFactory(client).newEventSource(request, listener)
            awaitClose { source.cancel() }
        }

    private companion object {
        val JSON = "application/json".toMediaType()
    }
}
