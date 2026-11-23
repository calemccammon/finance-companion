package com.calemccammon.financecompanion.catalog

import java.text.NumberFormat
import java.util.Locale
import kotlin.math.abs

/** How a figure is written. The agent chooses one; the figure itself comes from the data model. */
enum class FigureFormat(
    val wireName: String,
) {
    /** "1,234.56". */
    Number("number"),

    /** "$1,234.56". */
    Currency("currency"),

    /** "12.34%", for a figure already in percent. */
    Percent("percent"),

    /** "+1.23%" or "−1.23%", for a change already in percent. */
    Change("change"),
    ;

    fun format(
        value: Double,
        locale: Locale = Locale.getDefault(),
    ): String =
        when (this) {
            Number -> decimal(locale).format(value)
            Currency ->
                NumberFormat
                    .getCurrencyInstance(locale)
                    .apply {
                        currency =
                            java.util.Currency.getInstance("USD")
                    }.format(value)
            Percent -> decimal(locale).format(value) + "%"
            Change ->
                (
                    if (value > 0) {
                        "+"
                    } else if (value < 0) {
                        "−"
                    } else {
                        ""
                    }
                ) + decimal(locale).format(abs(value)) + "%"
        }

    companion object {
        val wireNames = entries.map { it.wireName }

        fun fromWire(name: String?): FigureFormat = entries.firstOrNull { it.wireName == name } ?: Number

        private fun decimal(locale: Locale) =
            NumberFormat.getNumberInstance(locale).apply {
                minimumFractionDigits = 2
                maximumFractionDigits = 2
            }
    }
}

/** Whether a change is up, down or flat; only [FigureFormat.Change] is coloured by it. */
internal fun Double.direction(): Int = compareTo(0.0)

/** A list of rows from the data model, each a JSON object; anything else is no rows. */
internal fun Any?.asRows(): List<Map<String, Any?>> =
    (this as? List<*>)
        ?.mapNotNull { row ->
            (row as? Map<*, *>)?.mapKeys { it.key.toString() }
        }.orEmpty()

internal fun Map<String, Any?>.number(key: String): Double? = (this[key] as? kotlin.Number)?.toDouble()

internal fun Map<String, Any?>.text(key: String): String? = this[key]?.toString()
