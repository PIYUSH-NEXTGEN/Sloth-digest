import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  getDigest,
  getHealth,
  getLatestDigest,
  getSettings,
  runDigest,
} from "../api/client";
import { server } from "../mocks/server";
import { http, HttpResponse } from "msw";
import { sampleDigest } from "../mocks/sampleDigest";

describe("typed API client against MSW mocks", () => {
  it("fetches health", async () => {
    const health = await getHealth();
    expect(health.status).toBe("ok");
    expect(health.model).toBe("gemma3:4b");
  });

  it("fetches the latest digest and it matches the sample", async () => {
    const digest = await getLatestDigest();
    expect(digest.id).toBe(sampleDigest.id);
    expect(digest.window.start).toBe(sampleDigest.window.start);
    expect(digest.groups[0]!.name).toBe(sampleDigest.groups[0]!.name);
  });

  it("raises APIError with server detail on 404", async () => {
    server.use(
      http.get("*/digest/latest", () =>
        HttpResponse.json({ detail: "no digest yet" }, { status: 404 }),
      ),
    );
    await expect(getLatestDigest()).rejects.toMatchObject({
      name: "APIError",
      status: 404,
      message: "no digest yet",
    });
  });

  it("runs a digest and fetches it by id", async () => {
    const run = await runDigest();
    expect(run.digest_id).toBe(sampleDigest.id);
    const fresh = await getDigest(run.digest_id);
    expect(fresh.groups).toHaveLength(2);
  });

  it("round-trips settings", async () => {
    const settings = await getSettings();
    expect(settings.digest_time).toBe("06:00");
  });
});

describe("DigestPage renders against mocks", () => {
  it("shows the sample digest once loaded", async () => {
    const { default: DigestPage } = await import("../pages/Digest");
    render(<DigestPage />);
    await waitFor(() =>
      expect(
        screen.getByRole("article", { name: /weekend trip/i }),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("button", { name: /run digest now/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/fetching your morning digest/i),
    ).not.toBeInTheDocument();
  });

  it("shows an error state with retry when the API fails", async () => {
    server.use(
      http.get("*/digest/latest", () =>
        HttpResponse.json({ detail: "backend down" }, { status: 500 }),
      ),
    );
    const { default: DigestPage } = await import("../pages/Digest");
    render(<DigestPage />);
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/backend down/),
    );
  });
});
