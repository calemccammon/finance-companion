package com.calemccammon.financecompanion.feature.conversation

import androidx.a2ui.model.protocol.A2uiClientEventMessage
import kotlinx.serialization.json.Json
import java.io.File
import java.time.Instant
import kotlin.test.Test
import kotlin.test.assertEquals

/**
 * What the app sends when a button is pressed. The agent's test reads the same
 * file with the SDK's own model of the message, so the two sides agree.
 */
class ClientMessagesTest {
    @Test
    fun `a tap is sent as a v0_9_1 action message`() {
        val tap =
            A2uiClientEventMessage(
                type = "refresh",
                surfaceId = "s1",
                componentId = "refresh",
                timestamp = Instant.parse("2026-11-23T12:00:00Z").toEpochMilli(),
                context = mapOf("ticker" to "AAPL"),
            )

        val expected = File(System.getProperty("fc.catalog"), "fixtures/refresh-action.json").readText()

        assertEquals(Json.parseToJsonElement(expected), Json.parseToJsonElement(tap.toJson()))
    }
}
