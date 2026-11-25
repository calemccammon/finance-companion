package com.calemccammon.financecompanion.core.data

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.calemccammon.financecompanion.core.data.database.ConversationDatabase
import com.calemccammon.financecompanion.core.data.network.AgentClient
import com.calemccammon.financecompanion.core.domain.AgentUnavailableException
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import okhttp3.OkHttpClient
import org.junit.After
import org.junit.Before
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.io.File
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

/**
 * The repository over a real database in memory and a local server replaying
 * what the agent sent, recorded by agent/scripts/record_streams.py.
 */
@RunWith(RobolectricTestRunner::class)
class OfflineFirstConversationRepositoryTest {
    private val server = MockWebServer()
    private val database =
        Room
            .inMemoryDatabaseBuilder(ApplicationProvider.getApplicationContext(), ConversationDatabase::class.java)
            .allowMainThreadQueries()
            .build()
    private val clock = Clock.fixed(Instant.parse("2026-11-23T12:00:00Z"), ZoneOffset.UTC)
    private lateinit var repository: OfflineFirstConversationRepository

    @Before
    fun start() {
        server.start()
        repository =
            OfflineFirstConversationRepository(
                database.conversationDao(),
                AgentClient(server.url("/").toString(), OkHttpClient()),
                clock,
            )
    }

    @After
    fun stop() {
        server.close()
        database.close()
    }

    private fun replay(name: String) = stream(File(System.getProperty("fc.catalog"), "fixtures/$name").readText())

    private fun stream(body: String) =
        server.enqueue(
            MockResponse
                .Builder()
                .addHeader("Content-Type", "text/event-stream")
                .body(body)
                .build(),
        )

    private fun event(json: String) = "data: $json\n\n"

    @Test
    fun `an answer is stored as it arrives, in order, with the surface it draws on`() =
        runTest {
            replay("apple-answer.sse")

            repository.ask("How is Apple doing?")

            val exchange = repository.exchanges.first().single()
            assertEquals("How is Apple doing?", exchange.question)
            assertEquals("answer-1", exchange.surfaceId)
            assertEquals(Instant.parse("2026-11-23T12:00:00Z"), exchange.askedAt)
            assertEquals(3, exchange.messages.size)
            assertTrue("createSurface" in exchange.messages[0])
            assertTrue("updateDataModel" in exchange.messages[1])
            assertTrue("updateComponents" in exchange.messages[2])

            val request = server.takeRequest()
            assertEquals("/ask", request.url.encodedPath)
            assertEquals("""{"text":"How is Apple doing?"}""", request.body?.utf8())
        }

    @Test
    fun `the comments the agent sends while it works are skipped`() =
        runTest {
            // While a model thinks, the agent sends ": working" so the read timeout does not fire.
            val recorded = File(System.getProperty("fc.catalog"), "fixtures/apple-answer.sse").readText()
            stream(": working\n\n" + recorded.replace("\n\ndata: ", "\n\n: working\n\n: working\n\ndata: "))

            repository.ask("How is Apple doing?")

            val exchange = repository.exchanges.first().single()
            assertEquals("answer-1", exchange.surfaceId)
            assertEquals(3, exchange.messages.size)
            assertTrue(exchange.messages.none { "working" in it })
        }

    @Test
    fun `a tap's answer is stored under the exchange that drew the surface`() =
        runTest {
            replay("apple-answer.sse")
            repository.ask("How is Apple doing?")
            replay("apple-one-month.sse")

            repository.send("answer-1", """{"version":"v0.9.1","action":{"name":"set_range"}}""")

            val exchange = repository.exchanges.first().single()
            assertEquals(4, exchange.messages.size)
            assertTrue(""""path": "/r1"""" in exchange.messages[3])
            server.takeRequest()
            assertEquals("/action", server.takeRequest().url.encodedPath)
        }

    @Test
    fun `a tap answered with a new question starts a new exchange`() =
        runTest {
            replay("apple-answer.sse")
            repository.ask("How is Apple doing?")
            stream(
                "event: question\ndata: \"How is TSLA doing?\"\n\n" +
                    event("""{"version":"v0.9.1","createSurface":{"surfaceId":"answer-2","catalogId":"c"}}"""),
            )

            repository.send("answer-1", "{}")

            val (first, second) = repository.exchanges.first()
            assertEquals(3, first.messages.size)
            assertEquals("How is TSLA doing?", second.question)
            assertEquals("answer-2", second.surfaceId)
            assertEquals(1, second.messages.size)
        }

    @Test
    fun `a question the agent cannot answer is not kept`() =
        runTest {
            server.enqueue(MockResponse.Builder().code(503).build())

            assertFailsWith<AgentUnavailableException> { repository.ask("How is Apple doing?") }

            assertEquals(emptyList(), repository.exchanges.first())
        }

    @Test
    fun `an agent that cannot be reached is reported as such`() =
        runTest {
            server.close()

            assertFailsWith<AgentUnavailableException> { repository.ask("How is Apple doing?") }
        }

    @Test
    fun `a message about a surface the device does not hold is not sent`() =
        runTest {
            repository.send("answer-9", "{}")

            assertEquals(0, server.requestCount)
        }
}
