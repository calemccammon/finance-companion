# Evaluation results

Each model answered the same questions through the real agent, tools and checks. A score is the number of questions, out of the total, that met it.

| Model | Questions | renders | shows_data | first_try | catalog_only | bindings | no_written_figure | right_tools |
|---|---|---|---|---|---|---|---|---|
| openai:qwen3:8b | 50 | 4 | 4 | 1 | 50 | 50 | 50 | 47 |
| openai:qwen3:8b, layouts held to a schema | 50 | 43 | 41 | 33 | 50 | 50 | 48 | 48 |

## How far answers got

The catalog_only, bindings and no_written_figure scores count questions where no attempt broke that rule. The app's own checks (bindings, written figures, paths written into text, rows shown under another name, formats) run only on an answer the A2UI SDK has accepted, so they say little when few answers got that far.

| Model | Attempts | Reached the app's own checks |
|---|---|---|
| openai:qwen3:8b | 99 | 4 |
| openai:qwen3:8b, layouts held to a schema | 65 | 53 |

## Why layouts were rejected

| Model | Class | Count |
|---|---|---|
| openai:qwen3:8b | not JSON | 37 |
| openai:qwen3:8b | broken component tree | 16 |
| openai:qwen3:8b | components nested in children | 13 |
| openai:qwen3:8b | no layout | 12 |
| openai:qwen3:8b | stray fields | 7 |
| openai:qwen3:8b | path written as plain text | 4 |
| openai:qwen3:8b | tool call in place of a layout | 4 |
| openai:qwen3:8b | other schema error | 2 |
| openai:qwen3:8b, layouts held to a schema | path written into text | 8 |
| openai:qwen3:8b, layouts held to a schema | other schema error | 7 |
| openai:qwen3:8b, layouts held to a schema | broken component tree | 5 |
| openai:qwen3:8b, layouts held to a schema | written figure | 2 |
