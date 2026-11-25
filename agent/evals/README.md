# Evaluation

`run.py` puts the 50 questions in `questions.json` to the real agent, tools
and checks, with whatever model `FC_MODEL` names, and scores each answer:

- **renders**: the final layout passed every check, so the app drew it rather
  than the fallback message;
- **shows_data**: it rendered, and showed a figure, chart or ranking when the
  question needed data;
- **first_try**: the first layout passed, with no correction;
- **right_tools**: the model called the tools the question needs;
- **catalog_only**, **bindings**, **no_written_figure**: no attempt used a
  component the app lacks, bound to a missing path, or typed a figure.

Each answer's tools, rejected layouts with their reasons, and accepted layout
are saved, so a score can be checked against the screen it counts.

```sh
uv run python evals/run.py --out evals/results/qwen3-8b-schema.json
uv run python evals/run.py --no-schema --out evals/results/qwen3-8b.json
uv run python evals/run.py --report evals/results/*.json > evals/REPORT.md
```

All runs below used qwen3:8b on Ollama 0.40.17 (16K context, 8-bit context
cache) on an 8 GB RTX 4060 laptop GPU: a little over an hour for 50
questions. The latest scores are in [`REPORT.md`](REPORT.md).

## How the layout rules came about

Each step came from reading a run: its rejected layouts, and later its
accepted ones.

| Step | Screens that passed |
|---|---|
| The model writes the layout freely | 1 of 50 (4 in the latest run) |
| Held to a JSON Schema of the catalog | 35 |
| Bindings limited to paths in the fetched data | 48 |
| Checks for paths written into text, and for unnamed rows | 44 |
| A check that each figure is drawn in its format | 34 |
| Formats fixed in the schema instead | 39 |
| Labels and captions fixed in the schema | 43 |

**Writing A2UI freely.** The model called the right tools for 47 of 50
questions, but its layouts were mostly JSON that did not parse, components
written inside `children` instead of by id, or plain text.

**A schema of the catalog** made those faults impossible. Ollama enforces a
JSON Schema through `response_format`, but not while tools are offered, so the
model gathers its data first and is then asked for the layout. The commonest
rejection became a binding to a path that did not exist (24 times), such as
`/r1/latest/unemployment_rate`.

**Paths from the data.** When the layout is asked for, the data is already
there, so the schema lists the paths it holds, by kind: lists for charts and
rankings, numbers for figures, strings for text.

**Reading what passed.** Some accepted screens were wrong. One showed
"Apple's last close was $/r1/latest/close". Others labelled a card "AAPL"
while showing the first row of a ranking, which is sorted by return, so the
row was another stock. Both are now rejected.

**Formats.** Four accepted cards drew a closing price as a percent change, so
$300 would read "+300%". A check alone sent 17 layouts back, and the model
often kept the wrong format when told. Tying each figure to its format in the
schema made a wrong one impossible, with no rejections for it.

**Labels.** Recording the README's demo with the real model found a mislabel
in each of five takes of "How is Apple doing?": "52-Week Volatility" over a
20-day figure, "1-Month Change" over a 90-day change, the range's first day
as the date under the latest close. Telling the model what each field means
did not stop it. Now a figure card comes with its label and date fixed: the
model chooses which figures to show and how to lay them out, not what to call
them. In the run after, all 51 cards in the accepted screens carried their
figure's own label, format and date.

## How much runs differ

The same code and questions give different scores from run to run. Between
the 44 and 39 runs above, eight questions went from passing to failing and
three the other way, none of them over formats. Differences of about five
are within what one run each can show.

## What still goes wrong

In the latest run, seven answers fell back to the plain message:

- The model sometimes writes a path, such as `"/r1/market_cap_category"`, as
  text where it meant to bind it, and repeats it when told.
- Some layouts are malformed in ways the schema cannot rule out: a button
  that is not reachable from the root, or a component that contains itself.
- An answer takes about a minute, and now and then more than the five-minute
  limit.
- The prompt asks for range buttons under every chart; the schema does not
  require them.
