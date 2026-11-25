# A scripted model

`script.json` stands in for the model: the agent runs its real tools, checks
and streaming, and takes the model's turns from the file in order. It answers
"How is Apple doing?", then "Which stocks are most volatile?", then a press on
TSLA in the ranking.

    FC_MODEL=scripted:demo/script.json uv run uvicorn finance_agent.server:app --port 8000

Use it to run the app without a model, or when the same answers are wanted
each time. The answer streams the app's tests replay
(`catalog/fixtures/*.sse`) are recorded from it by
`agent/scripts/record_streams.py`.
