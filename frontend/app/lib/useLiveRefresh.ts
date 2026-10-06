"use client";

import { useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

/** Query keys that never depend on the feedback data, so a new event doesn't refetch them. */
const STATIC_KEYS = new Set(["stream-status", "model", "quality", "health", "filters-options"]);

/**
 * Polls GET /stream/status. When the data version changes (a live or replayed event was processed),
 * every data query is marked stale and refetches: the dashboard "reads the latest state".
 */
export function useLiveRefresh() {
  const queryClient = useQueryClient();
  const statusQuery = useQuery({
    queryKey: ["stream-status"],
    queryFn: api.streamStatus,
    refetchInterval: (query) => (query.state.data?.replay.running || query.state.data?.queue_depth ? 1500 : 3000),
    retry: false,
  });
  const lastVersion = useRef<number | null>(null);
  const version = statusQuery.data?.version;

  useEffect(() => {
    if (version === undefined) return;
    if (lastVersion.current !== null && version !== lastVersion.current) {
      queryClient.invalidateQueries({
        predicate: (query) => !STATIC_KEYS.has(String(query.queryKey[0])),
      });
    }
    lastVersion.current = version;
  }, [version, queryClient]);

  return statusQuery;
}
