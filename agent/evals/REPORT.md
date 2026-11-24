# Evaluation results

Each model answered the same questions through the real agent, tools and checks. A score is the number of questions, out of the total, that met it.

| Model | Questions | renders | shows_data | first_try | catalog_only | bindings | no_written_figure | right_tools |
|---|---|---|---|---|---|---|---|---|
| openai:qwen3:8b | 50 | 0 | 0 | 0 | 50 | 50 | 50 | 47 |
| openai:qwen3:8b, layouts held to a schema | 50 | 44 | 43 | 28 | 50 | 50 | 49 | 47 |

## How far answers got

The catalog_only, bindings and no_written_figure scores count questions where no attempt broke that rule. The app's own checks (bindings, written figures, paths written into text, rows shown under another name) run only on an answer the A2UI SDK has accepted, so they say little when few answers got that far.

| Model | Attempts | Reached the app's own checks |
|---|---|---|
| openai:qwen3:8b | 100 | 0 |
| openai:qwen3:8b, layouts held to a schema | 71 | 66 |

## Why layouts were rejected

| Model | Class | Count |
|---|---|---|
| openai:qwen3:8b | not JSON | 33 |
| openai:qwen3:8b | components nested in children | 26 |
| openai:qwen3:8b | no layout | 13 |
| openai:qwen3:8b | broken component tree | 10 |
| openai:qwen3:8b | path written as plain text | 6 |
| openai:qwen3:8b | stray fields | 6 |
| openai:qwen3:8b | tool call in place of a layout | 6 |
| openai:qwen3:8b | other schema error | 1 |
| openai:qwen3:8b, layouts held to a schema | path written into text | 13 |
| openai:qwen3:8b, layouts held to a schema | row shown under another name | 11 |
| openai:qwen3:8b, layouts held to a schema | other schema error | 4 |
| openai:qwen3:8b, layouts held to a schema | broken component tree | 1 |
| openai:qwen3:8b, layouts held to a schema | written figure | 1 |
