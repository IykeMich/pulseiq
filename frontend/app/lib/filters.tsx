"use client";

import { createContext, useContext, useMemo, useState } from "react";

/** Global filters: every chart, stat and table on every page reads the same slice. */
export type FilterState = {
  days: number | "all";
  product: string;
  channel: string;
  country: string;
  city: string;
};

const DEFAULT_FILTERS: FilterState = { days: 30, product: "", channel: "", country: "", city: "" };

type FiltersContextValue = {
  filters: FilterState;
  setFilter: <Key extends keyof FilterState>(key: Key, value: FilterState[Key]) => void;
  reset: () => void;
  /** The filters as a query string for the API, e.g. "days=30&product=RideGo". */
  query: string;
  activeCount: number;
};

const FiltersContext = createContext<FiltersContextValue | null>(null);

export function toQuery(filters: FilterState): string {
  const params = new URLSearchParams();
  if (filters.days === "all") params.set("all", "true");
  else params.set("days", String(filters.days));
  for (const key of ["product", "channel", "country", "city"] as const) {
    if (filters[key]) params.set(key, filters[key]);
  }
  return params.toString();
}

export function FiltersProvider({ children }: { children: React.ReactNode }) {
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const value = useMemo<FiltersContextValue>(
    () => ({
      filters,
      setFilter: (key, filterValue) => setFilters((previous) => ({ ...previous, [key]: filterValue })),
      reset: () => setFilters(DEFAULT_FILTERS),
      query: toQuery(filters),
      activeCount: (["product", "channel", "country", "city"] as const).filter((key) => filters[key]).length,
    }),
    [filters],
  );
  return <FiltersContext.Provider value={value}>{children}</FiltersContext.Provider>;
}

export function useFilters(): FiltersContextValue {
  const context = useContext(FiltersContext);
  if (!context) throw new Error("useFilters must be used inside FiltersProvider");
  return context;
}
