import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { Brand } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-5 py-5 sm:px-8">
        <Brand />
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Button asChild variant="ghost" size="sm">
            <Link href="/login">Sign in</Link>
          </Button>
        </div>
      </header>

      <main className="relative flex flex-1 items-center overflow-hidden">
        <div className="pointer-events-none absolute inset-0 -z-10 opacity-[0.18] [background-image:repeating-linear-gradient(125deg,var(--border)_0px,var(--border)_1px,transparent_1px,transparent_52px)]" />
        <div className="mx-auto w-full max-w-6xl px-5 py-16 sm:px-8">
          <div className="max-w-2xl">
            <p className="label-mono text-xs text-muted-foreground">
              Real-time transit intelligence
            </p>
            <h1 className="mt-4 font-display text-4xl font-semibold leading-[1.05] tracking-tight text-balance sm:text-6xl">
              Every arrival, predicted.
              <br />
              <span className="text-muted-foreground">Every route, in motion.</span>
            </h1>
            <p className="mt-6 max-w-xl text-base leading-relaxed text-muted-foreground text-pretty">
              Smart Transit AI brings live vehicle tracking, predictive ETAs, and
              operator tooling together — for passengers, drivers, and the teams
              that keep the city moving.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <Button asChild size="lg">
                <Link href="/register">
                  Get started <ArrowRight className="size-4" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link href="/login">I have an account</Link>
              </Button>
            </div>
          </div>
        </div>
      </main>

      <footer className="mx-auto w-full max-w-6xl px-5 py-6 sm:px-8">
        <p className="label-mono text-[0.6rem] text-muted-foreground/70">
          Smart Transit AI · P0 shell
        </p>
      </footer>
    </div>
  );
}
