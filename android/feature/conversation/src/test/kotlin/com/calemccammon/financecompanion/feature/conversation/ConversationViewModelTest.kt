package com.calemccammon.financecompanion.feature.conversation

import com.calemccammon.financecompanion.core.testing.FakeConversationRepository
import com.calemccammon.financecompanion.core.testing.Fixtures
import com.calemccammon.financecompanion.core.testing.MainDispatcherRule
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Rule
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

/** The recorded answer to "How is Apple doing?", as the messages a repository stores. */
internal val appleAnswer: List<String> = Fixtures.messages("apple-answer.sse")

@RunWith(RobolectricTestRunner::class)
class ConversationViewModelTest {
    @get:Rule
    val main = MainDispatcherRule(UnconfinedTestDispatcher())

    private val repository = FakeConversationRepository().apply { answers["How is Apple doing?"] = appleAnswer }

    private fun TestScope.viewModel() = ConversationViewModel(repository, main.dispatcher).also { advanceUntilIdle() }

    @Test
    fun `asking stores the exchange and draws its answer on a surface`() =
        runTest {
            val vm = viewModel()

            vm.ask("  How is Apple doing?  ")
            advanceUntilIdle()

            val state = vm.state.value
            assertEquals(listOf(ExchangeItem(1, "How is Apple doing?", "answer-1")), state.exchanges)
            assertEquals(false, state.asking)
            assertEquals(listOf("answer-1"), vm.surfaces.value.map { it.id })
        }

    @Test
    fun `while a question is on its way, the screen says so and another is not sent`() =
        runTest {
            repository.gate = CompletableDeferred()
            val vm = viewModel()

            vm.ask("How is Apple doing?")
            vm.ask("How is Apple doing?")
            assertEquals(true, vm.state.value.asking)

            repository.gate?.complete(Unit)
            advanceUntilIdle()
            assertEquals(1, vm.state.value.exchanges.size)
        }

    @Test
    fun `a question the agent could not take is offered again`() =
        runTest {
            val vm = viewModel()

            vm.ask("How is the economy?")
            advanceUntilIdle()
            assertEquals("How is the economy?", vm.state.value.unanswered)
            assertEquals(0, vm.state.value.exchanges.size)

            repository.answers["How is the economy?"] = appleAnswer
            vm.retry()
            advanceUntilIdle()
            assertNull(vm.state.value.unanswered)
            assertEquals(1, vm.state.value.exchanges.size)
        }

    @Test
    fun `a blank question is not asked`() =
        runTest {
            val vm = viewModel()
            vm.ask("   ")
            assertEquals(false, vm.state.value.asking)
        }

    @Test
    fun `a conversation already on the device is drawn when the screen opens`() =
        runTest {
            repository.ask("How is Apple doing?")

            val vm = viewModel()

            assertEquals(1, vm.state.value.exchanges.size)
            assertEquals(listOf("answer-1"), vm.surfaces.value.map { it.id })
        }

    @Test
    fun `messages added to an exchange later are drawn, and the earlier ones not again`() =
        runTest {
            val vm = viewModel()
            vm.ask("How is Apple doing?")
            advanceUntilIdle()

            // A second createSurface for the same surface would be an error the renderer reports.
            repository.nextReply = listOf(appleAnswer[1])
            repository.send("answer-1", "{}")
            advanceUntilIdle()

            assertEquals(listOf("answer-1"), vm.surfaces.value.map { it.id })
            assertEquals(listOf("answer-1" to "{}"), repository.sent)
        }
}
