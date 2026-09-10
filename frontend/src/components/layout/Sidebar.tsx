import { NavLink } from "react-router-dom";
import { NAV_SECTIONS } from "../../navigation";

interface Props {
  open: boolean;
  onNavigate: () => void;
}

export default function Sidebar({ open, onNavigate }: Props) {
  return (
    <aside className={`sidebar${open ? " sidebar--open" : ""}`} aria-label="Primary">
      <div className="sidebar__brand">
        <div className="sidebar__mark" aria-hidden="true">◈</div>
        <div>
          <div className="sidebar__name">DevPulse</div>
          <div className="sidebar__tagline">Engineering Intelligence</div>
        </div>
      </div>

      <nav className="sidebar__nav">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label}>
            <div className="sidebar__group-label">{section.label}</div>
            {section.items.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === "/"}
                onClick={onNavigate}
                className={({ isActive }) => `nav-item${isActive ? " nav-item--active" : ""}`}
              >
                <span className="nav-item__icon" aria-hidden="true">{item.icon}</span>
                <span>{item.label}</span>
                {/* Navigation states honestly which pages have no engine behind them yet. */}
                {!item.hasData && <span className="nav-item__pending">SOON</span>}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="sidebar__footer">
        Deterministic core · AI deferred
      </div>
    </aside>
  );
}
