package com.calemccammon.financecompanion

import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.sse.EventSource
import okhttp3.sse.EventSourceListener
import okhttp3.sse.EventSources
import java.io.IOException

/**
 * Talks to the agent. Each request is a POST whose answer arrives on the same
 * response as Server-Sent Events, one A2UI message per event.
 */
class AgentClient(
    private val baseUrl: String,
    private val client: OkHttpClient = OkHttpClient(),
) {
    /** Sends [json] to [path] and emits each A2UI message of the answer, in order. */
    fun post(
        path: String,
        json: String,
    ): Flow<String> =
        callbackFlow {
            val request =
                Request
                    .Builder()
                    .url(baseUrl + path)
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
                        trySend(data)
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
