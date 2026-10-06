"use client";

import { useState } from "react";

type LegendItem = { label: string; color: string; shape?: "line" | "box" };

/**
 * Card around a chart: title, legend (always present for 2+ series), and a table view so every
 * value is reachable without hovering or relying on color.
 */
export function ChartFrame({
  title,
  subtitle,
  legend,
  table,
  actions,
  children,
  dimmed,
}: {
  title: string;
  subtitle?: React.ReactNode;
  legend?: LegendItem[];
  table?: { columns: string[]; rows: (string | number)[][] };
  actions?: React.ReactNode;
  children: React.ReactNode;
  dimmed?: boolean;
}) {
  const [showTable, setShowTable] = useState(false);
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">{title}</h2>
          {subtitle && <p className="panel-subtitle">{subtitle}</p>}
        </div>
        <div className="row">
          {actions}
          {table && (
            <button type="button" className="link-button small" onClick={() => setShowTable((value) => !value)}>
              {showTable ? "Show chart" : "Show table"}
            </button>
          )}
        </div>
      </div>
      {legend && legend.length > 1 && !showTable && (
        <div className="legend" style={{ marginBottom: 8 }}>
          {legend.map((item) => (
            <span key={item.label}>
              {item.shape === "line" ? (
                <span className="line-key" style={{ background: item.color, margin: 0 }} />
              ) : (
                <span className="swatch" style={{ background: item.color }} />
              )}
              {item.label}
            </span>
          ))}
        </div>
      )}
      <div className={dimmed ? "loading-dim" : undefined}>
        {showTable && table ? (
          <div className="table-wrap" style={{ maxHeight: 320, overflowY: "auto" }}>
            <table>
              <thead>
                <tr>
                  {table.columns.map((column, index) => (
                    <th key={column} className={index > 0 ? "num" : undefined}>
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {table.rows.map((row, rowIndex) => (
                  <tr key={rowIndex}>
                    {row.map((cell, cellIndex) => (
                      <td key={cellIndex} className={cellIndex > 0 ? "num" : undefined}>
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          children
        )}
      </div>
    </section>
  );
}
