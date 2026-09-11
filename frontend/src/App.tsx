import { Navigate, Route, Routes } from "react-router-dom";
import Login from "./pages/Login";
import { useAuth } from "./state/AuthContext";
import AppShell from "./components/layout/AppShell";
import Overview from "./pages/Overview";
import Repositories from "./pages/Repositories";
import Dora from "./pages/Dora";
import Deliveries from "./pages/Deliveries";
import Bottlenecks from "./pages/Bottlenecks";
import Health from "./pages/Health";
import Analysis from "./pages/Analysis";
import Integrations from "./pages/Integrations";
import Settings from "./pages/Settings";
import "./components/ui/ui.css";

export default function App() {
  const { status, loading, isAuthenticated, refresh } = useAuth();

  // Nothing is rendered until the server has said whether auth is required.
  // Rendering the app first and redirecting later would flash protected chrome.
  if (loading || status === null) {
    return <div style={{ padding: 40, color: "var(--text-muted)" }}>Loading…</div>;
  }

  if (!isAuthenticated) {
    return <Login status={status} onAuthenticated={refresh} />;
  }

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Overview />} />
        <Route path="repositories" element={<Repositories />} />
        <Route path="dora" element={<Dora />} />
        <Route path="deliveries" element={<Deliveries />} />
        <Route path="bottlenecks" element={<Bottlenecks />} />
        <Route path="health" element={<Health />} />
        <Route path="analysis" element={<Analysis />} />
        <Route path="integrations" element={<Integrations />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
