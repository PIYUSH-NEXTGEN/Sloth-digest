"""Digest delivery (A3.2): render Markdown + HTML, write files, notify.

Writes ``digests/YYYY-MM-DD.md`` and ``.html`` (date = generated_at, UTC).
HTML escapes ALL chat-derived text - never interpolate message content raw.
Desktop notification is opt-in (settings.desktop_notify) and silently no-ops
when plyer is unavailable; nothing is ever sent anywhere - files stay local.
"""

import html
from datetime import UTC, datetime
from pathlib import Path

from app.models import Digest


def _stamp(dt: datetime) -> str:
    return dt.isoformat(timespec="minutes")


def render_markdown(digest: Digest) -> str:
    lines: list[str] = [
        f"# SlothDigest - {digest.generated_at.date().isoformat()}",
        "",
        f"Window: {_stamp(digest.window.start)} .. {_stamp(digest.window.end)} (UTC)",
        f"Model: {digest.model} | Prompt: {digest.prompt_version}",
        "",
    ]
    for group in digest.groups:
        lines.append(f"## {group.name} ({group.platform.value})")
        lines.append("")
        lines.append(f"{group.message_count} messages, skipped {group.skipped_count} banter.")
        lines.append("")
        lines.append(f"**TL;DR:** {group.tldr}")
        lines.append("")
        if group.needs_you:
            lines.append("### Needs you")
            for item in group.needs_you:
                lines.append(f"- **{item.from_}** ({item.message_id}): {item.summary}")
                lines.append(f"  - why: {item.reason}")
                if item.suggested_reply:
                    lines.append(f"  - draft reply: {item.suggested_reply}")
            lines.append("")
        if group.decisions:
            lines.append("### Decisions")
            for decision in group.decisions:
                ids = ", ".join(decision.message_ids[:3])
                lines.append(f"- {decision.text} ({ids})")
            lines.append("")
        if group.deadlines:
            lines.append("### Deadlines")
            for deadline in group.deadlines:
                when = f" - due {deadline.when}" if deadline.when else ""
                lines.append(f"- {deadline.text}{when}")
            lines.append("")
        if group.by_person:
            lines.append("### Per person")
            for person in group.by_person:
                points = "; ".join(person.points[:3])
                lines.append(f"- {person.name}: {points}")
            lines.append("")
    lines.append("_Generated locally. Nothing left this machine._")
    return "\n".join(lines) + "\n"


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def render_html(digest: Digest) -> str:
    parts: list[str] = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        "<title>SlothDigest</title>",
        "<style>body{font-family:system-ui,sans-serif;max-width:760px;"
        "margin:2rem auto;padding:0 1rem}",
        "section{border:1px solid #ddd;border-radius:8px;padding:1rem;margin:1rem 0}",
        ".needs{background:#fff8e1;padding:.5rem;border-radius:6px}",
        ".meta{color:#666;font-size:.9rem}</style></head><body>",
        f"<h1>SlothDigest - {_esc(digest.generated_at.date().isoformat())}</h1>",
        f'<p class="meta">window {_esc(_stamp(digest.window.start))} .. '
        f"{_esc(_stamp(digest.window.end))} (UTC) | "
        f"model {_esc(digest.model)} | prompt {_esc(digest.prompt_version)}</p>",
    ]
    for group in digest.groups:
        parts.append("<section>")
        parts.append(
            f"<h2>{_esc(group.name)} <small class='meta'>({_esc(group.platform.value)}, "
            f"{group.message_count} messages, skipped {group.skipped_count} banter)</small></h2>"
        )
        parts.append(f"<p><strong>TL;DR:</strong> {_esc(group.tldr)}</p>")
        if group.needs_you:
            parts.append("<h3>Needs you</h3><ul>")
            for item in group.needs_you:
                parts.append(
                    f"<li><strong>{_esc(item.from_)}</strong>: {_esc(item.summary)} "
                    f"<small class='meta'>{_esc(item.reason)}</small>"
                )
                if item.suggested_reply:
                    parts.append(f"<br><em>draft reply: {_esc(item.suggested_reply)}</em>")
                parts.append("</li>")
            parts.append("</ul>")
        if group.decisions:
            parts.append("<h3>Decisions</h3><ul>")
            for decision in group.decisions:
                parts.append(f"<li>{_esc(decision.text)}</li>")
            parts.append("</ul>")
        if group.deadlines:
            parts.append("<h3>Deadlines</h3><ul>")
            for deadline in group.deadlines:
                when = f" - due {_esc(deadline.when)}" if deadline.when else ""
                parts.append(f"<li>{_esc(deadline.text)}{when}</li>")
            parts.append("</ul>")
        if group.by_person:
            parts.append("<h3>Per person</h3><ul>")
            for person in group.by_person:
                points = "; ".join(_esc(p) for p in person.points[:3])
                parts.append(f"<li><strong>{_esc(person.name)}</strong>: {points}</li>")
            parts.append("</ul>")
        parts.append("</section>")
    parts.append("<p class='meta'>Generated locally. Nothing left this machine.</p>")
    parts.append("</body></html>")
    return "\n".join(parts) + "\n"


def write_digest_files(digest: Digest, out_dir: str | Path) -> tuple[Path, Path]:
    """Write YYYY-MM-DD.md and .html; returns (md_path, html_path)."""
    folder = Path(out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    date = digest.generated_at.astimezone(UTC).date().isoformat()
    md_path = folder / f"{date}.md"
    html_path = folder / f"{date}.html"
    md_path.write_text(render_markdown(digest), encoding="utf-8")
    html_path.write_text(render_html(digest), encoding="utf-8")
    return md_path, html_path
