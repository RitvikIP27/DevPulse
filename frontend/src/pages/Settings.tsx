import PageHeader from "../components/ui/PageHeader";
import Banner from "../components/ui/Banner";
import { useFilters } from "../state/FilterContext";

export default function Settings() {
  const { windowDays, setWindowDays } = useFilters();

  return (
    <>
      <PageHeader
        title="Settings"
        description="How this DevPulse instance is configured."
      />

      <Banner tone="info" title="Configuration is environment-driven for now">
        Tracked repositories and credentials come from <code>backend/.env</code>.
        Managing them from the interface requires repository CRUD and encrypted
        credential storage, which arrive with the integrations model.
      </Banner>

      <section className="section">
        <h2 className="section__title">Analysis window</h2>
        <div className="card">
          <label htmlFor="settings-window" style={{ display: "block", marginBottom: "var(--space-3)", fontSize: 13, color: "var(--text-secondary)" }}>
            Default look-back window used across metric pages.
          </label>
          <select
            id="settings-window"
            className="select"
            value={windowDays}
            onChange={(event) => setWindowDays(Number(event.target.value))}
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>
      </section>

      <section className="section">
        <h2 className="section__title">Environment</h2>
        <div className="card scroll-x">
          <table className="data-table">
            <thead><tr><th>Setting</th><th>Source</th><th>Value</th></tr></thead>
            <tbody>
              <tr><td>Tracked repositories</td><td className="mono">GITHUB_REPOS</td><td style={{ color: "var(--text-muted)" }}>Set in backend/.env</td></tr>
              <tr><td>GitHub credentials</td><td className="mono">GITHUB_TOKEN</td><td style={{ color: "var(--text-muted)" }}>Never displayed</td></tr>
              <tr><td>Database</td><td className="mono">DATABASE_URL</td><td style={{ color: "var(--text-muted)" }}>Never displayed</td></tr>
              <tr><td>Schema</td><td className="mono">alembic</td><td>Migrations applied at container start</td></tr>
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
