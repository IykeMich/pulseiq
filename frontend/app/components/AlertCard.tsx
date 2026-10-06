import Link from "next/link";
import type { Alert } from "../lib/api";
import { formatPercent, humanize } from "../lib/format";
import { SeverityBadge } from "./Badges";

/** One early-warning alert: what changed, how sure we are, where it concentrates, what to do. */
export function AlertCard({ alert, compact = false }: { alert: Alert; compact?: boolean }) {
  const isAspect = alert.scope !== "overall";
  return (
    <article className={`alert-card alert-${alert.severity}`}>
      <div className="spread">
        <div className="row">
          <SeverityBadge severity={alert.severity} />
          <strong>{alert.name}</strong>
        </div>
        {isAspect && (
          <Link href={`/issues/${alert.scope}`} className="small nowrap">
            Investigate →
          </Link>
        )}
      </div>
      <p className="small">{alert.headline}</p>
      {!compact && (
        <>
          <p className="muted tiny num">
            Last 7 days: {alert.current.negative}/{alert.current.mentions} negative ({formatPercent(alert.current.negative_rate)}) ·
            previous 28 days: {formatPercent(alert.baseline.negative_rate)} · z = {alert.z_score.toFixed(1)}
          </p>
          {alert.drivers.length > 0 && (
            <p className="tiny secondary">
              Over-represented:{" "}
              {alert.drivers
                .map((driver) => `${humanize(driver.dimension)} ${driver.value} (${formatPercent(driver.share_of_negatives, 0)} of negatives, was ${formatPercent(driver.baseline_share_of_negatives, 0)})`)
                .join("; ")}
            </p>
          )}
        </>
      )}
    </article>
  );
}
