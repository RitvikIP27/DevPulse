export type BadgeTone = "success" | "warning" | "danger" | "info" | "neutral";

interface Props {
  tone: BadgeTone;
  children: React.ReactNode;
}

/**
 * Colour is never the only carrier of meaning (Design.md 2): the badge always
 * renders a text label alongside its tone.
 */
export default function StatusBadge({ tone, children }: Props) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}
