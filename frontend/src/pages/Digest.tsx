import { getSampleDigest } from "../mocks/sampleDigest";
import DigestCard from "../components/DigestCard";

export default function DigestPage() {
  const digest = getSampleDigest();

  return (
    <div className="digest-page">
      <h2>Morning digest</h2>
      <p className="meta">
        Sample data while the backend is under construction.{" "}
        {digest.groups.length} groups in the window.
      </p>
      {digest.groups.map((group) => (
        <DigestCard key={group.conversation_id} group={group} />
      ))}
      {digest.groups.length === 0 ? (
        <p className="empty-note">
          No digest yet. Drop a chat export in Sources to get started.
        </p>
      ) : null}
    </div>
  );
}
