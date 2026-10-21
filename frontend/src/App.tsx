import { useCallback, useEffect, useState } from "react";
import DigestPage from "./pages/Digest";
import SourcesPage from "./pages/Sources";
import SettingsPage from "./pages/Settings";

export type Route = "digest" | "sources" | "settings";

const DEFAULT_ROUTE: Route = "digest";

function currentRoute(): Route {
  const hash = window.location.hash.replace(/^#\/?/, "").toLowerCase();
  if (hash === "sources" || hash === "settings") {
    return hash;
  }
  return DEFAULT_ROUTE;
}

export default function App() {
  const [route, setRoute] = useState<Route>(currentRoute);

  const syncWithHash = useCallback(() => {
    setRoute(currentRoute());
  }, []);

  useEffect(() => {
    window.addEventListener("hashchange", syncWithHash);
    return () => window.removeEventListener("hashchange", syncWithHash);
  }, [syncWithHash]);

  const navigate = useCallback((next: Route) => {
    window.location.hash = `/${next}`;
    setRoute(next);
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <h1>SlothDigest</h1>
        <p className="tagline">Sleep through the chat. Wake up caught up.</p>
        <nav aria-label="Main navigation">
          <button
            type="button"
            className={route === "digest" ? "active" : ""}
            onClick={() => navigate("digest")}
          >
            Digest
          </button>
          <button
            type="button"
            className={route === "sources" ? "active" : ""}
            onClick={() => navigate("sources")}
          >
            Sources
          </button>
          <button
            type="button"
            className={route === "settings" ? "active" : ""}
            onClick={() => navigate("settings")}
          >
            Settings
          </button>
        </nav>
      </header>
      <main>
        {route === "digest" ? <DigestPage /> : null}
        {route === "sources" ? <SourcesPage /> : null}
        {route === "settings" ? <SettingsPage /> : null}
      </main>
    </div>
  );
}
