# finance-companion

An Android app that answers questions about stocks and the economy with native
screens an AI agent composes, using the A2UI protocol and its Jetpack Compose
renderer.

The data is the warehouse built by
[data-engineer-finance-analytics](https://github.com/calemccammon/data-engineer-finance-analytics):
daily prices for ten tickers and six FRED series, modelled in dbt. The model
chooses which analyses to run and how to lay out the answer. It never writes
SQL and never produces a number: every figure on screen comes from a fixed,
parameterised query against the dbt marts.

Work in progress. The plan is in the repository's milestones and issues.
