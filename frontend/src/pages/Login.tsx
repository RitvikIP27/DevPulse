import { useState } from "react";
import { login, register, type AuthStatus } from "../api/client";

interface Props {
  status: AuthStatus;
  onAuthenticated: () => void;
}

export default function Login({ status, onAuthenticated }: Props) {
  // With no account yet, this is a fresh install bootstrapping its first user.
  const isSetup = !status.has_users;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await (isSetup ? register(email, password) : login(email, password));
      onAuthenticated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 24 }}>
      <div className="card" style={{ width: "100%", maxWidth: 400 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
          <div className="sidebar__mark" aria-hidden="true">◈</div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700 }}>DevPulse</div>
            <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
              {isSetup ? "Create the first account" : "Sign in"}
            </div>
          </div>
        </div>

        {isSetup && (
          <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 0 }}>
            No account exists yet. The first account you create becomes the owner,
            and registration closes afterwards.
          </p>
        )}

        <form onSubmit={submit}>
          <label htmlFor="email" style={{ display: "block", fontSize: 12, color: "var(--text-muted)", marginBottom: 6 }}>
            Email
          </label>
          <input
            id="email" type="email" required autoComplete="username"
            className="select" style={{ width: "100%", cursor: "text", marginBottom: 16 }}
            value={email} onChange={(e) => setEmail(e.target.value)}
          />

          <label htmlFor="password" style={{ display: "block", fontSize: 12, color: "var(--text-muted)", marginBottom: 6 }}>
            Password
          </label>
          <input
            id="password" type="password" required
            autoComplete={isSetup ? "new-password" : "current-password"}
            minLength={isSetup ? 12 : undefined}
            className="select" style={{ width: "100%", cursor: "text", marginBottom: 8 }}
            value={password} onChange={(e) => setPassword(e.target.value)}
          />
          {isSetup && (
            <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 0 }}>
              At least 12 characters.
            </p>
          )}

          {error && (
            <p role="alert" style={{ color: "var(--danger)", fontSize: 13 }}>{error}</p>
          )}

          <button
            className="button button--primary"
            style={{ width: "100%", marginTop: 12, padding: "10px 16px" }}
            disabled={busy || !email || !password}
          >
            {busy ? "…" : isSetup ? "Create account" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
