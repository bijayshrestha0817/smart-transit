import { DashboardShell } from "@/components/dashboard-shell";

export default function DriverLayout({ children }: { children: React.ReactNode }) {
  return <DashboardShell role="driver">{children}</DashboardShell>;
}
