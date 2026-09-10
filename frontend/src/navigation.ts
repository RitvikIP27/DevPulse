/**
 * Single definition of the product's navigation (PRD 2.15).
 *
 * `hasData` records whether a page is backed by a real engine today. The
 * sidebar surfaces this so the interface never implies a capability the backend
 * does not have (AGENTS.md 12).
 */
export interface NavItem {
  path: string;
  label: string;
  icon: string;
  hasData: boolean;
}

export interface NavSection {
  label: string;
  items: NavItem[];
}

export const NAV_SECTIONS: NavSection[] = [
  {
    label: "Deliver",
    items: [
      { path: "/", label: "Overview", icon: "▤", hasData: true },
      { path: "/repositories", label: "Repositories", icon: "◫", hasData: true },
      { path: "/dora", label: "DORA", icon: "◷", hasData: true },
      { path: "/deliveries", label: "Deliveries", icon: "⇉", hasData: true },
    ],
  },
  {
    label: "Analyze",
    items: [
      { path: "/bottlenecks", label: "Bottlenecks", icon: "⧗", hasData: true },
      { path: "/health", label: "Health", icon: "◎", hasData: false },
      { path: "/analysis", label: "Analysis", icon: "✦", hasData: false },
    ],
  },
  {
    label: "Configure",
    items: [
      { path: "/integrations", label: "Integrations", icon: "⇄", hasData: true },
      { path: "/settings", label: "Settings", icon: "⚙", hasData: true },
    ],
  },
];
