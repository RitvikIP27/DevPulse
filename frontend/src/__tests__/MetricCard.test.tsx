import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import MetricCard from "../components/ui/MetricCard";

describe("MetricCard", () => {
  it("shows a value with its unit", () => {
    render(<MetricCard label="Deployment Frequency" value={2.64} unit="/week" />);
    expect(screen.getByText("2.64")).toBeInTheDocument();
    expect(screen.getByText("/week")).toBeInTheDocument();
  });

  it("renders a null value as Unavailable, never as zero", () => {
    render(<MetricCard label="Runtime Health" value={null} />);
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("explains why a value is unavailable", () => {
    render(
      <MetricCard
        label="Runtime Health"
        value={null}
        unavailableReason="No monitoring provider is connected."
      />
    );
    expect(screen.getByText("No monitoring provider is connected.")).toBeInTheDocument();
  });

  it("distinguishes a real zero from unavailable", () => {
    render(<MetricCard label="Open Incidents" value={0} />);
    expect(screen.getByText("0")).toBeInTheDocument();
    expect(screen.queryByText("Unavailable")).not.toBeInTheDocument();
  });
});
