"use client";

import { QueryClient, QueryClientProvider, keepPreviousData } from "@tanstack/react-query";
import { useState } from "react";
import { FiltersProvider } from "./lib/filters";

/** One shared TanStack Query cache plus the global filters, for every page. */
export function Providers({ children }: { children: React.ReactNode }) {
  // keepPreviousData: while a filter change refetches, charts keep their last render (no flash).
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30_000, refetchOnWindowFocus: false, placeholderData: keepPreviousData },
        },
      }),
  );
  return (
    <QueryClientProvider client={queryClient}>
      <FiltersProvider>{children}</FiltersProvider>
    </QueryClientProvider>
  );
}
