import { useCallback, useEffect, useState } from "react";
import { getSettings, updateSettings, APIError } from "../api/client";
import type { Settings } from "../api/client";

type Status = "loading" | "ready" | "error";

function parseList(value: string): string[] {
  return value
    .split(/[,\n]/)
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0);
}

export default function SettingsPage() {
  const [status, setStatus] = useState<Status>("loading");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  const [userNames, setUserNames] = useState("");
  const [vipPeople, setVipPeople] = useState("");
  const [keywords, setKeywords] = useState("");
  const [digestTime, setDigestTime] = useState("06:00");
  const [model, setModel] = useState("");

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      const current = await getSettings();
      setUserNames(current.user_names.join(", "));
      setVipPeople(current.vip_people.join(", "));
      setKeywords(current.keywords.join(", "));
      setDigestTime(current.digest_time);
      setModel(current.model);
      setError(null);
      setStatus("ready");
    } catch (err) {
      setError(err instanceof APIError ? err.message : String(err));
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const save = useCallback(async () => {
    setSaving(true);
    setSaved(false);
    try {
      const updated: Settings = {
        user_names: parseList(userNames),
        vip_people: parseList(vipPeople),
        keywords: parseList(keywords),
        digest_time: digestTime,
        model: model.trim(),
      };
      const echoed = await updateSettings(updated);
      setUserNames(echoed.user_names.join(", "));
      setVipPeople(echoed.vip_people.join(", "));
      setKeywords(echoed.keywords.join(", "));
      setDigestTime(echoed.digest_time);
      setModel(echoed.model);
      setSaved(true);
    } catch (err) {
      setError(err instanceof APIError ? err.message : String(err));
      setSaved(false);
    } finally {
      setSaving(false);
    }
  }, [userNames, vipPeople, keywords, digestTime, model]);

  if (status === "loading") {
    return <p className="empty-note">Loading settings…</p>;
  }

  if (status === "error") {
    return (
      <div className="settings-page">
        <h2>Settings</h2>
        <p role="alert">Could not load settings: {error}</p>
        <button type="button" onClick={() => void load()}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="settings-page">
      <h2>Settings</h2>
      <p className="meta">
        These tune who counts as "you", who is VIP, and which keywords surface.
        Everything stays in your local database.
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <label htmlFor="user-names">Your names & aliases</label>
        <input
          id="user-names"
          value={userNames}
          onChange={(event) => setUserNames(event.target.value)}
          placeholder="Your Name, nickname"
        />
        <label htmlFor="vip-people">VIP people</label>
        <input
          id="vip-people"
          value={vipPeople}
          onChange={(event) => setVipPeople(event.target.value)}
          placeholder="Riya, Kabir"
        />
        <label htmlFor="keywords">Extra keywords</label>
        <input
          id="keywords"
          value={keywords}
          onChange={(event) => setKeywords(event.target.value)}
          placeholder="urgent, deadline, verify"
        />
        <label htmlFor="digest-time">Digest time (local HH:MM)</label>
        <input
          id="digest-time"
          value={digestTime}
          onChange={(event) => setDigestTime(event.target.value)}
          pattern="\d{2}:\d{2}"
          maxLength={5}
        />
        <label htmlFor="model">Ollama model tag</label>
        <input
          id="model"
          value={model}
          onChange={(event) => setModel(event.target.value)}
          placeholder="gemma3:4b"
        />
        <button type="submit" disabled={saving}>
          {saving ? "Saving…" : "Save settings"}
        </button>
        {saved ? (
          <p role="status" className="empty-note">
            Saved. Your next digest run uses these instantly.
          </p>
        ) : null}
      </form>
    </div>
  );
}
