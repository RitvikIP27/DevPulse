import { useEffect, useState, useCallback } from "react";
import { fetchDoraMetrics, triggerSync, type ServiceDoraMetrics } from "./api/client";
import ServiceMetricsTable from "./components/ServiceMetricsTable";
import DoraChart from "./components/DoraChart";
import "./App.css";

export default function App() {
  const [services, setServices] = useState<ServiceDoraMetrics[]>([]);
  const [windowDays, setWindowDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDoraMetrics(windowDays);
      setServices(data.services);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load metrics");
    } finally {
      setLoading(false);
    }
  }, [windowDays]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSync() {
    setSyncing(true);
    try {
      await triggerSync();
      // Ingestion runs in the background; give it a moment before refreshing.
      setTimeout(load, 3000);
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>DevPulse</h1>
        <p className="subtitle">Engineering Intelligence &amp; DORA Metrics Dashboard</p>
      </header>

      <div className="controls">
        <label>
          Window:{" "}
          <select value={windowDays} onChange={(e) => setWindowDays(Number(e.target.value))}>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </label>
        <button onClick={handleSync} disabled={syncing}>
          {syncing ? "Syncing…" : "Sync from GitHub"}
        </button>
      </div>

      {loading && <p>Loading metrics…</p>}
      {error && <p className="error">{error}</p>}

      {!loading && !error && (
        <>
          <section>
            <h2>Per-Service Bottleneck Comparison</h2>
            <ServiceMetricsTable services={services} />
          </section>

          <section>
            <h2>Change Failure Rate by Service</h2>
            <DoraChart services={services} />
          </section>
        </>
      )}
    </div>
  );
}
