import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import AskPage from "../pages/Ask";
import { server } from "../mocks/server";

describe("AskPage", () => {
  it("answers a question and lists cited sources", async () => {
    render(<AskPage />);

    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "who owes the booking amount?" },
    });
    fireEvent.click(screen.getByRole("button", { name: /ask/i }));

    await waitFor(() =>
      expect(
        screen.getByText(/aman is collecting booking amounts/i),
      ).toBeInTheDocument(),
    );
    const sources = screen.getByRole("list");
    expect(sources).toHaveTextContent("whatsapp:trip-planning:000123");
    expect(sources).toHaveTextContent("discord:cricket-squad:000028");
  });

  it("stays disabled until the question has content", () => {
    render(<AskPage />);
    const button = screen.getByRole("button", { name: /ask/i });
    expect(button).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "   " },
    });
    expect(button).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "who took the carrom coins?" },
    });
    expect(button).toBeEnabled();
  });

  it("shows an error state when /ask fails", async () => {
    server.use(
      http.post("*/ask", () =>
        HttpResponse.json({ detail: "retrieval offline" }, { status: 500 }),
      ),
    );
    render(<AskPage />);
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "who owes zoodles?" },
    });
    fireEvent.click(screen.getByRole("button", { name: /ask/i }));

    const alerts = await screen.findAllByRole("alert");
    expect(
      alerts.some((el) => /retrieval offline/.test(el.textContent ?? "")),
    ).toBe(true);
  }, 10000);
});
