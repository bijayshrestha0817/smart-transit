"use client";

import type { LucideIcon } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { User } from "@/lib/api/types";
import { useMe } from "@/hooks/use-auth";

interface Tile {
  icon: LucideIcon;
  title: string;
  description: string;
}

/**
 * Shared dashboard body for the P0 shell. Confirms the logged-in identity and
 * lays out "coming soon" feature tiles. Domain UI lands in later phases.
 */
export function DashboardPlaceholder({
  greeting,
  tiles,
}: {
  greeting: string;
  tiles: Tile[];
}) {
  const { user } = useMe();
  if (!user) return null;

  return (
    <div className="grid gap-8">
      <section>
        <p className="label-mono text-xs text-muted-foreground">{greeting}</p>
        <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight text-balance">
          {displayName(user)}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          You&apos;re signed in. Your tools are being assembled — here&apos;s
          what&apos;s coming.
        </p>
      </section>

      <section className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
        {tiles.map((tile) => (
          <Card key={tile.title} className="group relative overflow-hidden">
            <span className="absolute right-4 top-4 label-mono text-[0.55rem] text-muted-foreground/70">
              Soon
            </span>
            <CardHeader>
              <span className="grid size-10 place-items-center rounded-lg bg-secondary text-secondary-foreground transition-colors group-hover:bg-accent group-hover:text-accent-foreground">
                <tile.icon className="size-5" />
              </span>
              <CardTitle className="mt-3 text-base">{tile.title}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground text-pretty">
                {tile.description}
              </p>
            </CardContent>
          </Card>
        ))}
      </section>

      <AccountSummary user={user} />
    </div>
  );
}

function AccountSummary({ user }: { user: User }) {
  const rows: Array<[string, string]> = [
    ["Email", user.email],
    ["Role", user.role],
    ["Phone", user.phone || "—"],
    ["Verified", user.is_verified ? "Yes" : "No"],
    ["Member since", formatDate(user.created_at)],
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Account</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
          {rows.map(([label, value]) => (
            <div key={label} className="flex items-center justify-between gap-4 border-b border-dashed py-1.5 last:border-0">
              <dt className="label-mono text-[0.6rem] text-muted-foreground">{label}</dt>
              <dd className="truncate text-sm font-medium">{value}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}

function displayName(user: User): string {
  if (user.full_name) return `Welcome, ${user.full_name.split(" ")[0]}.`;
  return "Welcome.";
}

function formatDate(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}
