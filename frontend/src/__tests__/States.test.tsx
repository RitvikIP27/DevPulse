import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { EmptyState, ErrorState, LoadingState, NotYetAvailable } from "../components/ui/States";

describe("async screen states", () => {
  it("announces loading to assistive technology", () => {
    render(<LoadingState />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("shows an empty state with guidance", () => {
    render(<EmptyState title="No repositories tracked" body="Set GITHUB_REPOS." />);
    expect(screen.getByText("No repositories tracked")).toBeInTheDocument();
    expect(screen.getByText("Set GITHUB_REPOS.")).toBeInTheDocument();
  });

  it("surfaces the error message and offers a retry", async () => {
    const onRetry = vi.fn();
    render(<ErrorState error={new Error("Could not reach the DevPulse API.")} onRetry={onRetry} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Could not reach the DevPulse API.");
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("marks an unbuilt capability as planned rather than empty", () => {
    // "Not available yet" must not be presented as "no data found" — they mean
    // different things and conflating them overstates what the backend knows.
    render(
      <NotYetAvailable
        title="Deliveries is not available yet"
        body="Nothing ingested carries a commit SHA to correlate on."
        stage="Stage 4"
      />
    );
    expect(screen.getByText(/Planned · Stage 4/)).toBeInTheDocument();
  });
});
