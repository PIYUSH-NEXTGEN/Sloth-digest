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
| fixtures\discord | ok | 100% | 100% | 100% | 1 | 246 | 7 | 0.038 |
| fixtures\telegram | ok | 100% | 100% | 100% | 1 | 266 | 15 | 0.039 |
| fixtures\whatsapp\android | ok | 100% | 100% | 100% | 1 | 325 | 15 | 0.038 |
| fixtures\whatsapp\edge_cases | ok | 100% | 100% | 100% | 1 | 11 | 12 | 0.016 |
| fixtures\whatsapp\hinglish | ok | 100% | 100% | 100% | 1 | 285 | 15 | 0.044 |
| fixtures\whatsapp\ios | ok | 100% | 100% | 100% | 1 | 10 | 5 | 0.015 |
| eval\datasets\base | ok | 100% | 100% | 100% | 1 | 503 | 15 | 0.068 |
| eval\datasets\hinglish | ok | 100% | 100% | 100% | 1 | 504 | 15 | 0.09 |
