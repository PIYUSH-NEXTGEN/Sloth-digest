# SlothDigest eval report

Deterministic runs over synthetic datasets only (no real chats). The
`scripted` table exercises the full pipeline with `ScriptedPipelineClient`,
a deterministic stand-in that answers chunk/reduce prompts with
perfect-content JSON built from each dataset's ground truth -- it measures
the workflow (chunking, validation, reduce, scoring, attribution), not a
model. The `gemma3:4b (live Ollama)` table runs the same harness against the
real local model; its numbers are the honest product-quality bar.
Regenerate with `uv run --project backend python eval/run_eval.py --fake`
and `--live`.
## Scripted workflow baseline

Perfect-content stand-in: recall here is the workflow ceiling.

| dataset | schema | needs-you recall | decision recall | attribution | groups | messages | surfaced | latency s |
|---|---|---|---|---|---|---|---|---|
| fixtures\discord | ok | 100% | 100% | 100% | 1 | 246 | 7 | 0.116 |
| fixtures\telegram | ok | 100% | 100% | 100% | 1 | 266 | 9 | 0.093 |
| fixtures\whatsapp\android | ok | 100% | 100% | 100% | 1 | 325 | 8 | 0.112 |
| fixtures\whatsapp\edge_cases | ok | 100% | 100% | 100% | 1 | 11 | 12 | 0.04 |
| fixtures\whatsapp\hinglish | ok | 100% | 100% | 100% | 1 | 285 | 9 | 0.113 |
| fixtures\whatsapp\ios | ok | 100% | 100% | 100% | 1 | 10 | 5 | 0.045 |
| eval\datasets\base | ok | 100% | 100% | 100% | 1 | 503 | 8 | 0.13 |
| eval\datasets\hinglish | ok | 100% | 100% | 100% | 1 | 504 | 9 | 0.154 |
| eval\datasets\noisy | ok | 100% | 100% | 100% | 1 | 325 | 7 | 0.138 |

## gemma3:4b via live Ollama

Real model; residual quality noise (bogus decisions, deadline 'when' language) is model-level and tracked under prompt tuning (A5.2).

_
(
n
o
t
 
r
u
n
 
y
e
t
)
_


