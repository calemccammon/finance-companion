# finance-companion

An Android app where you ask about stocks and the US economy, and an AI agent
answers with a native screen: figures, charts and rankings drawn in Jetpack
Compose. The agent composes the screen with the
[A2UI](https://a2ui.org/) protocol and the app draws it with the A2UI Compose
renderer. The model decides what to show and how to lay it out; it never
writes SQL and never produces a number. Every figure on screen comes from a
fixed query against the dbt marts of
[data-engineer-finance-analytics](https://github.com/calemccammon/data-engineer-finance-analytics).

| Asking and changing the range                   | A ranking, pressed to ask about one stock              |
| ----------------------------------------------- | ------------------------------------------------------ |
| ![An answer about Apple](docs/screenshot-answer.png) | ![Stocks ranked by volatility](docs/screenshot-ranking.png) |

![A session: asking about Apple, switching the chart to one month, ranking the stocks by volatility, and pressing Tesla](docs/demo.gif)

The screenshots and the recording come from the real agent, tools and app on an
emulator. The model's turns came from a script (`agent/demo/script.json`), so
that they show the same thing each time; a local 8B model now writes a screen
the checks accept for 39 of 50 test questions (see
[Evaluations](#evaluations)).

## How an answer is made

```
 app ──POST /ask──▶ agent ──▶ model: "price_history(AAPL)"
                     │        agent runs fixed SQL on the dbt marts,
                     │        stores the rows at /r1 in the surface's data model
                     │  ──▶   model, asked again for the layout, held to a
                     │        JSON Schema of the catalog and the paths in /r1
                     │  ◀──── model: one updateComponents message, figures
                     │        bound to paths such as /r1/latest/close
                     │        agent checks it (below); a rejected layout goes
                     │        back to the model once with the reasons
 app ◀─SSE── createSurface, updateDataModel (the rows), updateComponents
 app stores each message in Room, then draws it with the A2UI renderer
```

- **The model chooses, the warehouse answers.** Six tools wrap parameterised
  queries on `fct_daily_trading`, `dim_company` and `dim_date`:
  `price_history`, `compare_returns`, `volatility_rank`, `macro_overlay`,
  `macro_snapshot` and `company_profile`. Their arguments are typed, unknown
  fields are refused, and the warehouse is opened read-only.
- **The model never handles the data, only where it is.** It is told that a
  result is at `/r1` and what it holds, and binds its components to those
  paths. The server sends the data itself.
- **The layout is written under a JSON Schema.** Once the model has its
  data, it is asked for the layout with no tools and a schema built from the
  catalog and that data (`agent/finance_agent/layout_schema.py`): one
  `updateComponents` message, components referred to by id, no fields a
  component lacks, and every binding one of the paths the data holds, of the
  right kind (a list for a chart or a ranking, a number for a figure, a
  string for text), with a card's format tied to its figure (a price only as
  currency). With no data, only words can be laid out. Ollama's
  OpenAI-compatible endpoint enforces it with `response_format`.
- **Every layout is checked before it is sent.** First the A2UI SDK's
  validation against the app's catalog: unknown components, properties,
  types, malformed JSON. Then rules the SDK cannot know: every binding must
  resolve in the data model (inside a `List` template, against an item); a
  chart's points and a ranking's rows must be bound to a list; no figure may
  be written by the model, neither as a literal number in a data property nor
  as a money, percent or decimal figure from the data in text; no path may be
  written into text, where it would be shown as it is; a card showing one
  row of a ranking must name that row, since rankings are sorted by their
  figure; and a figure must be drawn in its format, a price as currency and
  a change as a signed percent.
- **Taps go back to the agent as A2UI actions.** A range button reruns its
  result's tool and rewrites only that part of the data model, with no model
  call. Pressing a stock in a ranking asks about it as a new question. An
  error reported by the renderer goes to the model for one correction.

## The catalog

The app's components are the only ones the agent may use. They are declared
in Kotlin, the renderer writes them out as JSON Schema, and a test keeps
`catalog/finance-catalog.json` in step with them; the agent loads that file.

| Component      | What it draws                                                             |
| -------------- | ------------------------------------------------------------------------- |
| `MetricCard`   | One bound figure with a label, as a number, dollars, percent or a signed change |
| `PriceChart`   | A stock's daily closes with its 30- and 90-day averages                   |
| `OverlayChart` | A stock's closes beside an economic series, each on its own scale        |
| `RankedBars`   | Rows ranked by one figure; each row can be pressed to ask about its stock |

Layout, text and buttons come from the A2UI Basic Catalog in Material 3.
Each component is read by a screen reader as a sentence, and each ranked row
is its own button at least 48 dp tall.

## The app

The app is built like
[android-weather](https://github.com/calemccammon/android-weather): Gradle
modules with convention plugins, Hilt, and Room as the one source of truth.
Every A2UI message is stored as it arrives and the screen is drawn from what
is stored, each message fed to the renderer once, in order. So an answer
streams onto the screen, a range change on an old answer is kept, and the
conversation comes back after a restart whether or not the agent is running.
A question the agent cannot take is not kept, and is offered again.

| Module                 | What it holds                                                        |
| ---------------------- | -------------------------------------------------------------------- |
| `catalog`              | The finance components, the catalog and the theme                    |
| `core:domain`          | The conversation repository interface                                |
| `core:data`            | Room, the Server-Sent Events client and the repository               |
| `core:testing`         | A stand-in repository and the shared fixtures                        |
| `feature:conversation` | The screen and its view model                                        |
| `app`                  | The activity and the Hilt wiring                                     |

## Running it

The agent needs Python 3.12 and [uv](https://docs.astral.sh/uv/); the app,
Java 21 and the Android SDK.

```sh
cd agent
uv sync
# The demo script, in order: "How is Apple doing?", "Which stocks are most volatile?", a press on TSLA.
FC_MODEL=scripted:demo/script.json uv run uvicorn finance_agent.server:app --port 8000
# A real model: qwen3:8b on a local Ollama by default, or any OpenAI-compatible endpoint.
uv run uvicorn finance_agent.server:app --port 8000
FC_MODEL="openai:http://localhost:8080/v1|some-model" uv run uvicorn finance_agent.server:app --port 8000

cd ../android
./gradlew :app:installDebug   # the emulator reaches the agent at 10.0.2.2:8000
```

For the default model, run [Ollama](https://ollama.com/) with a context
long enough for the agent's rules and catalog (about 6,000 tokens). Its
default is shorter and cuts the prompt without an error:

```sh
OLLAMA_CONTEXT_LENGTH=16384 OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 ollama serve
ollama pull qwen3:8b
```

The agent reads the warehouse from `FC_WAREHOUSE`, or else from the fixture in
`agent/tests/fixtures/warehouse.duckdb`: the last 130 trading days of the
marts (19 May to 20 November 2026), built by
`agent/scripts/build_fixture.py` from a real run of the pipeline.

## Tests

```sh
cd agent && uv run ruff check . && uv run pytest
cd android && ./gradlew ktlintCheck detekt lint checkComposeStability -PcomposeReports
cd android && ./gradlew test testDebugUnitTest verifyRoborazziDebug
cd android && ./gradlew :app:connectedDebugAndroidTest   # on an emulator or device
```

- **The agent (135 tests)**: the tools against values worked out from the raw
  rows; the checks and the layout schema, each with the mistakes a local model made;
  the question-to-surface loop, corrections, fallbacks and
  actions with a scripted model; the model clients' message formats; the HTTP
  service; and the evaluation harness.
- **The app on the JVM (33 tests)**: the components drawn by the renderer from
  a surface the agent's tests also validate; Room and the repository against a
  local server replaying recorded agent answers; the view model; the screen,
  including a tap reaching the agent; and screenshots, light and dark.
- **The app on a device (2 tests)**: the whole app against a stand-in agent,
  through a range change, a restart and an outage.

The two halves are checked against the same files in `catalog/`: the
catalog, a surface both sides validate, an action message both sides read,
and answer streams recorded from the real agent
(`agent/scripts/record_streams.py`), which an agent test fails on if they
drift.

CI runs all of it on every pull request, the device tests on an emulator.

## Evaluations

`agent/evals/run.py` puts 50 questions to the agent with a given model and
scores each one: whether the layout rendered, whether it passed first time,
whether it kept to the catalog, bound only to real data and wrote no figure,
and whether the right tools were called. The questions cover single stocks,
comparisons, rankings, the economy, questions needing two tools, off-topic
ones and adversarial ones (a figure asked for in plain text, a ticker the
warehouse lacks, a forecast, raw SQL).

```sh
uv run python evals/run.py --out evals/results/qwen3-8b.json
uv run python evals/run.py --report evals/results/*.json > evals/REPORT.md
```

### qwen3:8b on a laptop

[`agent/evals/REPORT.md`](agent/evals/REPORT.md) holds the scores of two runs
of the same code with qwen3:8b on Ollama 0.40.17 (16K context, 8-bit context
cache) on an 8 GB RTX 4060 laptop GPU, each a little over an hour for the 50
questions: one with the layout held to the schema, one without
(`--no-schema`). Every answer's tools, rejections with their reasons, and
accepted layout are kept in [`agent/evals/results/`](agent/evals/results/).

| | Without the schema | With the schema |
|---|---|---|
| Screens that passed every check | 2 / 50 | 39 / 50 |
| ...and showed data where the question needed it | 2 | 38 |
| ...the first time, with no correction | 0 | 30 |
| Right tools called | 47 | 46 |
| Attempts that reached the app's own checks | 2 of 100 | 60 of 67 |

- **Without the schema, the model rarely writes A2UI.** Its rejections were
  JSON that does not parse (37), a broken component tree (20), components
  written inside `children` instead of their ids (17) and plain text instead
  of a screen (16).
- **With it, those faults are gone, and the app's own checks do the work.**
  The rejections left are mistakes about meaning: a path written as a plain
  string where it should be bound (13), a card labelled with something other
  than the row it shows (6), and a figure typed into text (4). Each went back
  to the model with the reason; most were corrected.
- **What fell back to a plain message (11):** five answers that wrote a path
  such as `"/r1/sector"` into text twice running, three of them on questions
  that try to bend the rules (a figure in plain text, a forecast, raw SQL);
  four whose first layout was malformed (a component it did not define) or
  broke a rule, and whose correction broke another; and two questions that
  took longer than the five-minute limit.
- **Runs vary.** The previous run of this harness, before formats were
  checked, passed 44; eight questions that passed there failed here and
  three went the other way, none of them over a format. One run per setting
  cannot tell those two numbers apart.
- **What got through and is still wrong.** Reading the 47 cards in the
  accepted layouts: every format fits its figure, but five labels do not.
  "90-Day Average" over the 52-week low, "Change Over Period" over the
  52-week position, "Daily Change" over the change across the whole range
  (twice), "52w High/Low" over the high alone. Nothing checks that a label
  describes its figure.

Each step came from reading a run. The schema came from the first runs'
rejections. The checks for paths in text, unnamed rows and formats came from
layouts that had passed and were wrong. A run with the format check alone
passed 34 of 50: 17 layouts were sent back for a format, and the model often
kept the wrong one when told. Tying each format to its figures in the schema
made a wrong one impossible instead; this run had no format rejections. A
larger model is still to be tried.

## Limits

- **The agent keeps its sessions in memory.** After it restarts, a range
  button on an earlier answer does nothing; the answer itself still shows.
- **The A2UI Compose renderer is an alpha** (1.0.0-alpha02, spec v0.9.1) and
  has no encoder for the messages it sends, so the app writes the `action`
  and `error` JSON itself.

## Data

Prices and company data come from Yahoo Finance through
[yfinance](https://github.com/ranaroussi/yfinance), and economic series from
FRED, Federal Reserve Bank of St. Louis, both through
data-engineer-finance-analytics.
