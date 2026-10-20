import DigestPage from "./pages/Digest";

export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>SlothDigest</h1>
        <p className="tagline">Sleep through the chat. Wake up caught up.</p>
        <nav aria-label="Main navigation">
          <a href="/digest">Digest</a>
          {" · "}
          <a href="/sources">Sources</a>
          {" · "}
          <a href="/settings">Settings</a>
        </nav>
      </header>
      <main>
        <DigestPage />
      </main>
    </div>
  );
}
