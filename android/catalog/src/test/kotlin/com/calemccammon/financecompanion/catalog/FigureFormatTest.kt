package com.calemccammon.financecompanion.catalog

import java.util.Locale
import kotlin.test.Test
import kotlin.test.assertEquals

class FigureFormatTest {
    private val us = Locale.US

    @Test
    fun `each format writes a figure its own way`() {
        assertEquals("1,234.50", FigureFormat.Number.format(1234.5, us))
        assertEquals("$1,234.50", FigureFormat.Currency.format(1234.5, us))
        assertEquals("27.98%", FigureFormat.Percent.format(27.978, us))
        assertEquals("+1.20%", FigureFormat.Change.format(1.2, us))
        assertEquals("−1.20%", FigureFormat.Change.format(-1.2, us))
        assertEquals("0.00%", FigureFormat.Change.format(0.0, us))
    }

    @Test
    fun `figures follow the device's locale`() {
        assertEquals("1.234,50", FigureFormat.Number.format(1234.5, Locale.GERMANY))
    }

    @Test
    fun `an unknown or missing format name means a plain number`() {
        assertEquals(FigureFormat.Number, FigureFormat.fromWire("sparkly"))
        assertEquals(FigureFormat.Number, FigureFormat.fromWire(null))
        assertEquals(FigureFormat.Currency, FigureFormat.fromWire("currency"))
    }
}
