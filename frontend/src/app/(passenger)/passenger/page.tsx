"use client";

import { Bell, MapPin, Route, Ticket } from "lucide-react";

import { DashboardPlaceholder } from "@/components/dashboard-placeholder";

export default function PassengerDashboard() {
  return (
    <DashboardPlaceholder
      greeting="Passenger dashboard"
      tiles={[
        {
          icon: MapPin,
          title: "Live nearby",
          description: "See buses and stops around you, updated in real time.",
        },
        {
          icon: Route,
          title: "Plan a trip",
          description: "Route planning with predictive arrival times.",
        },
        {
          icon: Bell,
          title: "Arrival alerts",
          description: "Get notified before your ride reaches your stop.",
        },
        {
          icon: Ticket,
          title: "Saved routes",
          description: "Pin the lines you ride most for one-tap access.",
        },
      ]}
    />
  );
}
