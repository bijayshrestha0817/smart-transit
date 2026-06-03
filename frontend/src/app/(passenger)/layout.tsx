import { DashboardShell } from "@/components/dashboard-shell";

export default function PassengerLayout({ children }: { children: React.ReactNode }) {
  return <DashboardShell role="passenger">{children}</DashboardShell>;
}
