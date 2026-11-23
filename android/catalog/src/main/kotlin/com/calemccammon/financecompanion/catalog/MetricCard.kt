package com.calemccammon.financecompanion.catalog

import androidx.a2ui.compose.runtime.A2uiComponentProperties
import androidx.a2ui.compose.runtime.A2uiComponentScope
import androidx.a2ui.compose.runtime.A2uiProperty
import androidx.a2ui.compose.ui.A2uiComponent
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

/**
 * One figure with its label: "Close 182.31". The figure is bound to a path in
 * the data model, so it comes from the server's query, not from the model.
 */
object MetricCard : A2uiComponent {
    override val name = "MetricCard"

    override val description = "One figure with a short label, such as a closing price or a return."

    private val label = A2uiProperty.dynamicString("label", required = true, description = "What the figure is.")
    private val value = A2uiProperty.dynamicNumber("value", required = true, description = "The figure.")

    override val properties = listOf(label, value)

    @Composable
    override fun A2uiComponentScope.Content(
        properties: A2uiComponentProperties,
        modifier: Modifier,
    ) {
        Card(modifier) {
            Column(Modifier.padding(16.dp)) {
                Text(properties.bind(label).orEmpty(), style = MaterialTheme.typography.labelLarge)
                Text(properties.bind(value)?.toString().orEmpty(), style = MaterialTheme.typography.headlineMedium)
            }
        }
    }
}
