# Evaluation results

Each model answered the same questions through the real agent, tools and checks. A score is the number of questions, out of the total, that met it.

| Model | Questions | renders | first_try | catalog_only | bindings | no_written_figure | right_tools |
|---|---|---|---|---|---|---|---|
| openai:qwen3:8b | 50 | 1 | 0 | 49 | 50 | 50 | 47 |

## How far answers got

The catalog_only, bindings and no_written_figure scores count questions where no attempt broke that rule. The app's checks for bindings and written figures run only on an answer the A2UI SDK has accepted, so they say little when few answers got that far.

| Model | Attempts | Reached the app's own checks |
|---|---|---|
| openai:qwen3:8b | 100 | 1 |

## Why layouts were rejected

| Model | Class | Count |
|---|---|---|
| openai:qwen3:8b | not JSON | 29 |
| openai:qwen3:8b | components nested in children | 28 |
| openai:qwen3:8b | broken component tree | 16 |
| openai:qwen3:8b | no layout | 12 |
| openai:qwen3:8b | path written as plain text | 10 |
| openai:qwen3:8b | stray fields | 5 |
| openai:qwen3:8b | tool call in place of a layout | 3 |
| openai:qwen3:8b | unknown component | 1 |
| openai:qwen3:8b | other schema error | 1 |
