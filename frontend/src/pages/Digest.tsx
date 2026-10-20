import { useCallback, useEffect, useState } from "react";
import DigestCard from "../components/DigestCard";
import { getDigest, getLatestDigest, runDigest, APIError } from "../api/client";
import type { Digest } from "../types";

type Status = "loading" | "ready" | "empty" | "error";

export default function DigestPage() {
  const [digest, setDigest] = useState<Digest | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      const latest = await getLatestDigest();
      setDigest(latest);
      setStatus(latest.groups.length === 0 ? "empty" : "ready");
    } catch (err) {
      setError(err instanceof APIError ? err.message : String(err));
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const runNow = useCallback(async () => {
    setRunning(true);
    setError(null);
    try {
      const { digest_id } = await runDigest();
      const fresh = await getDigestById(digest_id);
      setDigest(fresh);
      setStatus(fresh.groups.length === 0 ? "empty" : "ready");
    } catch (err) {
      setError(err instanceof APIError ? err.message : String(err));
      setStatus("error");
    } finally {
      setRunning(false);
    }
  }, []);

  if (status === "loading") {
    return <p className="empty-note">Fetching your morning digest…</p>;
  }

  if (status === "error") {
    return (
      <div className="digest-page">
        <h2>Morning digest</h2>
        <p role="alert">Could not load the digest: {error}</p>
        <button type="button" onClick={() => void load()}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="digest-page">
      <h2>Morning digest</h2>
      <p className="meta">
        {digest ? `${digest.groups.length} groups` : ""} · window{" "}
        {digest ? `${digest.window.start} → ${digest.window.end}` : ""}
      </p>
      <button type="button" onClick={() => void runNow()} disabled={running}>
        {running ? "Running digest…" : "Run digest now"}
      </button>
      {status === "empty" ? (
        <p className="empty-note">
          No digest yet. Drop a chat export in Sources to get started.
        </p>
      ) : null}
      {digest
        ? digest.groups.map((group) => (
            <DigestCard key={group.conversation_id} group={group} />
          ))
        : null}
    </div>
  );
}

async function getDigestById(id: string): Promise<Digest> {
  return getDigest(id);
}
