"use client";

import Link from "next/link";
import { ArrowRight, MapPin, Route as RouteIcon } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useMe } from "@/hooks/use-auth";

export default function PassengerDashboard() {
  const { user } = useMe();
  const firstName = user?.full_name?.split(" ")[0];

  return (
    <div className="grid gap-8">
      <section>
        <p className="label-mono text-xs text-muted-foreground">Passenger</p>
        <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight text-balance">
          {firstName ? `Welcome, ${firstName}.` : "Welcome."}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Explore the transit network — browse every route and find stops near you.
        </p>
      </section>

      <section className="grid gap-3.5 sm:grid-cols-2">
        <BrowseCard
          href="/passenger/routes"
          icon={RouteIcon}
          title="Routes"
          description="See every line, search by name, and open a route for its stops in order."
        />
        <BrowseCard
          href="/passenger/stops"
          icon={MapPin}
          title="Stops"
          description="Find stops by name or route, or show the ones closest to you."
        />
      </section>
    </div>
  );
}

function BrowseCard({
  href,
  icon: Icon,
  title,
  description,
}: {
  href: string;
  icon: LucideIcon;
  title: string;
  description: string;
}) {
  return (
    <Link href={href} className="group">
      <Card className="h-full transition-colors group-hover:border-foreground/20 group-hover:bg-muted/30">
        <CardHeader>
          <span className="grid size-10 place-items-center rounded-lg bg-secondary text-secondary-foreground transition-colors group-hover:bg-accent group-hover:text-accent-foreground">
            <Icon className="size-5" />
          </span>
          <CardTitle className="mt-3 flex items-center justify-between text-base">
            {title}
            <ArrowRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground text-pretty">{description}</p>
        </CardContent>
      </Card>
    </Link>
  );
}
