import PageHeader from "../components/ui/PageHeader";
import { NotYetAvailable } from "../components/ui/States";

interface PlannedPageProps {
  title: string;
  description: string;
  body: string;
  stage: string;
  requires: string[];
}

/**
 * A page whose engine does not exist yet.
 *
 * These deliberately show nothing rather than placeholder numbers. Rendering
 * invented deliveries or a fabricated health score would make the UI claim more
 * than the backend knows, which rules.md 11 and AGENTS.md 12 both forbid — and
 * it is the single easiest way for a demo to become dishonest.
 */
export default function PlannedPage({
  title, description, body, stage, requires,
}: PlannedPageProps) {
  return (
    <>
      <PageHeader title={title} description={description} />
      <NotYetAvailable title={`${title} is not available yet`} body={body} stage={stage} />

      <section className="section" style={{ marginTop: "var(--space-8)" }}>
        <h2 className="section__title">What this needs first</h2>
        <div className="card">
          <ul style={{ margin: 0, paddingLeft: "var(--space-5)", color: "var(--text-secondary)", fontSize: 13 }}>
            {requires.map((requirement) => (
              <li key={requirement} style={{ marginBottom: "var(--space-2)" }}>{requirement}</li>
            ))}
          </ul>
        </div>
      </section>
    </>
  );
}
