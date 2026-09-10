interface EmptyProps {
  icon?: string;
  title: string;
  body: string;
  action?: React.ReactNode;
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="state-block" role="status" aria-live="polite">
      <div className="skeleton" style={{ width: 180, height: 10, marginBottom: 12 }} />
      <div className="skeleton" style={{ width: 120, height: 10 }} />
      <span style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>
        {label}
      </span>
    </div>
  );
}

export function EmptyState({ icon = "◍", title, body, action }: EmptyProps) {
  return (
    <div className="state-block">
      <div className="state-block__icon" aria-hidden="true">{icon}</div>
      <p className="state-block__title">{title}</p>
      <p className="state-block__body">{body}</p>
      {action && <div className="state-block__actions">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  return (
    <div className="state-block" role="alert">
      <div className="state-block__icon" aria-hidden="true">⚠</div>
      <p className="state-block__title">Something went wrong</p>
      <p className="state-block__body">{error.message}</p>
      {onRetry && (
        <div className="state-block__actions">
          <button className="button" onClick={onRetry}>Try again</button>
        </div>
      )}
    </div>
  );
}

/**
 * A capability that does not exist yet. This is deliberately distinct from an
 * empty state: empty means "no data found", this means "DevPulse cannot answer
 * this question yet". Presenting the second as the first would overstate what
 * the backend knows (AGENTS.md 12).
 */
export function NotYetAvailable({
  title, body, stage,
}: { title: string; body: string; stage: string }) {
  return (
    <div className="state-block">
      <div className="state-block__icon" aria-hidden="true">◌</div>
      <p className="state-block__title">{title}</p>
      <p className="state-block__body">{body}</p>
      <div className="state-block__actions">
        <span className="badge badge--neutral">Planned · {stage}</span>
      </div>
    </div>
  );
}
