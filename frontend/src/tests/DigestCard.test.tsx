import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import DigestCard from "../components/DigestCard";
import { sampleDigest } from "../mocks/sampleDigest";

describe("DigestCard", () => {
  it("renders a digest group with all headline sections", () => {
    const group = sampleDigest.groups[0]!;
    render(<DigestCard group={group} />);

    expect(
      screen.getByRole("article", { name: /digest for weekend trip/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Weekend trip planning 🏔️")).toBeInTheDocument();
    expect(screen.getByText(group.tldr)).toBeInTheDocument();
    expect(screen.getByText(/needs you \(2\)/i)).toBeInTheDocument();
    expect(screen.getByText("Decisions")).toBeInTheDocument();
    expect(screen.getByText("By person")).toBeInTheDocument();
    expect(screen.getByText("Deadlines")).toBeInTheDocument();
  });

  it("shows suggested reply flagged as draft only", () => {
    const group = sampleDigest.groups[0]!;
    render(<DigestCard group={group} />);

    const replyLabels = screen.getAllByText(
      /suggested reply \(draft only, never sent\)/i,
    );
    expect(replyLabels.length).toBeGreaterThanOrEqual(2);
    expect(
      screen.getByText(
        "I can drive, +1 passenger seat free. Pick the venue and I'm in.",
      ),
    ).toBeInTheDocument();
  });

  it("toggles the skipped-banter disclosure", () => {
    render(<DigestCard group={sampleDigest.groups[1]!} />);

    const button = screen.getByRole("button", {
      name: /show skipped/i,
    });
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(
      screen.queryByText(/skipped 171 low-value messages/i),
    ).not.toBeInTheDocument();

    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByText(/skipped 171 low-value messages/i),
    ).toBeInTheDocument();
  });

  it("shows an empty needs-you state when nothing needs the user", () => {
    const emptyGroup = {
      ...sampleDigest.groups[1]!,
      needs_you: [],
      deadlines: [],
      decisions: [],
    };
    render(<DigestCard group={emptyGroup} />);

    expect(screen.getByText(/nothing needs you/i)).toBeInTheDocument();
    expect(screen.queryByText("Decisions")).not.toBeInTheDocument();
    expect(screen.queryByText("Deadlines")).not.toBeInTheDocument();
  });
});
