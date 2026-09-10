import { Navigate, Route, Routes } from "react-router-dom";
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
