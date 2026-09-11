import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Login from "../pages/Login";
import { getToken, setToken } from "../api/client";

beforeEach(() => setToken(null));
afterEach(() => {
  vi.unstubAllGlobals();
  setToken(null);
});

function mockAuth(ok: boolean, body: unknown = { access_token: "t", token_type: "bearer", expires_in_minutes: 60 }) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok, status: ok ? 200 : 401, json: async () => body } as Response)
  );
}

describe("Login", () => {
  it("offers account creation on a fresh install", () => {
    render(<Login status={{ auth_required: true, has_users: false }} onAuthenticated={vi.fn()} />);

    expect(screen.getByText("Create the first account")).toBeInTheDocument();
    expect(screen.getByText(/registration closes afterwards/i)).toBeInTheDocument();
  });

  it("offers sign-in once an account exists", () => {
    render(<Login status={{ auth_required: true, has_users: true }} onAuthenticated={vi.fn()} />);

    // "Sign in" is both the subtitle and the button label, so assert on the
    // absence of the setup copy instead of an ambiguous text match.
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
    expect(screen.queryByText("Create the first account")).not.toBeInTheDocument();
    expect(screen.queryByText(/registration closes/i)).not.toBeInTheDocument();
  });

  it("stores the token and signals success", async () => {
    mockAuth(true);
    const onAuthenticated = vi.fn();
    render(<Login status={{ auth_required: true, has_users: true }} onAuthenticated={onAuthenticated} />);

    await userEvent.type(screen.getByLabelText(/email/i), "a@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "correct-horse-battery");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(onAuthenticated).toHaveBeenCalled());
    expect(getToken()).toBe("t");
  });

  it("surfaces a rejection without storing a token", async () => {
    mockAuth(false, { detail: "Incorrect email or password." });
    render(<Login status={{ auth_required: true, has_users: true }} onAuthenticated={vi.fn()} />);

    await userEvent.type(screen.getByLabelText(/email/i), "a@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password.");
    expect(getToken()).toBeNull();
  });

  it("keeps submission disabled until both fields are filled", async () => {
    render(<Login status={{ auth_required: true, has_users: true }} onAuthenticated={vi.fn()} />);
    const button = screen.getByRole("button", { name: /sign in/i });

    expect(button).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/email/i), "a@example.com");
    expect(button).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/password/i), "pw");
    expect(button).toBeEnabled();
  });
});
