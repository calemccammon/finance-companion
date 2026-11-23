package com.calemccammon.financecompanion.catalog

import androidx.a2ui.compose.runtime.A2uiMessageParser
import androidx.a2ui.compose.ui.A2uiMessageProcessor
import androidx.a2ui.model.processor.processInput
import androidx.a2ui.model.protocol.A2uiClientErrorMessage
import androidx.a2ui.model.protocol.A2uiClientToServerMessage
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.a2ui.A2uiSurface
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.test.hasContentDescription
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import org.junit.After
import org.junit.Rule
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * The renderer with this app's catalog: a v0.9.1 surface as the agent sends
 * it is drawn, and a component the catalog lacks is reported back.
 */
@RunWith(RobolectricTestRunner::class)
class RendererTest {
    @get:Rule
    val compose = createComposeRule()

    private val processor = A2uiMessageProcessor(catalogs = listOf(FinanceCatalog.create()))

    // The processor works on real threads, as it does in the app; a test
    // dispatcher would not move while the compose rule waits.
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    @After
    fun stop() = scope.cancel()

    private val parser = A2uiMessageParser()

    private fun send(vararg messages: String) = messages.forEach { processor.processInput(parser, it) }

    private val create =
        """{"version": "v0.9.1", "createSurface": {"surfaceId": "s1", "catalogId": "${FinanceCatalog.ID}"}}"""

    private fun components(vararg json: String) =
        """{"version": "v0.9.1", "updateComponents": {"surfaceId": "s1", "components": [${json.joinToString()}]}}"""

    private fun show() {
        compose.setContent {
            MaterialTheme {
                val surfaces by processor.activeSurfaces.collectAsState()
                surfaces.forEach { A2uiSurface(it) }
            }
        }
    }

    @Test
    fun `a custom component draws a figure bound to the data model`() {
        run {
            scope.launch { processor.collectMessages() }
            // The same messages the Python agent's test builds with the SDK.
            send(
                *File(
                    "../../catalog/fixtures/metric-card-surface.jsonl",
                ).readLines().filter { it.isNotBlank() }.toTypedArray(),
            )
            show()

            compose.waitUntil(TIMEOUT) {
                compose.onAllNodes(hasContentDescription("Close, 182.31")).fetchSemanticsNodes().isNotEmpty()
            }
            compose.onNodeWithText("Apple").assertExists()
        }
    }

    @Test
    fun `an unknown component is reported to the agent and does not crash`() {
        run {
            val outbound = java.util.concurrent.CopyOnWriteArrayList<A2uiClientToServerMessage>()
            scope.launch { processor.collectMessages() }
            scope.launch(start = CoroutineStart.UNDISPATCHED) { processor.outboundEvents.collect { outbound += it } }

            send(create, components("""{"id": "root", "component": "Sparkline", "values": {"path": "/series"}}"""))
            show()
            compose.waitUntil(TIMEOUT) { outbound.isNotEmpty() }

            val error = outbound.single() as A2uiClientErrorMessage
            assertTrue("Sparkline" in error.toString(), error.toString())
            assertEquals(1, processor.activeSurfaces.value.size)
        }
    }

    private companion object {
        const val TIMEOUT = 5_000L
    }
}
