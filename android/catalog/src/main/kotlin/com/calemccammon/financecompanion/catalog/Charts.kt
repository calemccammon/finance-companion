package com.calemccammon.financecompanion.catalog

import androidx.a2ui.compose.runtime.A2uiComponentProperties
import androidx.a2ui.compose.runtime.A2uiComponentScope
import androidx.a2ui.compose.runtime.A2uiProperty
import androidx.a2ui.compose.ui.A2uiComponent
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import kotlinx.collections.immutable.ImmutableList
import kotlinx.collections.immutable.persistentListOf

/** A line to draw: values in order, already scaled to the chart's own range by [Canvas]. */
private class Line(
    val values: List<Double?>,
    val colour: Color,
    val dashed: Boolean = false,
)

/** Draws [lines] across the canvas, each within [low]..[high]. A null value breaks a line. */
private fun DrawScope.drawLines(
    lines: List<Line>,
    low: Double,
    high: Double,
) {
    val span = (high - low).takeIf { it > 0 } ?: 1.0
    for (line in lines) {
        val count = line.values.size
        if (count < 2) continue
        val path = Path()
        var drawing = false
        line.values.forEachIndexed { i, v ->
            if (v == null) {
                drawing = false
                return@forEachIndexed
            }
            val point = Offset(size.width * i / (count - 1), size.height * (1 - ((v - low) / span)).toFloat())
            if (drawing) path.lineTo(point.x, point.y) else path.moveTo(point.x, point.y)
            drawing = true
        }
        drawPath(
            path,
            line.colour,
            style =
                Stroke(
                    width = 2.dp.toPx(),
                    pathEffect = if (line.dashed) PathEffect.dashPathEffect(floatArrayOf(DASH, DASH)) else null,
                ),
        )
    }
}

@Composable
private fun Legend(entries: List<Pair<String, Color>>) {
    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        entries.forEach { (label, colour) ->
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(8.dp).background(colour, CircleShape))
                Text(" $label", style = MaterialTheme.typography.labelSmall)
            }
        }
    }
}

/**
 * A card holding a chart. With a [description], the whole card is read out as
 * that one sentence; without, its title and rows are read one by one.
 */
@Composable
private fun ChartCard(
    title: String?,
    description: String?,
    modifier: Modifier,
    content: @Composable () -> Unit,
) {
    val reading =
        if (description ==
            null
        ) {
            Modifier
        } else {
            Modifier.clearAndSetSemantics { contentDescription = description }
        }
    Card(modifier.fillMaxWidth().then(reading)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            title?.let { Text(it, Modifier.semantics { heading() }, style = MaterialTheme.typography.titleMedium) }
            content()
        }
    }
}

/** The first and last dates under a chart, and, if given, the lowest and highest close between them. */
@Composable
private fun AxisNotes(
    first: String?,
    last: String?,
    lowest: String? = null,
    highest: String? = null,
) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(first.orEmpty(), style = MaterialTheme.typography.labelSmall)
        Text(last.orEmpty(), style = MaterialTheme.typography.labelSmall)
    }
    if (lowest != null && highest != null) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("Lowest close $lowest", style = MaterialTheme.typography.labelSmall)
            Text("Highest close $highest", style = MaterialTheme.typography.labelSmall)
        }
    }
}

/**
 * A stock's daily closes as a line, with its 30- and 90-day moving averages
 * dashed beside it. Bind `points` to the `points` of a `price_history` result.
 */
object PriceChart : A2uiComponent {
    override val name = "PriceChart"

    override val description =
        "A line chart of one stock's daily closes. Bind `points` to the `points` list of a price_history result."

    private val title = A2uiProperty.dynamicString("title", description = "A heading for the chart.")
    private val points =
        A2uiProperty.dynamicValue(
            "points",
            required = true,
            description = "A path to a list of {date, close, sma30, sma90} rows, oldest first.",
        )
    private val showAverages =
        A2uiProperty.booleanWithDefault(
            "showAverages",
            defaultValue = true,
            description = "Whether to draw the 30- and 90-day moving averages.",
        )

    override val properties: ImmutableList<A2uiProperty<*>> = persistentListOf(title, points, showAverages)

    @Composable
    override fun A2uiComponentScope.Content(
        properties: A2uiComponentProperties,
        modifier: Modifier,
    ) {
        val rows = properties.bind(points).asRows()
        val closes = rows.map { it.number("close") }
        val averages = properties[showAverages] ?: true
        val price = MaterialTheme.colorScheme.primary
        val lines =
            buildList {
                add(Line(closes, price))
                if (averages) {
                    add(Line(rows.map { it.number("sma30") }, Charts.average30, dashed = true))
                    add(Line(rows.map { it.number("sma90") }, Charts.average90, dashed = true))
                }
            }
        val drawn = lines.flatMap { it.values }.filterNotNull()
        val low = drawn.minOrNull() ?: 0.0
        val high = drawn.maxOrNull() ?: 0.0
        val money = FigureFormat.Currency
        val first = rows.firstOrNull()?.text("date")
        val last = rows.lastOrNull()?.text("date")
        val title = properties.bind(title)
        val description =
            listOfNotNull(
                title ?: "Price chart",
                "closes from $first to $last",
                closes.firstOrNull { it != null }?.let { "starting at ${money.format(it)}" },
                closes.lastOrNull { it != null }?.let { "ending at ${money.format(it)}" },
            ).joinToString(", ")

        ChartCard(title, description, modifier) {
            Canvas(Modifier.fillMaxWidth().height(160.dp)) { drawLines(lines, low, high) }
            // The chart is scaled to every line drawn; the notes are about the closes alone.
            val shown = closes.filterNotNull()
            AxisNotes(first, last, shown.minOrNull()?.let(money::format), shown.maxOrNull()?.let(money::format))
            if (averages) {
                Legend(
                    listOf(
                        "Close" to price,
                        "30-day average" to Charts.average30,
                        "90-day average" to Charts.average90,
                    ),
                )
            }
        }
    }
}

/**
 * A stock's closes beside an economic series over the same days, each line
 * on its own scale. Bind `points` to the `points` of a `macro_overlay` result.
 */
object OverlayChart : A2uiComponent {
    override val name = "OverlayChart"

    override val description =
        "A stock's closes and an economic series on one chart, each on its own scale. " +
            "Bind `points` to the `points` list of a macro_overlay result."

    private val title = A2uiProperty.dynamicString("title", description = "A heading for the chart.")
    private val points =
        A2uiProperty.dynamicValue(
            "points",
            required = true,
            description = "A path to a list of {date, close, series} rows.",
        )
    private val priceLabel =
        A2uiProperty.dynamicString(
            "priceLabel",
            required = true,
            description = "What the price line is, such as the ticker.",
        )
    private val seriesLabel =
        A2uiProperty.dynamicString(
            "seriesLabel",
            required = true,
            description = "What the economic series is; bind it to `seriesName`.",
        )

    override val properties: ImmutableList<A2uiProperty<*>> = persistentListOf(title, points, priceLabel, seriesLabel)

    @Composable
    override fun A2uiComponentScope.Content(
        properties: A2uiComponentProperties,
        modifier: Modifier,
    ) {
        val rows = properties.bind(points).asRows()
        val price = rows.map { it.number("close") }
        val series = rows.map { it.number("series") }
        val priceLabel = properties.bind(priceLabel).orEmpty()
        val seriesLabel = properties.bind(seriesLabel).orEmpty()
        val priceColour = MaterialTheme.colorScheme.primary
        val title = properties.bind(title)
        val first = rows.firstOrNull()?.text("date")
        val last = rows.lastOrNull()?.text("date")

        ChartCard(
            title,
            listOfNotNull(title, "$priceLabel and $seriesLabel from $first to $last").joinToString(", "),
            modifier,
        ) {
            Canvas(Modifier.fillMaxWidth().height(160.dp)) {
                // Two scales: each line fills the chart's height on its own.
                drawLines(
                    listOf(Line(price, priceColour)),
                    price.filterNotNull().minOrNull() ?: 0.0,
                    price.filterNotNull().maxOrNull() ?: 0.0,
                )
                drawLines(
                    listOf(Line(series, Charts.series)),
                    series.filterNotNull().minOrNull() ?: 0.0,
                    series.filterNotNull().maxOrNull() ?: 0.0,
                )
            }
            AxisNotes(first, last)
            Legend(listOf(priceLabel to priceColour, seriesLabel to Charts.series))
        }
    }
}

/**
 * Rows ranked by one figure, each with a bar for its size: returns, or
 * volatility. Bind `rows` to the `rows` of a `compare_returns` or
 * `volatility_rank` result. A row can be pressed to ask about its ticker.
 */
object RankedBars : A2uiComponent {
    override val name = "RankedBars"

    override val description =
        "Rows ranked by one figure, each with a bar: for compare_returns or volatility_rank results. " +
            "Pressing a row sends the action named in `rowAction` with the row's ticker."

    private val title = A2uiProperty.dynamicString("title", description = "A heading for the list.")
    private val rows = A2uiProperty.dynamicValue("rows", required = true, description = "A path to a list of rows.")
    private val valueKey =
        A2uiProperty.string(
            "valueKey",
            required = true,
            description = "The field of each row to rank by, such as returnPct or volatility.",
        )
    private val format =
        A2uiProperty.stringEnum(
            "format",
            FigureFormat.wireNames,
            description = "How to write each figure. Defaults to number.",
        )
    private val rowAction =
        A2uiProperty.string(
            "rowAction",
            description = "If set, the name of the action sent when a row is pressed, with the row's ticker.",
        )

    override val properties: ImmutableList<A2uiProperty<*>> = persistentListOf(title, rows, valueKey, format, rowAction)

    @Composable
    override fun A2uiComponentScope.Content(
        properties: A2uiComponentProperties,
        modifier: Modifier,
    ) {
        val rows = properties.bind(rows).asRows()
        val key = properties[valueKey].orEmpty()
        val format = FigureFormat.fromWire(properties[format])
        val action = properties[rowAction]
        val values = rows.map { it.number(key) ?: 0.0 }
        val largest = values.maxOfOrNull { kotlin.math.abs(it) }?.takeIf { it > 0 } ?: 1.0
        val title = properties.bind(title)

        // Each row is read, and pressed, on its own.
        ChartCard(title, description = null, modifier) {
            rows.forEachIndexed { i, row ->
                val ticker = row.text("ticker").orEmpty()
                val value = values[i]
                val colour =
                    if (format == FigureFormat.Change &&
                        value < 0
                    ) {
                        MaterialTheme.colorScheme.error
                    } else {
                        MaterialTheme.colorScheme.primary
                    }
                val written = format.format(value)
                val press =
                    if (action == null) {
                        Modifier
                    } else {
                        Modifier.clickableRow {
                            dispatchAction(
                                mapOf(
                                    "event" to mapOf("name" to action, "context" to mapOf("ticker" to ticker)),
                                ),
                            )
                        }
                    }
                Row(
                    // The press goes first: the semantics set after it replace only what is inside.
                    press
                        .fillMaxWidth()
                        .clearAndSetSemantics { contentDescription = "$ticker, $written" }
                        .padding(vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(ticker, Modifier.weight(0.22f), style = MaterialTheme.typography.labelLarge)
                    Box(Modifier.weight(0.5f).height(10.dp)) {
                        Box(
                            Modifier
                                .fillMaxWidth((kotlin.math.abs(value) / largest).toFloat().coerceIn(0.02f, 1f))
                                .height(10.dp)
                                .background(colour, MaterialTheme.shapes.extraSmall),
                        )
                    }
                    Text(
                        format.format(value),
                        Modifier.weight(0.28f).padding(start = 8.dp),
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            }
        }
    }
}

/** Length of each dash, and of each gap, in a dashed line, in pixels. */
private const val DASH = 8f

internal object Charts {
    val average30 = Color(0xFFB26A00)
    val average90 = Color(0xFF6D5677)
    val series = Color(0xFF00897B)
}

internal object Gains {
    /** Green for a rise, light on a dark theme and dark on a light one, so it reads on either. */
    @Composable
    fun up(): Color = if (MaterialTheme.colorScheme.surface.luminance() < HALF) onDark else onLight

    private val onLight = Color(0xFF1E7B34)
    private val onDark = Color(0xFF7DD88C)
    private const val HALF = 0.5f
}
