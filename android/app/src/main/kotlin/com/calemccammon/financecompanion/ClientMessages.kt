package com.calemccammon.financecompanion

import androidx.a2ui.model.protocol.A2uiClientErrorMessage
import androidx.a2ui.model.protocol.A2uiClientEventMessage
import androidx.a2ui.model.protocol.A2uiClientToServerMessage
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.time.Instant

/*
 * The renderer hands over what the user did as objects; the protocol sends
 * them as JSON. The renderer has no encoder for its own outbound messages, so
 * this writes the v0.9.1 `action` and `error` messages.
 */

/** The message as A2UI v0.9.1 JSON. */
fun A2uiClientToServerMessage.toJson(): String =
    when (this) {
        is A2uiClientEventMessage ->
            buildJsonObject {
                put("version", VERSION)
                put(
                    "action",
                    buildJsonObject {
                        put("name", type)
                        put("surfaceId", surfaceId)
                        put("sourceComponentId", componentId)
                        put("timestamp", Instant.ofEpochMilli(timestamp).toString())
                        put("context", context.toJsonElement())
                    },
                )
            }.toString()
        is A2uiClientErrorMessage ->
            buildJsonObject {
                put("version", VERSION)
                put(
                    "error",
                    buildJsonObject {
                        put("code", code)
                        put("surfaceId", surfaceId)
                        put("message", message)
                    },
                )
            }.toString()
    }

private const val VERSION = "v0.9.1"

private fun Any?.toJsonElement(): JsonElement =
    when (this) {
        null -> JsonNull
        is String -> JsonPrimitive(this)
        is Number -> JsonPrimitive(this)
        is Boolean -> JsonPrimitive(this)
        is Map<*, *> -> JsonObject(entries.associate { (k, v) -> k.toString() to v.toJsonElement() })
        is Iterable<*> -> JsonArray(map { it.toJsonElement() })
        else -> JsonPrimitive(toString())
    }
