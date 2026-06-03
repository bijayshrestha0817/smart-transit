"use client";

import { Bus, Map, ShieldCheck, Users } from "lucide-react";

import { DashboardPlaceholder } from "@/components/dashboard-placeholder";

export default function AdminDashboard() {
  return (
    <DashboardPlaceholder
      greeting="Operator console"
      tiles={[
        {
          icon: Map,
          title: "Routes & stops",
          description: "Define and manage the network's routes and stops.",
        },
        {
          icon: Bus,
          title: "Fleet",
          description: "Register vehicles and monitor their live status.",
        },
        {
          icon: Users,
          title: "Accounts",
          description: "Manage passengers, drivers, and operator access.",
        },
        {
          icon: ShieldCheck,
          title: "System health",
          description: "Service metrics and operational alerts at a glance.",
        },
      ]}
    />
  );
}
