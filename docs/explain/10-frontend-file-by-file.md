# 10 · Frontend tour, file by file

```text
frontend/
├── index.html            the single HTML page
├── vite.config.ts        build + dev proxy + test config
├── tsconfig.json         TypeScript rules
├── package.json          dependencies and scripts
└── src/
    ├── main.tsx          entry point — mounts React, wraps providers
    ├── App.tsx           auth gate + routing table
    ├── navigation.ts     the sidebar definition
    ├── format.ts         presentation helpers
    ├── index.css         base styles
    ├── styles/tokens.css the design system
    ├── api/client.ts     the ONLY file that makes network calls
    ├── state/            shared state and the async hook
    ├── components/       reusable UI
    ├── pages/            one file per screen
    └── __tests__/        component and unit tests
```

---

## Entry points

**`main.tsx`** mounts React and establishes the provider nesting:

```tsx
<BrowserRouter>
  <AuthProvider>
    <FilterProvider>
      <App />
    </FilterProvider>
  </AuthProvider>
</BrowserRouter>
```

Order matters: routing outermost, then auth, then filters. `AuthProvider` must be
inside the router because the login flow may navigate.

**`App.tsx`** is the auth gate plus the routing table:

```tsx
if (loading || status === null) return <div>Loading…</div>;
if (!isAuthenticated) return <Login status={status} onAuthenticated={refresh} />;
return <Routes>…</Routes>;
```

Nothing renders until the server has said whether auth is required. Rendering
the app first and redirecting later would flash protected chrome on screen.

---

## `api/client.ts` — the network boundary

The single file allowed to call `fetch`. Everything else goes through it
(`rules.md` §14).

Three responsibilities:

**1. Typed interfaces** mirroring the backend's Pydantic schemas —
`ServiceDoraMetrics`, `DeliveryDetail`, `EvidencePackage`, and so on.

**2. Token handling:**

```ts
function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
```

Storage is wrapped in `try/catch` because private browsing can deny
`localStorage`. Signing in still works; the session just does not survive a
reload — better than failing to sign in at all.

**3. Uniform error handling:**

```ts
if (response.status === 401) {
  setToken(null);          // expired or revoked
  throw new ApiError("Your session has expired. Please sign in again.", 401);
}
```

Clearing the token makes the shell fall back to the login screen instead of
looping on failed requests.

---

## `state/`

| File | Purpose |
|---|---|
| `useAsync.ts` | Loading / success / error as a union type, with cancellation |
| `FilterContext.tsx` | The shared look-back window |
| `AuthContext.tsx` | Whether auth is required and whether we have a token |

`AuthContext` has one deliberate detail:

```tsx
fetchAuthStatus()
  .then(setStatus)
  .catch(() => setStatus({ auth_required: true, has_users: true }))
```

If the status endpoint itself is unreachable, **assume auth is required**. Fail
closed: it is better to show a login screen you cannot use than to render the
app as though it were open.

---

## `components/`

### Layout

| File | Renders |
|---|---|
| `AppShell.tsx` | Sidebar + sticky top bar + `<Outlet />`, mobile drawer state |
| `Sidebar.tsx` | Grouped navigation from `navigation.ts` |
| `layout.css` | Shell layout and the responsive breakpoints |

### UI primitives

| File | Purpose |
|---|---|
| `PageHeader.tsx` | Title, description, action slot |
| `StatusBadge.tsx` | A tone + **always** a text label |
| `MetricCard.tsx` | A metric, or an explicit unavailable state |
| `Banner.tsx` | Persistent caveats |
| `States.tsx` | `LoadingState`, `EmptyState`, `ErrorState`, `NotYetAvailable` |
| `AnomalyList.tsx` | Anomaly cards with baseline/current/change |
| `ui.css` | Component styles, all referencing tokens |

**`MetricCard` is where the honesty rule lives in the UI:**

```tsx
{isUnavailable ? (
  <p className="metric-card__value--unavailable">Unavailable</p>
) : (
  <p className="metric-card__value">{value}{unit}</p>
)}
```

`value={null}` renders **"Unavailable"** plus a reason. `value={0}` renders
**"0"**. There is a test asserting both, because these must never converge.

**`States.tsx`** keeps three situations distinct:

```text
EmptyState        the query ran and found nothing
ErrorState        something went wrong (with a retry)
NotYetAvailable   DevPulse cannot answer this question yet
```

---

## `pages/`

| Page | Data source | Shows |
|---|---|---|
| `Overview.tsx` | `/metrics/dora` | Aggregate DORA + "not yet measured" |
| `Repositories.tsx` | `/repositories` | Activity, last sync, coverage drill-down |
| `Dora.tsx` | `/metrics/dora` | Five metrics per service + source badge |
| `Deliveries.tsx` | `/deliveries` | List → full trace with correlation evidence |
| `Bottlenecks.tsx` | `/bottlenecks`, `/anomalies` | Anomalies + decomposed scores |
| `Health.tsx` | `/conflicts`, `/health-score` | Conflicts + five dimensions |
| `Analysis.tsx` | `/analysis/*` | Evidence package, then AI on request |
| `Integrations.tsx` | `/repositories` | Provider connection state |
| `Settings.tsx` | `/repositories` | Deployment rules, window, environment |
| `Login.tsx` | `/auth/*` | Sign in, or bootstrap the first account |
| `Planned.tsx` | — | Shared component for unbuilt capabilities |

`Planned.tsx` is worth noting even though nothing uses it now: during
development, pages without an engine rendered a **PLANNED** state naming the
stage that would build them, with no numbers at all (ADR-017). Placeholder
charts are indistinguishable from real data on screen, and a product built on
"evidence before inference" cannot ship invented numbers. Every page now has a
real engine, but the component remains for the next unbuilt capability.

`Overview.tsx` contains a subtle correctness detail:

```tsx
const measurable = services.filter((s) => s.deployment_source !== "NONE");
```

Services with no deployment source are **excluded from aggregates**, not counted
as zero. Averaging in a zero would drag the whole picture down because of a
missing integration.

---

## `format.ts`

Presentation helpers with one rule: **`null` always renders as `—`**.

```ts
export const UNAVAILABLE = "—";

export function formatHours(hours: number | null): string {
  if (hours === null) return UNAVAILABLE;
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 48) return `${hours.toFixed(1)}h`;
  return `${(hours / 24).toFixed(1)}d`;
}
```

A test asserts `formatHours(0)` returns `"0m"`, not `"—"`. Zero is a real
measurement — it is what the broken lead-time metric actually produced, and
hiding it would have concealed the defect.

---

## `navigation.ts`

The sidebar is data, not markup:

```ts
{ path: "/deliveries", label: "Deliveries", icon: "⇉", hasData: true }
```

`hasData` drove a `SOON` badge while pages were unbuilt — the interface openly
advertising how much of the product was incomplete. An engineering audience
trusts a tool that states its limits far more than one that hides them.

---

**Next:** [11 · Docker, Compose and CI](11-docker-and-ci.md)
