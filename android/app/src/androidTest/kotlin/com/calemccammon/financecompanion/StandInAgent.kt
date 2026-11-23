package com.calemccammon.financecompanion

import androidx.test.platform.app.InstrumentationRegistry
import com.calemccammon.financecompanion.core.data.di.AgentConfig
import dagger.Module
import dagger.Provides
import dagger.hilt.components.SingletonComponent
import dagger.hilt.testing.TestInstallIn
import mockwebserver3.Dispatcher
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import mockwebserver3.RecordedRequest
import org.junit.rules.ExternalResource
import java.util.concurrent.CopyOnWriteArrayList

/**
 * A server on the device that answers as the agent did when its answers were
 * recorded (agent/scripts/record_streams.py). Everything from the HTTP client
 * inwards is the shipped app.
 */
class StandInAgent : ExternalResource() {
    private val server = MockWebServer()

    /** While true, every request fails as if the agent were down. */
    @Volatile
    var down = false

    /** The path and body of every request, in order. */
    val requests = CopyOnWriteArrayList<Pair<String, String>>()

    override fun before() {
        server.dispatcher =
            object : Dispatcher() {
                override fun dispatch(request: RecordedRequest): MockResponse {
                    requests += request.url.encodedPath to request.body?.utf8().orEmpty()
                    val recording = RECORDINGS[request.url.encodedPath]
                    return when {
                        down -> MockResponse.Builder().code(SERVICE_UNAVAILABLE).build()
                        recording == null -> MockResponse.Builder().code(NOT_FOUND).build()
                        else ->
                            MockResponse
                                .Builder()
                                .addHeader("Content-Type", "text/event-stream")
                                .body(read(recording))
                                .build()
                    }
                }
            }
        server.start()
        url = server.url("/").toString()
    }

    override fun after() = server.close()

    private fun read(name: String): String =
        InstrumentationRegistry
            .getInstrumentation()
            .context.assets
            .open(name)
            .bufferedReader()
            .use { it.readText() }

    companion object {
        /** The running server's address; the app is pointed at it by [StandInAgentModule]. */
        @Volatile
        var url: String = "http://localhost:1/"
            private set

        /** What the agent sent for each request, recorded. */
        private val RECORDINGS = mapOf("/ask" to "apple-answer.sse", "/action" to "apple-one-month.sse")
        private const val SERVICE_UNAVAILABLE = 503
        private const val NOT_FOUND = 404
    }
}

/** Points the app at [StandInAgent] in place of the real one. */
@Module
@TestInstallIn(components = [SingletonComponent::class], replaces = [AgentConfigModule::class])
object StandInAgentModule {
    @Provides
    fun agentConfig(): AgentConfig = AgentConfig(StandInAgent.url)
}
