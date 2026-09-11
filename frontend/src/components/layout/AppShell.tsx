import { useState } from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import { useFilters } from "../../state/FilterContext";
import { useAuth } from "../../state/AuthContext";
import "./layout.css";

const WINDOW_OPTIONS = [7, 30, 90];

export default function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { windowDays, setWindowDays } = useFilters();
  const { status, signOut } = useAuth();

  return (
    <div className="app-shell">
      <Sidebar open={sidebarOpen} onNavigate={() => setSidebarOpen(false)} />
      {sidebarOpen && (
        <div className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} aria-hidden="true" />
      )}

      <div className="main">
        <div className="topbar">
          <button
            className="button topbar__menu-button"
            onClick={() => setSidebarOpen((open) => !open)}
            aria-label="Toggle navigation"
          >
            ☰
          </button>

          <div className="topbar__filters">
            <label className="topbar__label" htmlFor="window-select">Window</label>
            <select
              id="window-select"
              className="select"
              value={windowDays}
              onChange={(event) => setWindowDays(Number(event.target.value))}
            >
              {WINDOW_OPTIONS.map((days) => (
                <option key={days} value={days}>Last {days} days</option>
              ))}
            </select>
            {status?.auth_required && (
              <button className="button" onClick={signOut}>Sign out</button>
            )}
          </div>
        </div>

        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
