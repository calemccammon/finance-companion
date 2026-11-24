# A scripted model

`script.json` stands in for the model: the agent runs its real tools, checks
and streaming, and takes the model's turns from the file in order. It answers
"How is Apple doing?", then "Which stocks are most volatile?", then a press on
TSLA in the ranking.

    FC_MODEL=scripted:demo/script.json uv run uvicorn finance_agent.server:app --port 8000

It is how the app is run and recorded without a model, so that a recording
shows the same answers each time; the local model evaluated in the main README
writes a screen the checks accept for most questions, but not every time.
