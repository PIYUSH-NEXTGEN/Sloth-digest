import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "../App";

describe("App", () => {
  it("renders the header, navigation and the digest page", async () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "SlothDigest" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Sleep through the chat. Wake up caught up."),
    ).toBeInTheDocument();
    expect(screen.getByRole("navigation")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: /morning digest/i }),
      ).toBeInTheDocument(),
    );
  });

  it("renders one digest card per group with long/emoji names", async () => {
    render(<App />);

    await waitFor(() =>
      expect(
        screen.getByRole("article", { name: /weekend trip/i }),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("article", { name: /sunday-cricket-squad/i }),
    ).toBeInTheDocument();
  });
});
