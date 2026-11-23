package com.calemccammon.financecompanion.feature.conversation

import android.os.Looper
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.hasContentDescription
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import com.calemccammon.financecompanion.catalog.FinanceTheme
import com.calemccammon.financecompanion.core.testing.FakeConversationRepository
import kotlinx.coroutines.Dispatchers
import org.junit.Rule
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * The screen with its real view model over a stand-in repository: what the
 * user asks, what is drawn, and what a tap sends back to the agent.
 */
@RunWith(RobolectricTestRunner::class)
@Config(qualifiers = "en-rUS-w411dp-h891dp")
class ConversationScreenTest {
    @get:Rule
    val compose = createComposeRule()

    private val repository =
        FakeConversationRepository().apply {
            answers["How is Apple doing?"] = appleAnswer
            answers["Which stocks are most volatile?"] = appleAnswer
        }

    private fun show() {
        val viewModel = ConversationViewModel(repository, Dispatchers.Default)
        compose.setContent { FinanceTheme { ConversationRoute(viewModel) } }
    }

    private fun waitFor(description: String) =
        compose.waitUntil(TIMEOUT) {
            compose.onAllNodes(hasContentDescription(description, substring = true)).fetchSemanticsNodes().isNotEmpty()
        }

    @Test
    fun `an empty conversation suggests questions, and one asks it`() {
        show()

        compose.onNodeWithText("How is Apple doing?").performClick()

        waitFor("You asked: How is Apple doing?")
        waitFor("Close, $342.56")
    }

    @Test
    fun `a typed question is sent with the button, which is off while the box is empty`() {
        show()

        compose.onNodeWithContentDescription("Send").assertIsNotEnabled()
        compose.onNodeWithText("Ask about a stock or the economy").performTextInput("Which stocks are most volatile?")
        compose.onNodeWithContentDescription("Send").assertIsEnabled().performClick()

        waitFor("You asked: Which stocks are most volatile?")
    }

    @Test
    fun `a range button sends its action to the agent for the surface it is on`() {
        show()
        compose.onNodeWithText("How is Apple doing?").performClick()
        waitFor("Close, $342.56")

        compose.onNodeWithText("1 month").performScrollTo()
        // The list scrolls to the newest answer as it arrives; press once it is still.
        compose.waitForIdle()
        compose.onNodeWithText("1 month").performClick()
        // The tap reaches the view model through the main looper, which the
        // compose rule's wait does not run on its own.
        compose.waitUntil(TIMEOUT) {
            shadowOf(Looper.getMainLooper()).idle()
            repository.sent.isNotEmpty()
        }

        val (surface, json) = repository.sent.single()
        assertEquals("answer-1", surface)
        assertTrue(""""name":"set_range"""" in json, json)
        assertTrue(""""result":"/r1"""" in json && """"days":30""" in json, json)
    }

    @Test
    fun `a question the agent could not take is offered again`() {
        show()
        compose.onNodeWithText("Ask about a stock or the economy").performTextInput("How is the economy?")
        compose.onNodeWithContentDescription("Send").performClick()

        compose.waitUntil(TIMEOUT) {
            compose
                .onAllNodes(
                    androidx.compose.ui.test
                        .hasText("Try again"),
                ).fetchSemanticsNodes()
                .isNotEmpty()
        }
        repository.answers["How is the economy?"] = appleAnswer
        compose.onNodeWithText("Try again").performClick()

        waitFor("You asked: How is the economy?")
    }

    private companion object {
        const val TIMEOUT = 5_000L
    }
}
