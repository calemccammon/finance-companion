package com.calemccammon.financecompanion.catalog

import androidx.a2ui.compose.ui.toJsonSchemaString
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals

/**
 * The catalog as the agent must see it. The schema the app's components
 * declare is committed at `catalog/finance-catalog.json`, where the agent
 * reads it; this fails if the two have drifted apart.
 *
 * Run with `-Dfc.updateCatalog=true` to write the file after changing a component.
 */
@RunWith(RobolectricTestRunner::class)
class CatalogSchemaTest {
    private val committed = File(System.getProperty("fc.catalog"), "finance-catalog.json")

    @Test
    fun `the committed catalog matches the components`() {
        val schema = FinanceCatalog.create().toJsonSchemaString()
        if (System.getProperty("fc.updateCatalog") == "true") {
            committed.parentFile?.mkdirs()
            committed.writeText(schema + "\n")
        }
        assertEquals(committed.readText().trim(), schema.trim(), "Run with -Dfc.updateCatalog=true to update it")
    }
}
