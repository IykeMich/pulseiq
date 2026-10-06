import type { Metadata } from "next";
import { Providers } from "./providers";
import { AppShell } from "./components/AppShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "PulseIQ Customer Pulse",
  description: "Sentiment and behavioral intelligence over customer feedback",
};

/** Root layout for every page: query cache + filters, inside the sidebar shell. */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
