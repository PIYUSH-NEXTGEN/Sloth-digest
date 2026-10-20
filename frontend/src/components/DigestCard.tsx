import { useState } from "react";
import type { DigestGroup } from "../types";
import { PLATFORM_LABELS } from "../types";
import NeedsYouList from "./NeedsYouList";
import PersonSummary from "./PersonSummary";

interface DigestCardProps {
  group: DigestGroup;
}

export default function DigestCard({ group }: DigestCardProps) {
  const [showSkipped, setShowSkipped] = useState(false);

  const platformLabel = PLATFORM_LABELS[group.platform];

  return (
    <article className="digest-card" aria-label={`Digest for ${group.name}`}>
      <header>
        <h2>{group.name}</h2>
        <p className="meta">
          {platformLabel} · {group.message_count} messages
        </p>
      </header>

      <p className="tldr" role="doc-abstract">
        {group.tldr}
      </p>

      <NeedsYouList items={group.needs_you} />

      {group.decisions.length > 0 ? (
        <section aria-labelledby={`decisions-${group.conversation_id}`}>
          <h3 id={`decisions-${group.conversation_id}`}>Decisions</h3>
          <ul className="summary-list">
            {group.decisions.map((decision) => (
              <li key={decision.text}>{decision.text}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {group.by_person.length > 0 ? (
        <section aria-labelledby={`by-person-${group.conversation_id}`}>
          <h3 id={`by-person-${group.conversation_id}`}>By person</h3>
          {group.by_person.map((person) => (
            <PersonSummary
              key={person.name}
              name={person.name}
              points={person.points}
            />
          ))}
        </section>
      ) : null}

      {group.deadlines.length > 0 ? (
        <section aria-labelledby={`deadlines-${group.conversation_id}`}>
          <h3 id={`deadlines-${group.conversation_id}`}>Deadlines</h3>
          <ul className="summary-list">
            {group.deadlines.map((deadline) => (
              <li key={deadline.text}>
                {deadline.text}
                {deadline.when ? <em> ({deadline.when})</em> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <button
        type="button"
        aria-expanded={showSkipped}
        onClick={() => setShowSkipped((prev) => !prev)}
      >
        {showSkipped
          ? `Hide skipped banter (${group.skipped_count} messages)`
          : `Show skipped (${group.skipped_count} messages of banter)`}
      </button>
      {showSkipped ? (
        <p className="empty-note">
          Skipped {group.skipped_count} low-value messages (banter, memes,
          reactions). Full messages stay in your local database.
        </p>
      ) : null}
    </article>
  );
}
