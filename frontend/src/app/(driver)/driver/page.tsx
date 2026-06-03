"use client";

import { Gauge, Navigation, Radio, ScrollText } from "lucide-react";

import { DashboardPlaceholder } from "@/components/dashboard-placeholder";

export default function DriverDashboard() {
  return (
    <DashboardPlaceholder
      greeting="Driver dashboard"
      tiles={[
        {
          icon: Navigation,
          title: "Active shift",
          description: "Start a shift and broadcast your location to riders.",
        },
        {
          icon: ScrollText,
          title: "Assigned route",
          description: "Your stops, sequence, and schedule for the day.",
        },
        {
          icon: Gauge,
          title: "On-time status",
          description: "Track how you're tracking against the timetable.",
        },
        {
          icon: Radio,
          title: "Dispatch",
          description: "Messages and updates from operations.",
        },
      ]}
    />
  );
}
