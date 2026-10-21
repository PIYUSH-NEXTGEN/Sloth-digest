import { useCallback, useEffect, useState } from "react";
import { listSources, ingestFile, APIError } from "../api/client";
import type { ConversationInfo } from "../types";
import { PLATFORM_LABELS } from "../types";

type LoadState = "loading" | "ready" | "error";

export default function SourcesPage() {
  const [conversations, setConversations] = useState<ConversationInfo[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const load = useCallback(async () => {
    setState("loading");
    try {
      const { conversations: convs } = await listSources();
      setConversations(convs);
      setState("ready");
    } catch (err) {
      setError(err instanceof APIError ? err.message : String(err));
      setState("error");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const upload = useCallback(
    async (file: File) => {
      setUploading(true);
      setError(null);
      setLastResult(null);
      try {
        const result = await ingestFile(file);
        setLastResult(
          `"${file.name}": ${result.imported} new messages` +
            (result.duplicates > 0
              ? `, ${result.duplicates} duplicates skipped`
              : "") +
            `.`,
        );
        await load();
      } catch (err) {
        setError(
          err instanceof APIError
            ? `Upload failed: ${err.message}`
            : `Upload failed: ${String(err)}`,
        );
      } finally {
        setUploading(false);
      }
    },
    [load],
  );

  return (
    <div className="sources-page">
      <h2>Sources</h2>
      {state === "error" ? (
        <p role="alert">Could not load sources: {error}</p>
      ) : null}
      <UploadBox
        onFile={(f) => void upload(f)}
        uploading={uploading}
        dragOver={dragOver}
        setDragOver={setDragOver}
        lastResult={lastResult}
        error={error}
      />
      {state === "ready" ? (
        <ConversationList conversations={conversations} />
      ) : null}
    </div>
  );
}

interface UploadBoxProps {
  onFile: (file: File) => void;
  uploading: boolean;
  dragOver: boolean;
  setDragOver: (over: boolean) => void;
  lastResult: string | null;
  error: string | null;
}

function UploadBox(props: UploadBoxProps) {
  const { onFile, uploading, dragOver, setDragOver, lastResult, error } = props;

  return (
    <section
      className={dragOver ? "upload-box drag-over" : "upload-box"}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const file = e.dataTransfer.files[0];
        if (file) {
          onFile(file);
        }
      }}
      aria-label="Chat export upload"
    >
      <p>
        Drop a chat export here (WhatsApp .txt / Discord JSON / Telegram JSON) —
        imported locally, nothing is sent anywhere.
      </p>
      <label>
        <input
          aria-label="Chat export file"
          type="file"
          accept=".txt,.json"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onFile(file);
          }}
        />
      </label>
      {uploading ? <p className="empty-note">Importing…</p> : null}
      {lastResult ? (
        <p role="status" className="import-result">
          {lastResult}
        </p>
      ) : null}
      {error && !uploading ? <p role="alert">{error}</p> : null}
    </section>
  );
}

function ConversationList({
  conversations,
}: {
  conversations: ConversationInfo[];
}) {
  if (conversations.length === 0) {
    return (
      <p className="empty-note">
        No conversations yet. Import an export above to get started.
      </p>
    );
  }
  return (
    <ul aria-label="Imported conversations" className="conversation-list">
      {conversations.map((conv) => (
        <li key={conv.id}>
          <span className="conv-name">{conv.name}</span>{" "}
          <span className="meta">
            ({PLATFORM_LABELS[conv.platform]} · {conv.message_count} messages
            {conv.last_message_at ? ` · until ${conv.last_message_at}` : ""})
          </span>
        </li>
      ))}
    </ul>
  );
}
