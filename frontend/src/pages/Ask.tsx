import { useCallback, useState } from "react";
import { ask, APIError } from "../api/client";
import type { Answer } from "../api/client";

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = useCallback(async () => {
    const trimmed = question.trim();
    if (!trimmed) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setAnswer(await ask(trimmed));
    } catch (err) {
      setError(err instanceof APIError ? err.message : String(err));
      setAnswer(null);
    } finally {
      setBusy(false);
    }
  }, [question]);

  return (
    <div className="ask-page">
      <h2>Ask your chats</h2>
      <p className="meta">
        Answers come only from your local store; every claim cites message ids.
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <label htmlFor="ask-question">Question</label>
        <input
          id="ask-question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="who owes the booking amount?"
          enterKeyHint="search"
          autoComplete="off"
        />
        <button type="submit" disabled={busy || question.trim().length === 0}>
          {busy ? "Searching locally…" : "Ask"}
        </button>
      </form>
      {error ? <p role="alert">Ask failed: {error}</p> : null}
      {answer ? (
        <article className="digest-card" aria-label="Answer">
          <p className="tldr">{answer.answer}</p>
          <h3>Sources</h3>
          {answer.sources.length > 0 ? (
            <ul className="summary-list">
              {answer.sources.map((messageId) => (
                <li key={messageId}>
                  <code className="source-id">{messageId}</code>
                </li>
              ))}
            </ul>
          ) : (
            <p className="empty-note">No supporting messages found.</p>
          )}
        </article>
      ) : null}
    </div>
  );
}
