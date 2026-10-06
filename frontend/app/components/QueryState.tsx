/** Loading / error placeholders for a query, so every panel fails the same readable way. */
export function QueryState({ isPending, error }: { isPending: boolean; error: Error | null }) {
  if (error) return <p className="error-text small">{error.message}</p>;
  if (isPending) return <p className="muted small">Loading…</p>;
  return null;
}
