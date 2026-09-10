# DevPulse — Design System

**Visual direction:** Dark, modern, technical, mature, high-signal.

DevPulse should look like a serious engineering platform rather than a generic SaaS dashboard.

---

# 1. Design Principles

## 1.1 Dense but readable

Engineering users need information density.

Use:

- compact cards
- strong hierarchy
- restrained decoration
- clear data labels
- generous spacing between logical sections

Avoid:

- giant marketing-style cards
- excessive gradients
- excessive rounded containers
- decorative animations
- noisy dashboards

---

## 1.2 Dark-first

Default theme is dark.

The interface should feel:

```text
observability platform
+
developer tooling
+
premium infrastructure product
```

Think:

- deep graphite background
- slightly lighter surfaces
- cool neutral borders
- bright but restrained accent colors

---

# 2. Color System

Use CSS variables.

```css
:root {
  --bg-primary: #080b10;
  --bg-secondary: #0d1117;
  --bg-tertiary: #121821;

  --surface: #151b24;
  --surface-elevated: #1a2230;

  --border: #273140;
  --border-subtle: #1d2530;

  --text-primary: #f3f6fa;
  --text-secondary: #a8b3c2;
  --text-muted: #6f7b8c;

  --accent: #6ee7ff;
  --accent-soft: #16323b;

  --success: #4ade80;
  --warning: #facc15;
  --danger: #fb7185;
  --info: #60a5fa;
}
```

Do not use color alone to communicate state.

Always combine color with:

- label
- icon
- status
- text

---

# 3. Typography

Primary font:

```text
Inter
```

Fallback:

```text
system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
```

Optional technical/data font:

```text
JetBrains Mono
```

Use monospace for:

- commit SHA
- IDs
- API paths
- timestamps when dense
- technical identifiers

Hierarchy:

```text
Page title:      28–32px / 700
Section title:   18–22px / 650
Card title:      14–16px / 600
Body:            14px / 400–500
Secondary:       12–13px
Metric:          26–36px / 700
```

---

# 4. Spacing

Use a consistent 4px/8px-based system.

Preferred values:

```text
4
8
12
16
20
24
32
40
48
64
```

Do not invent arbitrary spacing values repeatedly.

---

# 5. Radius

Use restrained rounding:

```text
small controls: 6px
cards:           10px
large panels:    12px
```

Avoid pill-shaped UI unless it represents a status/tag.

---

# 6. Shadows

Keep shadows subtle.

Dark interfaces should primarily use:

- surface contrast
- borders
- elevation changes

rather than heavy shadows.

---

# 7. Layout

Desktop:

```text
┌──────────────┬──────────────────────────────┐
│ Sidebar      │ Main                         │
│              │                              │
│ Overview     │ Page header                  │
│ Repositories │                              │
│ DORA         │ Content                      │
│ Deliveries   │                              │
│ Bottlenecks  │                              │
│ Health       │                              │
│ Analysis     │                              │
│ Integrations │                              │
│ Settings     │                              │
└──────────────┴──────────────────────────────┘
```

Sidebar:

```text
240–260px
```

Main content:

```text
max-width: 1440px
padding: 24–40px
```

---

# 8. Responsive Breakpoints

Use:

```text
mobile:  < 640px
tablet:  640–1023px
desktop: ≥ 1024px
wide:    ≥ 1440px
```

## Mobile

- sidebar becomes drawer
- one-column cards
- horizontally scrollable tables where required
- important metrics remain visible
- avoid tiny charts

## Tablet

- 2-column metric grids
- collapsible sidebar
- responsive pipeline visualizations

## Desktop

- multi-column analytics
- persistent navigation
- timeline + evidence side-by-side where appropriate

---

# 9. Component Patterns

Core components:

```text
AppShell
Sidebar
TopBar
PageHeader
MetricCard
StatusBadge
HealthScore
TrendIndicator
DataTable
EmptyState
ErrorState
LoadingState
FilterBar
DateRangePicker
RepositorySelector
PipelineTimeline
StageCard
BottleneckCard
AnomalyCard
EvidencePanel
IntegrationCard
```

Components should be reusable and composable.

---

# 10. Metric Cards

A metric card should contain:

```text
label
value
unit
trend
comparison
optional status
```

Example:

```text
CHANGE LEAD TIME

3.4h

↓ 18% vs previous period
```

Avoid meaningless decoration.

---

# 11. Pipeline Visualization

Use a horizontal pipeline on desktop:

```text
PR
 ↓
CI
 ↓
Build
 ↓
Deploy
 ↓
Runtime
```

Each stage should communicate:

- status
- duration
- provider
- anomaly
- bottleneck state

On mobile, switch to a vertical timeline.

---

# 12. Status Semantics

Success:

```text
green
```

Warning:

```text
yellow
```

Failure:

```text
red/pink
```

Informational:

```text
blue
```

Neutral:

```text
gray
```

Do not overuse danger colors.

---

# 13. Charts

Charts should prioritize:

- readability
- baseline comparison
- trend direction
- anomalies
- labels

Preferred:

- line charts
- bar charts
- distribution plots
- stage-duration charts

Avoid 3D charts and decorative chart effects.

---

# 14. Motion

Animation should be subtle.

Use motion for:

- drawer opening
- panel transitions
- loading
- state changes

Do not animate every metric.

Engineering dashboards should feel stable.

---

# 15. Visual Identity

DevPulse should feel:

> **precise, calm, technical, premium and slightly futuristic.**

It should not feel:

> flashy, gaming-inspired, neon-heavy, crypto-like or consumer-social.

Use the accent color sparingly so important information has visual priority.
