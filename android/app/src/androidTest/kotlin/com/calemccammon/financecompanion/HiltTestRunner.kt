package com.calemccammon.financecompanion

import android.app.Application
import android.content.Context
import androidx.test.runner.AndroidJUnitRunner
import dagger.hilt.android.testing.HiltTestApplication

/** Runs the device tests with Hilt's test application, which lets a test swap parts of the graph. */
class HiltTestRunner : AndroidJUnitRunner() {
    override fun newApplication(
        loader: ClassLoader,
        className: String,
        context: Context,
    ): Application = super.newApplication(loader, HiltTestApplication::class.java.name, context)
}
