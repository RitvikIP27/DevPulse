import { createContext, useContext, useMemo, useState } from "react";

interface FilterValue {
  windowDays: number;
  setWindowDays: (days: number) => void;
}

const FilterContext = createContext<FilterValue | null>(null);

/**
 * The look-back window is shared by several pages, so it lives above them rather
 * than being duplicated into each one (rules.md 14).
 */
export function FilterProvider({ children }: { children: React.ReactNode }) {
  const [windowDays, setWindowDays] = useState(30);
  const value = useMemo(() => ({ windowDays, setWindowDays }), [windowDays]);
  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>;
}

export function useFilters(): FilterValue {
  const context = useContext(FilterContext);
  if (!context) {
    throw new Error("useFilters must be used within a FilterProvider");
  }
  return context;
}
