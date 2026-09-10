import StatusBadge, { type BadgeTone } from "./StatusBadge";

interface Props {
  label: string;
  /** null renders an explicit unavailable state rather than a zero. */
  value: number | string | null;
  unit?: string;
  note?: string;
  /** Shown when value is null — why the number is missing. */
  unavailableReason?: string;
  tone?: BadgeTone;
  toneLabel?: string;
}

export default function MetricCard({
  label, value, unit, note, unavailableReason, tone, toneLabel,
}: Props) {
  const isUnavailable = value === null;

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
        <p className="metric-card__label">{label}</p>
        {tone && toneLabel && <StatusBadge tone={tone}>{toneLabel}</StatusBadge>}
      </div>

      {isUnavailable ? (
        <p className="metric-card__value metric-card__value--unavailable">Unavailable</p>
      ) : (
        <p className="metric-card__value">
          {value}
          {unit && <span className="metric-card__unit">{unit}</span>}
        </p>
      )}

      {(isUnavailable ? unavailableReason : note) && (
        <p className="metric-card__note">{isUnavailable ? unavailableReason : note}</p>
      )}
    </div>
  );
}
