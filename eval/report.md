# SlothDigest eval report

Deterministic runs over the synthetic datasets (no real chats).
`--fake` exercises the full pipeline with `ScriptedPipelineClient`:
a deterministic stand-in that answers chunk/reduce prompts with
perfect-content JSON built from each dataset's ground truth. It
measures the workflow (chunking, validation, reduce, scoring,
attribution), not a model; `--live` results with real Gemma land
here as well once the demo machine has Ollama pulled up.

| dataset | schema | needs-you recall | decision recall | attribution | groups | messages | surfaced | latency s |
|---|---|---|---|---|---|---|---|---|
| fixtures\discord | ok | 100% | 100% | 100% | 1 | 246 | 7 | 0.036 |
| fixtures\telegram | ok | 100% | 100% | 100% | 1 | 266 | 15 | 0.03 |
| fixtures\whatsapp\android | ok | 100% | 100% | 100% | 1 | 325 | 15 | 0.057 |
| fixtures\whatsapp\edge_cases | ok | 100% | 100% | 100% | 1 | 11 | 12 | 0.02 |
| fixtures\whatsapp\hinglish | ok | 100% | 100% | 100% | 1 | 285 | 15 | 0.031 |
| fixtures\whatsapp\ios | ok | 100% | 100% | 100% | 1 | 10 | 5 | 0.013 |
| eval\datasets\base | ok | 100% | 100% | 100% | 1 | 503 | 15 | 0.063 |
| eval\datasets\hinglish | ok | 100% | 100% | 100% | 1 | 504 | 15 | 0.516 |
| eval\datasets\noisy | ok | 100% | 100% | 100% | 1 | 325 | 7 | 0.129 |
