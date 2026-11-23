package com.calemccammon.financecompanion.catalog

import androidx.compose.foundation.clickable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role

/** A whole row that can be pressed, announced as a button. */
internal fun Modifier.clickableRow(onClick: () -> Unit): Modifier = clickable(role = Role.Button, onClick = onClick)
