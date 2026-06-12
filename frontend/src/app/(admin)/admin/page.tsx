"use client";

import Link from "next/link";
import { ArrowRight, Bus, Map, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { AdminKpis } from "@/components/admin-kpis";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useMe } from "@/hooks/use-auth";

export default function AdminDashboard() {
  const { user } = useMe();
  const firstName = user?.full_name?.split(" ")[0];

  return (
    <div className="grid gap-8">
      <section>
        <p className="label-mono text-xs text-muted-foreground">Operator console</p>
        <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight text-balance">
          {firstName ? `Welcome, ${firstName}.` : "Welcome."}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          A live read on the network — today&apos;s ridership, revenue, and fleet — plus quick
          access to manage routes, the fleet, and drivers.
        </p>
      </section>

      <AdminKpis />

      <section className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
        <p className="label-mono col-span-full text-xs text-muted-foreground">Manage</p>
        <ManageCard
          href="/admin/routes"
          icon={Map}
          title="Routes"
          description="Create and edit routes and their ordered stops."
        />
        <ManageCard
          href="/admin/buses"
          icon={Bus}
          title="Buses"
          description="Register vehicles, assign drivers, and flag maintenance."
        />
        <ManageCard
          href="/admin/drivers"
          icon={Users}
          title="Drivers"
          description="Add and manage driver accounts."
        />
      </section>
    </div>
  );
}

function ManageCard({
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
