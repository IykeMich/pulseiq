"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api, API_BASE_URL } from "../lib/api";
import { useLiveRefresh } from "../lib/useLiveRefresh";

const NAV = [
  { group: "Monitor", links: [
    { href: "/", label: "Overview" },
    { href: "/trends", label: "Sentiment trends" },
    { href: "/aspects", label: "Aspect explorer" },
    { href: "/feedback", label: "Feedback explorer" },
  ] },
  { group: "Analyze", links: [
    { href: "/analyze", label: "Analyze text" },
    { href: "/model", label: "Model & data" },
  ] },
  { group: "Project", links: [{ href: "/about", label: "Project details" }] },
];

/** Sidebar navigation + API and stream status. Also hosts the live-refresh poller for every page. */
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const healthQuery = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 15_000, retry: false });
  const streamQuery = useLiveRefresh();
  const connection = healthQuery.isPending ? "checking" : healthQuery.isSuccess ? "online" : "offline";
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));
  const streaming = streamQuery.data && (streamQuery.data.replay.running || streamQuery.data.queue_depth > 0);

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">P</span>
          <div>
            <strong>PulseIQ</strong>
            <span className="muted tiny">Customer Pulse</span>
          </div>
        </div>
        <nav className="nav" aria-label="Main">
          {NAV.map((section) => (
            <div key={section.group} className="nav">
              <span className="nav-label">{section.group}</span>
              {section.links.map((link) => (
                <Link key={link.href} href={link.href} aria-current={isActive(link.href) ? "page" : undefined}>
                  {link.label}
                </Link>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className={`status-pill status-${connection}`} title={API_BASE_URL}>
            <span className="status-dot" aria-hidden="true" />
            {connection === "checking" ? "Checking API…" : connection === "online" ? "API online" : "API offline"}
          </span>
          {healthQuery.data && <span className="muted tiny">Model {healthQuery.data.model_version}</span>}
          {streaming && (
            <span className="status-pill">
              <span className="live-dot" aria-hidden="true" />
              Processing events…
            </span>
          )}
        </div>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
