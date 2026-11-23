package com.calemccammon.financecompanion

import androidx.compose.ui.test.hasContentDescription
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.v2.createEmptyComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import dagger.hilt.android.testing.HiltAndroidRule
import dagger.hilt.android.testing.HiltAndroidTest
import org.junit.Rule
import org.junit.Test
import org.junit.rules.RuleChain
import org.junit.runner.RunWith
import kotlin.test.assertEquals

/**
 * The whole app on a device, as a user goes through it: the real screen,
 * view model, renderer, Room database and HTTP client, against a stand-in
 * for the agent.
 */
@HiltAndroidTest
@RunWith(AndroidJUnit4::class)
class ConversationJourneyTest {
    private val agent = StandInAgent()
    private val compose = createEmptyComposeRule()

    // The stand-in is up before Hilt builds the app.
    @get:Rule
    val rules: RuleChain = RuleChain.outerRule(agent).around(HiltAndroidRule(this)).around(compose)

    private fun launch(): ActivityScenario<MainActivity> = ActivityScenario.launch(MainActivity::class.java)

    private fun waitForDescription(text: String) =
        compose.waitUntil(TIMEOUT) {
            compose.onAllNodes(hasContentDescription(text, substring = true)).fetchSemanticsNodes().isNotEmpty()
        }

    private fun waitForText(text: String) =
        compose.waitUntil(
            TIMEOUT,
        ) { compose.onAllNodes(hasText(text, substring = true)).fetchSemanticsNodes().isNotEmpty() }

    @Test
    fun aSuggestedQuestionIsAnsweredARangeIsChangedAndBothSurviveARestart() {
        launch().use {
            compose.onNodeWithText("How is Apple doing?").performClick()
            waitForDescription("Close, $342.56")
            waitForDescription("closes from 2026-08-24")

            // The list scrolls to the new answer as it arrives, and a tap
            // during a scroll only stops the scroll: press until the agent hears it.
            compose.waitUntil(TIMEOUT) {
                compose.onNodeWithText("1 month").performScrollTo().performClick()
                Thread.sleep(PRESS_INTERVAL)
                agent.requests.any { it.first == "/action" }
            }
            waitForDescription("closes from 2026-10-21")
        }
        assertEquals(listOf("/ask", "/action"), agent.requests.map { it.first })

        // A new activity and view model: what shows was read from the device.
        agent.down = true
        launch().use {
            waitForDescription("You asked: How is Apple doing?")
            waitForDescription("closes from 2026-10-21")
        }
    }

    @Test
    fun aQuestionTheAgentCannotTakeIsOfferedAgain() {
        agent.down = true
        launch().use {
            compose.onNodeWithText("How is Apple doing?").performClick()
            waitForText("Could not reach the agent")

            agent.down = false
            compose.onNodeWithText("Try again").performClick()
            waitForDescription("Close, $342.56")
        }
    }

    private companion object {
        const val TIMEOUT = 10_000L
        const val PRESS_INTERVAL = 500L
    }
}
