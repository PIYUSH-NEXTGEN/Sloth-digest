import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "../App";

describe("App navigation", () => {
  it("navigates to Sources and shows the upload box", async () => {
    render(<App />);

    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: /morning digest/i }),
      ).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Sources" }));

    await waitFor(() =>
      expect(screen.getByText("Weekend trip planning 🏔️")).toBeInTheDocument(),
    );
    expect(
      screen.getByText(/imported locally, nothing is sent anywhere/i),
    ).toBeInTheDocument();
  });

  it("keeps digest cards accessible after navigating back", async () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Sources" }));
    await waitFor(() =>
      expect(screen.getByText(/weekend trip planning/i)).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Digest" }));
    await waitFor(() =>
      expect(
        screen.getByRole("article", { name: /weekend trip/i }),
      ).toBeInTheDocument(),
    );
  });

  it("navigates to Settings and loads the current values", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    const names = await screen.findByLabelText("Your names & aliases");
    await waitFor(() => expect(names).toHaveValue("Priya, prids"));
  });
});
