/** Presentation helpers. Null always renders as an explicit dash, never as zero. */

export const UNAVAILABLE = "—";

export function formatHours(hours: number | null): string {
  if (hours === null) return UNAVAILABLE;
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 48) return `${hours.toFixed(1)}h`;
  return `${(hours / 24).toFixed(1)}d`;
}

export function formatPercent(value: number | null): string {
  return value === null ? UNAVAILABLE : `${value.toFixed(1)}%`;
}

export function formatRelativeDate(iso: string | null): string {
  if (!iso) return UNAVAILABLE;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return UNAVAILABLE;

  const days = Math.floor((Date.now() - then) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days} days ago`;
  const months = Math.floor(days / 30);
  return months === 1 ? "1 month ago" : `${months} months ago`;
}
