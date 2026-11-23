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
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.unit.dp
import kotlinx.collections.immutable.ImmutableList
import kotlinx.collections.immutable.persistentListOf

/**
 * One figure with its label: "Close $182.31". The figure is bound to a path in
 * the data model, so it comes from the server's query, not from the model.
 */
object MetricCard : A2uiComponent {
    override val name = "MetricCard"

    override val description =
        "One figure with a short label, such as a closing price or a return. " +
            "Bind `value` to a number in the data model; never write a figure yourself."

    private val label = A2uiProperty.dynamicString("label", required = true, description = "What the figure is.")
    private val value =
        A2uiProperty.dynamicNumber("value", required = true, description = "The figure: a path in the data model.")
    private val format =
        A2uiProperty.stringEnum(
            "format",
            FigureFormat.wireNames,
            description =
                "How to write the figure: number, currency (US dollars), percent (a figure already in percent) " +
                    "or change (a change in percent, shown with its sign and coloured). Defaults to number.",
        )
    private val caption =
        A2uiProperty.dynamicString("caption", description = "A short note under the figure, such as a date.")

    override val properties: ImmutableList<A2uiProperty<*>> = persistentListOf(label, value, format, caption)

    @Composable
    override fun A2uiComponentScope.Content(
        properties: A2uiComponentProperties,
        modifier: Modifier,
    ) {
        val label = properties.bind(label).orEmpty()
        val figure = properties.bind(value)?.toDouble()
        val format = FigureFormat.fromWire(properties[format])
        val written = figure?.let { format.format(it) }.orEmpty()
        val caption = properties.bind(caption)
        val colour =
            when {
                format != FigureFormat.Change || figure == null -> MaterialTheme.colorScheme.onSurface
                figure.direction() > 0 -> Gains.up()
                figure.direction() < 0 -> MaterialTheme.colorScheme.error
                else -> MaterialTheme.colorScheme.onSurface
            }

        Card(
            modifier.clearAndSetSemantics {
                contentDescription =
                    listOfNotNull(label, written, caption).joinToString(", ")
            },
        ) {
            Column(Modifier.padding(16.dp)) {
                Text(
                    label,
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(written, style = MaterialTheme.typography.headlineMedium, color = colour)
                caption?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            }
        }
    }
}
