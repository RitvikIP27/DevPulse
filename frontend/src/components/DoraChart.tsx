import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { ServiceDoraMetrics } from "../api/client";

interface Props {
  services: ServiceDoraMetrics[];
}

export default function DoraChart({ services }: Props) {
  if (services.length === 0) return null;

  return (
    <div style={{ width: "100%", height: 300 }}>
      <ResponsiveContainer>
        <BarChart data={services} margin={{ top: 16, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="service" tick={{ fontSize: 12 }} />
          <YAxis label={{ value: "Change Failure Rate (%)", angle: -90, position: "insideLeft" }} />
          <Tooltip />
          <Bar dataKey="change_failure_rate_pct" radius={[4, 4, 0, 0]}>
            {services.map((s) => (
              <Cell key={s.service} fill={s.change_failure_rate_pct >= 20 ? "#d9534f" : "#2e8b57"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
