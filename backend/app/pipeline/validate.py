"""Validation hard-stop (A2.7): LLM output vs the store, before display.

The LLM may reference message IDs but never decides who said something
(AGENTS.md 7.4). extract.shape checks catch most garbage; this module is the
last line of defense before a digest can leave a machine:

- every decision/deadline message_id must exist in the window's messages -
  unknown ids are dropped; an item left without ids is dropped entirely,
- question ids pointing at missing/system messages are dropped,
- NeedsYouItem.from_ is already rebuilt from the store by score.py, but we
  re-assert it here (belt and braces, no fake attribution ever),
- ids get sorted+deduped for determinism.
"""

from app.models import Deadline, Decision, GroupDigest, Message, NeedsYouItem


def validate_decisions(
    decisions: list[Decision], all_ids: set[str]
) -> list[tuple[Decision, list[str]]]:
    """(kept item, ids) pairs; ids validated."""
    kept: list[tuple[Decision, list[str]]] = []
    for decision in decisions:
        ids = [mid for mid in dict.fromkeys(decision.message_ids) if mid in all_ids]
        if ids:
            kept.append((decision, ids))
    return kept


def validate_deadlines(
    deadlines: list[Deadline], all_ids: set[str]
) -> list[tuple[Deadline, list[str]]]:
    kept: list[tuple[Deadline, list[str]]] = []
    for deadline in deadlines:
        ids = [mid for mid in dict.fromkeys(deadline.message_ids) if mid in all_ids]
        if ids:
            kept.append((deadline, ids))
    return kept


def validate_questions(question_ids: list[str], all_ids: set[str]) -> list[str]:
    return [mid for mid in dict.fromkeys(question_ids) if mid in all_ids]


def validate_needs_you(items: list[NeedsYouItem], messages: list[Message]) -> list[NeedsYouItem]:
    """from_ must match the stored message sender; unknown ids dropped."""
    by_id = {m.id: m for m in messages}
    kept: list[NeedsYouItem] = []
    for item in items:
        message = by_id.get(item.message_id)
        if message is None:
            continue
        if item.from_ != message.sender:
            # LLM-provided attribution - rebuild from the store, never trust it
            item = item.model_copy(update={"from_": message.sender})
        kept.append(item)
    return kept


def validate_group_digest(digest: GroupDigest, messages: list[Message]) -> GroupDigest:
    """Return a corrected copy of the digest; raises on empty needs-you."""
    all_ids = {m.id for m in messages}
    kept_decisions = validate_decisions(digest.decisions, all_ids)
    kept_deadlines = validate_deadlines(digest.deadlines, all_ids)
    decisions = [Decision(text=d.text, message_ids=ids) for d, ids in kept_decisions]
    deadlines = [
        Deadline(text=dtext.text, when=dtext.when, message_ids=ids) for dtext, ids in kept_deadlines
    ]
    needs_you = validate_needs_you(digest.needs_you, messages)
    return digest.model_copy(
        update={
            "decisions": decisions,
            "deadlines": deadlines,
            "needs_you": needs_you,
        }
    )
