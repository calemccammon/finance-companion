package com.calemccammon.financecompanion.feature.conversation

import androidx.compose.ui.test.hasContentDescription
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onRoot
import com.calemccammon.financecompanion.catalog.FinanceTheme
import com.calemccammon.financecompanion.core.testing.FakeConversationRepository
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import org.junit.Rule
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import kotlin.test.Test

/** Pictures of the screen, kept in src/test/snapshots and compared by `verifyRoborazziDebug`. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(qualifiers = "en-rUS-w411dp-h891dp-xxhdpi")
class ConversationScreenshotTest {
    @get:Rule
    val compose = createComposeRule()

    private fun capture(
        name: String,
        answered: Boolean,
        dark: Boolean = false,
    ) {
        val repository = FakeConversationRepository().apply { answers["How is Apple doing?"] = appleAnswer }
        if (answered) runBlocking { repository.ask("How is Apple doing?") }
        val viewModel = ConversationViewModel(repository, Dispatchers.Default)
        compose.setContent { FinanceTheme(dark = dark) { ConversationRoute(viewModel) } }
        if (answered) {
            compose.waitUntil(5_000) {
                compose
                    .onAllNodes(
                        hasContentDescription("Close, $342.56", substring = true),
                    ).fetchSemanticsNodes()
                    .isNotEmpty()
            }
        }
        compose.onRoot().captureRoboImage("src/test/snapshots/$name.png")
    }

    @Test
    fun `an empty conversation`() = capture("conversation_empty", answered = false)

    @Test
    fun `an answer`() = capture("conversation_answer", answered = true)

    @Test
    fun `an answer in the dark theme`() = capture("conversation_answer_dark", answered = true, dark = true)
}
