package com.calemccammon.financecompanion.feature.conversation

import androidx.a2ui.model.processor.A2uiSurfaceModel
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material3.AssistChip
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.SnackbarResult
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.a2ui.A2uiSurface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.collections.immutable.ImmutableList
import kotlinx.collections.immutable.toImmutableList

/** The conversation screen wired to its view model. */
@Composable
fun ConversationRoute(viewModel: ConversationViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val surfaces by viewModel.surfaces.collectAsStateWithLifecycle()

    ConversationScreen(
        state = state,
        surfaces = surfaces.toImmutableList(),
        onAsk = viewModel::ask,
        onRetry = viewModel::retry,
        onDismiss = viewModel::dismiss,
    )
}

/**
 * Questions and the agent's answers, oldest at the top, with a box to ask
 * the next one. Each answer is an A2UI surface the agent composed.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConversationScreen(
    state: ConversationState,
    surfaces: ImmutableList<A2uiSurfaceModel>,
    onAsk: (String) -> Unit,
    onRetry: () -> Unit,
    onDismiss: () -> Unit,
) {
    val snackbars = remember { SnackbarHostState() }
    Unanswered(state.unanswered, snackbars, onRetry, onDismiss)

    Scaffold(
        topBar = { TopAppBar(title = { Text(stringResource(R.string.feature_conversation_title)) }) },
        snackbarHost = { SnackbarHost(snackbars) },
        bottomBar = { AskBar(state.asking, onAsk) },
    ) { padding ->
        if (state.exchanges.isEmpty() && !state.asking) {
            Suggestions(onAsk, Modifier.padding(padding))
        } else {
            Exchanges(state, surfaces, padding)
        }
    }
}

@Composable
private fun Exchanges(
    state: ConversationState,
    surfaces: ImmutableList<A2uiSurfaceModel>,
    padding: PaddingValues,
) {
    val list = rememberLazyListState()
    // The newest exchange, and its answer as it grows, stay in view.
    LaunchedEffect(state.exchanges.size, surfaces.size) {
        if (state.exchanges.isNotEmpty()) list.animateScrollToItem(state.exchanges.lastIndex)
    }
    LazyColumn(
        Modifier.fillMaxSize(),
        state = list,
        contentPadding = PaddingValues(16.dp).plus(padding),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        items(state.exchanges, key = { it.id }) { exchange ->
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Question(exchange.question)
                val surface = surfaces.firstOrNull { it.id == exchange.surfaceId }
                if (surface != null) A2uiSurface(surface, Modifier.fillMaxWidth())
            }
        }
        if (state.asking) {
            item(key = "answering") {
                val answering = stringResource(R.string.feature_conversation_answering)
                LinearProgressIndicator(Modifier.fillMaxWidth().semantics { contentDescription = answering })
            }
        }
    }
}

@Composable
private fun Question(text: String) {
    val spoken = stringResource(R.string.feature_conversation_you_asked, text)
    Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.CenterEnd) {
        Surface(
            color = MaterialTheme.colorScheme.secondaryContainer,
            shape = MaterialTheme.shapes.large,
            modifier = Modifier.semantics(mergeDescendants = true) { contentDescription = spoken },
        ) {
            Text(
                text,
                Modifier.padding(horizontal = 16.dp, vertical = 10.dp),
                style = MaterialTheme.typography.bodyLarge,
            )
        }
    }
}

@Composable
private fun Suggestions(
    onAsk: (String) -> Unit,
    modifier: Modifier,
) {
    val suggestions =
        listOf(
            stringResource(R.string.feature_conversation_suggestion_apple),
            stringResource(R.string.feature_conversation_suggestion_volatile),
            stringResource(R.string.feature_conversation_suggestion_tech),
            stringResource(R.string.feature_conversation_suggestion_rates),
        )
    Column(modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(stringResource(R.string.feature_conversation_intro), style = MaterialTheme.typography.bodyLarge)
        suggestions.forEach { AssistChip(onClick = { onAsk(it) }, label = { Text(it) }) }
    }
}

@Composable
private fun AskBar(
    asking: Boolean,
    onAsk: (String) -> Unit,
) {
    var text by rememberSaveable { mutableStateOf("") }
    val send = {
        if (text.isNotBlank() && !asking) {
            onAsk(text)
            text = ""
        }
    }
    Surface(tonalElevation = 3.dp) {
        Row(
            Modifier.fillMaxWidth().imePadding().padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            OutlinedTextField(
                value = text,
                onValueChange = { text = it },
                modifier = Modifier.weight(1f),
                placeholder = { Text(stringResource(R.string.feature_conversation_input_hint)) },
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                keyboardActions = KeyboardActions(onSend = { send() }),
            )
            FilledIconButton(onClick = send, enabled = text.isNotBlank() && !asking) {
                Icon(
                    Icons.AutoMirrored.Filled.Send,
                    contentDescription = stringResource(R.string.feature_conversation_send),
                )
            }
        }
    }
}

/** Offers to ask again a question the agent could not be reached for. */
@Composable
private fun Unanswered(
    question: String?,
    snackbars: SnackbarHostState,
    onRetry: () -> Unit,
    onDismiss: () -> Unit,
) {
    val message = stringResource(R.string.feature_conversation_unavailable)
    val action = stringResource(R.string.feature_conversation_try_again)
    val currentOnRetry by rememberUpdatedState(onRetry)
    val currentOnDismiss by rememberUpdatedState(onDismiss)
    LaunchedEffect(question) {
        if (question == null) return@LaunchedEffect
        val result = snackbars.showSnackbar(message, actionLabel = action, duration = SnackbarDuration.Long)
        if (result == SnackbarResult.ActionPerformed) currentOnRetry() else currentOnDismiss()
    }
}

private operator fun PaddingValues.plus(other: PaddingValues): PaddingValues =
    PaddingValues(
        start =
            calculateLeftPadding(androidx.compose.ui.unit.LayoutDirection.Ltr) +
                other.calculateLeftPadding(androidx.compose.ui.unit.LayoutDirection.Ltr),
        top = calculateTopPadding() + other.calculateTopPadding(),
        end =
            calculateRightPadding(androidx.compose.ui.unit.LayoutDirection.Ltr) +
                other.calculateRightPadding(androidx.compose.ui.unit.LayoutDirection.Ltr),
        bottom = calculateBottomPadding() + other.calculateBottomPadding(),
    )
