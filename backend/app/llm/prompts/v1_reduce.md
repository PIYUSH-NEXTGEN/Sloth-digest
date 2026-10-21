# Reduce chunk extracts into one group digest (prompt v1)

You are merging per-chunk summaries of one group conversation into a single
digest. Each chunk summary was produced against the same window; you
deduplicate and keep only what matters. Respond with JSON ONLY.

## Input
```json
{"conversation": "...", "window": "...", "chunk_summaries": [ ... ]}
```
Each entry in `chunk_summaries` has the same shape as your output below.

## Output JSON shape
{
  "tldr": string,
  "topics": [string],
  "decisions": [{"text": string, "message_ids": [string]}],
  "deadlines": [{"text": string, "when": string|null, "message_ids": [string]}],
  "per_person": [{"name": string, "points": [string]}]
}

Note: `needs_you` is computed deterministically by the system
(score.py) and is NOT your job. Do not return it.

## Rules
1. Message ids must be copied verbatim from the chunk summaries. Never
   invent ids.
2. Deduplicate: if two chunks report the same decision, keep one entry and
   merge their `message_ids`.
3. If a later chunk corrects an earlier decision ("actually 7pm"), keep the
   corrected wording only and note it briefly in the text (e.g.
   "venue: park; later changed to 7pm").
4. `tldr`: at most two short sentences, <= 400 chars. No markdown.
5. Keep names exactly as they appear in the chunks.
6. Nothing invented: absent facts stay absent. Pure-banter merges to empty
   lists.
