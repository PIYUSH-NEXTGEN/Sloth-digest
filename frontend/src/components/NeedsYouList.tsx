import type { NeedsYouItem } from "../types";

interface NeedsYouListProps {
  items: NeedsYouItem[];
}

export default function NeedsYouList({ items }: NeedsYouListProps) {
  if (items.length === 0) {
    return (
      <section aria-labelledby="needs-you-heading">
        <h3 id="needs-you-heading">Needs you</h3>
        <p className="empty-note">Nothing needs you. Sleep on. 🦥</p>
      </section>
    );
  }

  return (
    <section aria-labelledby="needs-you-heading">
      <h3 id="needs-you-heading">Needs you ({items.length})</h3>
      <ul className="needs-you-list">
        {items.map((item) => (
          <li key={item.message_id} className="needs-you-item">
            <p className="needs-you-summary">
              <strong>{item.from}</strong>: {item.summary}
            </p>
            <p className="needs-you-reason">{item.reason}</p>
            {item.suggested_reply ? (
              <p className="suggested-reply">
                <span>Suggested reply (draft only, never sent):</span>{" "}
                {item.suggested_reply}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
