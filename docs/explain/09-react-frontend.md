# 09 · React and the frontend

## What the browser actually runs

A web page is three things:

- **HTML** — structure. Headings, tables, buttons.
- **CSS** — appearance. Colours, spacing, layout.
- **JavaScript** — behaviour. What happens when you click.

The browser reads HTML, applies CSS, and runs JavaScript.

## Why not write HTML by hand?

Imagine the Repositories page in plain JavaScript. You fetch data, then build
each row:

```javascript
const row = document.createElement("tr");
row.innerHTML = "<td>" + repo.full_name + "</td>";
table.appendChild(row);
```

Now the user clicks "Coverage" and a panel should expand. You must find the
right row, insert a panel, remember it is open, and remove it if they click
again. With ten interacting pieces of state this becomes unmanageable — and the
bugs are all of the form *"the screen no longer matches the data"*.

## React's idea

You write a function that **describes what the screen should look like for a
given set of data**. When the data changes, React works out the minimal DOM
changes and applies them.

You never say "insert a row". You say "here is what the table looks like now".

```tsx
export default function StatusBadge({ tone, children }: Props) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}
```

That is a **component**: a function returning markup. The HTML-looking syntax is
**JSX** — JavaScript with markup embedded, compiled to normal function calls.

Components compose:

```tsx
<StatusBadge tone="danger">Elevated</StatusBadge>
```

`tone` and `children` are **props** — inputs to the component, like function
arguments.

## State: data that changes

```tsx
const [expanded, setExpanded] = useState<number | null>(null);
```

`useState` gives you a value and a setter. Calling `setExpanded(5)` tells React
"this changed" and it re-renders with the new value.

`useState` is a **hook** — a function starting with `use` that lets a component
remember things between renders. The rule is that hooks must be called
unconditionally at the top of a component, so React can match them up across
renders.

## Side effects

Fetching data is a **side effect** — it reaches outside the component. That goes
in `useEffect`, which DevPulse wraps in one shared hook,
`frontend/src/state/useAsync.ts`:

```tsx
export function useAsync<T>(load: () => Promise<T>, deps: unknown[]) {
  const [state, setState] = useState<AsyncState<T>>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    run()
      .then((data) => { if (!cancelled) setState({ status: "success", data }); })
      .catch((error) => { if (!cancelled) setState({ status: "error", error }); });
    return () => { cancelled = true; };
  }, [run, nonce]);

  return { state, reload: () => setNonce((n) => n + 1) };
}
```

Two things worth understanding:

**The `cancelled` flag.** If you switch pages while a request is in flight, the
response still arrives — for a component that no longer exists. The cleanup
function (returned from `useEffect`) sets `cancelled = true`, so the late
response is ignored. Without this you get warnings and stale data flashing on
screen.

**The state is a union type**, not separate booleans:

```ts
type AsyncState<T> =
  | { status: "loading" }
  | { status: "error"; error: Error }
  | { status: "success"; data: T };
```

With `isLoading` / `error` / `data` as three independent variables you can
represent impossible combinations — loading *and* error *and* data. With a union
you cannot. And TypeScript will not let you read `.data` until you have checked
`status === "success"`.

This is `rules.md` §14 enforced by the type system: every async screen must
account for loading, success, empty and error.

## TypeScript

JavaScript has no types. This is legal and fails at runtime:

```javascript
const rate = response.change_failure_rate_pct;
rate.toFixed(1);              // crashes if rate is null
```

**TypeScript** adds types checked before the code runs:

```ts
export interface ServiceDoraMetrics {
  service: string;
  change_failure_rate_pct: number | null;
}
```

Now `rate.toFixed(1)` is a **compile error** until you handle the `null`. Given
that DevPulse's whole premise is "metrics can be unavailable", this is not
optional — the type system enforces the honesty rule at every use site.

These interfaces mirror the backend's Pydantic schemas. When the API changes,
`tsc` finds every affected line.

## Routing

DevPulse is a **single-page application**: one HTML file, JavaScript swapping
what is displayed. `react-router-dom` maps URLs to components:

```tsx
<Routes>
  <Route element={<AppShell />}>
    <Route index element={<Overview />} />
    <Route path="repositories" element={<Repositories />} />
    <Route path="dora" element={<Dora />} />
    ...
    <Route path="*" element={<Navigate to="/" replace />} />
  </Route>
</Routes>
```

`AppShell` is a **layout route** — it renders the sidebar and top bar once, with
an `<Outlet />` where the current page goes. The sidebar does not re-render when
you navigate.

`path="*"` catches unknown URLs and redirects home.

## Context: state shared across pages

The look-back window is used by several pages. Passing it down through every
component ("prop drilling") is tedious, so DevPulse uses **context**:

```tsx
export function FilterProvider({ children }) {
  const [windowDays, setWindowDays] = useState(30);
  const value = useMemo(() => ({ windowDays, setWindowDays }), [windowDays]);
  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>;
}

export function useFilters() {
  const context = useContext(FilterContext);
  if (!context) throw new Error("useFilters must be used within a FilterProvider");
  return context;
}
```

Any component can call `useFilters()` regardless of depth. The `throw` turns a
misuse into an immediate, clear error instead of a confusing `undefined`.

`useMemo` prevents creating a new object on every render, which would make every
consumer re-render unnecessarily.

DevPulse has two contexts: `FilterContext` (window) and `AuthContext` (who is
signed in).

## The design system

`frontend/src/styles/tokens.css` defines every colour, spacing and radius as a
**CSS variable**:

```css
:root {
  --bg-primary: #080b10;
  --surface: #151b24;
  --text-primary: #f3f6fa;
  --accent: #6ee7ff;
  --success: #4ade80;
  --danger: #fb7185;
  --space-4: 16px;
  --radius-md: 10px;
}
```

Components reference `var(--danger)`, never `#fb7185`. One file changes the whole
product's appearance, and nothing can drift into a slightly-different red.

Colour is never the only signal — a `StatusBadge` always carries text as well,
so the UI works for colour-blind users.

## Vite

**Vite** is the build tool. In development it serves files instantly and updates
the browser as you save. For production, `npm run build` bundles everything into
a few optimised files in `dist/`.

`vite.config.ts` also sets up a **proxy**: during development the frontend runs
on port 5173 and the backend on 8000. The browser would treat those as different
origins and block the requests. The proxy forwards `/api` calls to the backend so
they appear to come from the same place.

---

**Next:** [10 · Frontend tour, file by file](10-frontend-file-by-file.md)
