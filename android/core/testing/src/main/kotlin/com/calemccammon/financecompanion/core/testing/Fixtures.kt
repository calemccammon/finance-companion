package com.calemccammon.financecompanion.core.testing

import java.io.File

/** Files in the repository's `catalog/fixtures`, which the agent's tests check too. */
object Fixtures {
    fun file(name: String): File = File(System.getProperty("fc.catalog"), "fixtures/$name")

    fun text(name: String): String = file(name).readText()

    /** The A2UI messages of a recorded answer stream, as a repository stores them. */
    fun messages(name: String): List<String> =
        text(name).split("\n\n").filter { it.startsWith("data: ") }.map { it.removePrefix("data: ") }
}
