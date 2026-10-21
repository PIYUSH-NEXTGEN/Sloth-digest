import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import SourcesPage from "../pages/Sources";
import { server } from "../mocks/server";

describe("SourcesPage", () => {
  it("lists known conversations with counts", async () => {
    render(<SourcesPage />);

    await waitFor(() =>
      expect(screen.getByText("Weekend trip planning 🏔️")).toBeInTheDocument(),
    );
    expect(screen.getByText("sunday-cricket-squad")).toBeInTheDocument();
    expect(screen.getByText(/412 messages/)).toBeInTheDocument();
    expect(screen.getByText(/187 messages/)).toBeInTheDocument();
  });

  it("shows an empty state when no conversations are stored", async () => {
    server.use(
      http.get("*/sources", () => HttpResponse.json({ conversations: [] })),
    );
    render(<SourcesPage />);

    await waitFor(() =>
      expect(screen.getByText(/no conversations yet/i)).toBeInTheDocument(),
    );
  });

  it("shows an error state when /sources fails", async () => {
    server.use(
      http.get("*/sources", () =>
        HttpResponse.json({ detail: "backend down" }, { status: 500 }),
      ),
    );
    render(<SourcesPage />);

    const alerts = await screen.findAllByRole("alert");
    expect(alerts.some((el) => /backend down/.test(el.textContent ?? ""))).toBe(
      true,
    );
  }, 10000);

  it("uploads a file through the input and refreshes the list", async () => {
    render(<SourcesPage />);

    await waitFor(() =>
      expect(screen.getByText("Weekend trip planning 🏔️")).toBeInTheDocument(),
    );

    const input = screen.getByLabelText("Chat export file");
    const file = new File(["chat content"], "chat.txt", {
      type: "text/plain",
    });
    fireEvent.change(input, { target: { files: [file] } });

    const status = await screen.findByRole("status", {}, { timeout: 10000 });
    expect(status).toHaveTextContent(/404 new messages, 8 duplicates skipped/i);
  }, 20000);
});
