package com.calemccammon.financecompanion.catalog

import androidx.a2ui.compose.runtime.A2uiMessageParser
import androidx.a2ui.compose.ui.A2uiMessageProcessor
import androidx.a2ui.model.processor.processInput
import androidx.a2ui.model.protocol.A2uiClientEventMessage
import androidx.a2ui.model.protocol.A2uiClientToServerMessage
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.a2ui.A2uiSurface
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.assertHasClickAction
import androidx.compose.ui.test.hasContentDescription
import androidx.compose.ui.test.isHeading
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import org.junit.After
import org.junit.Before
import org.junit.Rule
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import java.util.concurrent.CopyOnWriteArrayList
import kotlin.test.Test
import kotlin.test.assertEquals

/**
 * The finance components, drawn from a surface written as the agent sends
 * it: every figure bound to a path in the data model.
 */
@RunWith(RobolectricTestRunner::class)
@Config(qualifiers = "en-rUS-w411dp-h1600dp")
class ComponentsTest {
    @get:Rule
    val compose = createComposeRule()

    private val processor = A2uiMessageProcessor(catalogs = listOf(FinanceCatalog.create()))
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val outbound = CopyOnWriteArrayList<A2uiClientToServerMessage>()

    @Before
    fun show() {
        scope.launch { processor.collectMessages() }
        scope.launch(start = CoroutineStart.UNDISPATCHED) { processor.outboundEvents.collect { outbound += it } }
        val parser = A2uiMessageParser()
        File(System.getProperty("fc.catalog"), "fixtures/components-surface.jsonl")
            .readLines()
            .filter {
                it.isNotBlank()
            }.forEach {
                processor.processInput(parser, it)
            }
        compose.setContent {
            MaterialTheme {
                val surfaces by processor.activeSurfaces.collectAsState()
                Column(Modifier.verticalScroll(rememberScrollState())) { surfaces.forEach { A2uiSurface(it) } }
            }
        }
        compose.waitUntil(TIMEOUT) {
            compose.onAllNodes(hasContentDescription("Close", substring = true)).fetchSemanticsNodes().isNotEmpty()
        }
    }

    @After
    fun stop() = scope.cancel()

    @Test
    fun `a metric card writes its bound figure in the chosen format`() {
        compose.onNodeWithContentDescription("Close, $342.56, 20 November").assertExists()
        compose.onNodeWithContentDescription("Change, −4.20%").assertExists()
    }

    @Test
    fun `a price chart describes the closes it draws`() {
        compose
            .onNodeWithContentDescription(
                "Apple, closes from 2026-11-18 to 2026-11-20, starting at $352.45, ending at $342.56",
            ).performScrollTo()
            .assertExists()
    }

    @Test
    fun `ranked bars read each row with its figure, under a heading`() {
        compose.onNodeWithText("Returns").performScrollTo().assert(isHeading())
        compose.onNodeWithContentDescription("NVDA, +12.50%").assertHasClickAction()
        compose.onNodeWithContentDescription("AAPL, −4.20%").assertHasClickAction()
    }

    @Test
    fun `pressing a ranked row sends its action with the row's ticker`() {
        compose.onNodeWithContentDescription("NVDA, +12.50%").performScrollTo().performClick()
        compose.waitUntil(TIMEOUT) { outbound.any { it is A2uiClientEventMessage } }

        val tap = outbound.filterIsInstance<A2uiClientEventMessage>().single()
        assertEquals("open_ticker", tap.type)
        assertEquals(mapOf("ticker" to "NVDA"), tap.context)
    }

    @Test
    fun `an overlay chart names both lines from the data`() {
        compose
            .onNodeWithContentDescription("AAPL and 10-year Treasury yield from 2026-11-18 to 2026-11-20")
            .performScrollTo()
            .assertExists()
    }

    @Test
    fun `nothing was reported back as an error`() {
        compose.waitForIdle()
        assertEquals(emptyList(), outbound.filter { it !is A2uiClientEventMessage })
    }

    private companion object {
        const val TIMEOUT = 5_000L
    }
}
