import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import SettingsPage from "../pages/Settings";
import { server } from "../mocks/server";

const SAVED_ALERT_TEXT = "Saved. Your next digest run uses these instantly.";

describe("SettingsPage", () => {
  it("loads current settings into the form", async () => {
    render(<SettingsPage />);

    await waitFor(() => {
      expect(
        screen.getByLabelText("Your names & aliases") as HTMLInputElement,
      ).toHaveValue("Priya, prids");
    });
    expect(screen.getByLabelText("VIP people")).toHaveValue("Riya");
    expect(screen.getByLabelText("Extra keywords")).toHaveValue("biryani");
    expect(screen.getByLabelText(/Digest time/)).toHaveValue("06:00");
    expect(screen.getByLabelText(/Ollama model/)).toHaveValue("gemma3:4b");
  });

  it("shows an error state when /settings fails", async () => {
    server.use(
      http.get("*/settings", () =>
        HttpResponse.json({ detail: "db locked" }, { status: 500 }),
      ),
    );
    render(<SettingsPage />);

    const alerts = await screen.findAllByRole("alert");
    expect(alerts.some((el) => /db locked/.test(el.textContent ?? ""))).toBe(
      true,
    );
  }, 10000);

  it("saves edits and echoes the updated values", async () => {
    render(<SettingsPage />);

    await waitFor(() =>
      expect(screen.getByLabelText("VIP people")).toHaveValue("Riya"),
    );

    fireEvent.change(screen.getByLabelText("VIP people"), {
      target: { value: "Riya, Kabir" },
    });
    fireEvent.change(screen.getByLabelText("Extra keywords"), {
      target: { value: "biryani, verify" },
    });

    fireEvent.click(screen.getByRole("button", { name: /save settings/i }));

    await waitFor(() =>
      expect(screen.getByText(SAVED_ALERT_TEXT)).toBeInTheDocument(),
    );
    expect(screen.getByLabelText("VIP people")).toHaveValue("Riya, Kabir");
    expect(screen.getByLabelText("Extra keywords")).toHaveValue(
      "biryani, verify",
    );
  }, 10000);
});
