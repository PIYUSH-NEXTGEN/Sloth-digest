# Extract one chat chunk (prompt v1)

You read a slice of a group chat and produce a strict JSON summary.
Respond with JSON ONLY - no prose, no code fences.

## Input
The chunk lists messages as: `<message_id> [<HH:MM>] <sender>: <text>`
where `<text>` may contain placeholders like `[PHONE_1]` (redacted data).
Placeholders are redacted on purpose; do not try to reconstruct them.

## Output JSON shape
{
  "topics": [string],
  "decisions": [{"text": string, "message_ids": [string]}],
  "questions_for_user": [{"message_id": string, "question": string}],
  "deadlines": [{"text": string, "when": string|null, "message_ids": [string]}],
  "per_person": [{"name": string, "points": [string]}]
}

## Hard rules
1. Reference messages ONLY by the `message_id` strings given in the chunk.
   An id that is not in the chunk makes verification impossible - do not
   invent, shorten, or reformat ids.
2. NEVER decide who said something. Names come from the message lines you
   were given; when you summarise what a person said, `name` must be copied
   from one of those lines.
3. Do not invent facts. If the chunk is pure banter, return empty lists.
4. "questions_for_user" is for questions clearly directed *at the user*
   (the person the digest is for). If unsure it is directed at them, leave
   it out.
5. "decisions" includes corrections that change an earlier plan
   (e.g. "actually make it 7"). Put the id of the correcting message in
   `message_ids` too.
6. "deadlines" includes commitments with a time ("by Friday", "kal tak",
   "tomorrow"). Normalise `when` to YYYY-MM-DD or HH:MM ONLY when the chunk
   itself gives the full date; otherwise null. Never guess a year.
7. Keep each text field short (<= 240 chars); no markdown inside strings.
8. Dates are in local time as printed in the chunk.
9. Keep output SHORT so the JSON is never cut off: at most 6 topics, at
   most 4 decisions, at most 4 deadlines, at most 4 per_person entries,
   and at most 3 `points` per person as SHORT text (say what they did or
   asked, never an id, never a bare date).
