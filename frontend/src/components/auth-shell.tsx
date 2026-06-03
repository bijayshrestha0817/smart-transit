import Link from "next/link";

import { Brand } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";

const HIGHLIGHTS = [
  { code: "ETA", label: "Predictive arrivals" },
  { code: "GPS", label: "Live vehicle tracking" },
  { code: "OPS", label: "Operator dashboards" },
];

/**
 * Split-screen auth scaffold. The left panel carries the brand and a "departure
 * board" backdrop; the right column hosts the form. Collapses to a single column
 * on small screens with a slim branded header.
 */
export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="grid min-h-dvh w-full lg:grid-cols-[1.05fr_1fr]">
      {/* Brand panel */}
      <aside className="transit-grid relative hidden flex-col justify-between overflow-hidden p-10 lg:flex">
        <Link href="/">
          <Brand invert />
        </Link>

        <div className="relative z-10 max-w-md">
          <p className="label-mono text-xs text-accent">Now boarding</p>
          <h2 className="mt-3 font-display text-3xl font-semibold leading-tight text-white text-balance">
            Move the city with intelligence in every arrival.
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-white/70">
            Real-time tracking, predictive ETAs, and operator tooling — one
            platform for passengers, drivers, and transit operators.
          </p>

          <dl className="mt-10 grid grid-cols-3 gap-px overflow-hidden rounded-xl border border-white/10 bg-white/5">
            {HIGHLIGHTS.map((item) => (
              <div key={item.code} className="bg-white/[0.03] px-4 py-4">
                <dt className="font-display text-lg font-semibold text-accent">
                  {item.code}
                </dt>
                <dd className="mt-1 text-[0.7rem] leading-tight text-white/60">
                  {item.label}
                </dd>
              </div>
            ))}
          </dl>
        </div>

        <p className="relative z-10 label-mono text-[0.6rem] text-white/40">
          Smart Transit AI · Platform 01
        </p>
      </aside>

      {/* Form column */}
      <main className="relative flex flex-col">
        <header className="flex items-center justify-between p-5 lg:justify-end lg:p-6">
          <Link href="/" className="lg:hidden">
            <Brand />
          </Link>
          <ThemeToggle />
        </header>

        <div className="flex flex-1 items-center justify-center px-5 pb-12 sm:px-8">
          <div className="w-full max-w-sm">
            <div className="mb-7">
              <h1 className="font-display text-2xl font-semibold tracking-tight text-balance">
                {title}
              </h1>
              {subtitle ? (
                <p className="mt-2 text-sm text-muted-foreground text-pretty">
                  {subtitle}
                </p>
              ) : null}
            </div>

            {children}

            {footer ? (
              <div className="mt-6 text-center text-sm text-muted-foreground">
                {footer}
              </div>
            ) : null}
          </div>
        </div>
      </main>
    </div>
  );
}
