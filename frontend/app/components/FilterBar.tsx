"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { type FilterState, useFilters } from "../lib/filters";
import { humanize } from "../lib/format";

const RANGES: { value: FilterState["days"]; label: string }[] = [
  { value: 7, label: "7 days" },
  { value: 30, label: "30 days" },
  { value: 90, label: "90 days" },
  { value: "all", label: "All" },
];

/** The one filter row: date range first, then segment filters. Scopes everything below it. */
export function FilterBar({ hideRange = false, note }: { hideRange?: boolean; note?: string }) {
  const { filters, setFilter, reset, activeCount } = useFilters();
  const optionsQuery = useQuery({ queryKey: ["filters-options"], queryFn: api.filters, staleTime: 300_000 });
  const options = optionsQuery.data;

  return (
    <div className="filter-bar" role="group" aria-label="Filters">
      {!hideRange && (
        <div className="segmented" role="group" aria-label="Date range">
          {RANGES.map((range) => (
            <button
              key={String(range.value)}
              type="button"
              aria-pressed={filters.days === range.value}
              onClick={() => setFilter("days", range.value)}
            >
              {range.label}
            </button>
          ))}
        </div>
      )}
      {(["product", "channel", "country", "city"] as const).map((dimension) => (
        <label key={dimension}>
          <span className="visually-hidden">{dimension}</span>
          <select value={filters[dimension]} onChange={(event) => setFilter(dimension, event.target.value)}>
            <option value="">All {dimension === "country" ? "countries" : dimension === "city" ? "cities" : `${dimension}s`}</option>
            {options?.[dimension].map((value) => (
              <option key={value} value={value}>
                {dimension === "channel" ? humanize(value) : value}
              </option>
            ))}
          </select>
        </label>
      ))}
      {activeCount > 0 && (
        <button type="button" className="link-button small" onClick={reset}>
          Clear filters
        </button>
      )}
      {note && <span className="muted tiny" style={{ marginLeft: "auto" }}>{note}</span>}
    </div>
  );
}
