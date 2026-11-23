package com.calemccammon.financecompanion.catalog

import androidx.a2ui.compose.ui.A2uiCatalog
import androidx.compose.material3.a2ui.catalog.MaterialA2uiBasicCatalogV1Defaults

/**
 * The components the agent may use: layout and text from the A2UI Basic
 * Catalog, drawn in Material 3, and this app's own finance components.
 *
 * Media components (images, video, audio) are left out: the answers are
 * built from the warehouse's figures and have no use for them.
 */
object FinanceCatalog {
    /** Announced to the agent; the version is in the path so a breaking change gets a new id. */
    const val ID = "https://github.com/calemccammon/finance-companion/catalog/v1"

    fun create(): A2uiCatalog =
        A2uiCatalog(
            catalogId = ID,
            components =
                listOf(
                    MaterialA2uiBasicCatalogV1Defaults.text,
                    MaterialA2uiBasicCatalogV1Defaults.row,
                    MaterialA2uiBasicCatalogV1Defaults.column,
                    MaterialA2uiBasicCatalogV1Defaults.list,
                    MaterialA2uiBasicCatalogV1Defaults.card,
                    MaterialA2uiBasicCatalogV1Defaults.divider,
                    MaterialA2uiBasicCatalogV1Defaults.button,
                    MetricCard,
                ),
        )
}
