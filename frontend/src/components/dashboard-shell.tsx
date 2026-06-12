"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { Brand } from "@/components/brand";
import { LogoutButton } from "@/components/logout-button";
import { NotificationBell } from "@/components/notification-bell";
import { ThemeToggle } from "@/components/theme-toggle";
import type { UserRole } from "@/lib/api/types";
import { dashboardPath } from "@/lib/auth-routes";
import { cn } from "@/lib/utils";
import { useMe } from "@/hooks/use-auth";

const ROLE_LABEL: Record<UserRole, string> = {
  passenger: "Passenger",
  driver: "Driver",
  admin: "Operator",
};

/** Primary nav per role. */
const NAV_BY_ROLE: Record<UserRole, { href: string; label: string }[]> = {
  passenger: [
    { href: "/passenger/routes", label: "Routes" },
    { href: "/passenger/stops", label: "Stops" },
    { href: "/passenger/tickets", label: "Tickets" },
    { href: "/passenger/wallet", label: "Wallet" },
  ],
  driver: [
    { href: "/driver", label: "Trips" },
    { href: "/driver/notifications", label: "Notifications" },
  ],
  admin: [
    { href: "/admin/routes", label: "Routes" },
    { href: "/admin/buses", label: "Buses" },
    { href: "/admin/drivers", label: "Drivers" },
    { href: "/admin/trips", label: "Trips" },
    { href: "/admin/fleet", label: "Fleet" },
  ],
};

/** The role's nav links, shared by the desktop bar and the mobile strip. */
function NavLinks({ role, pathname }: { role: UserRole; pathname: string }) {
  return (
    <>
      {NAV_BY_ROLE[role].map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm whitespace-nowrap transition-colors",
              active
                ? "bg-muted font-medium text-foreground"
                : "text-muted-foreground hover:bg-muted/50 hover:text-foreground",
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </>
  );
}

/**
 * Client-side guard + chrome for the role dashboards.
 *
 * `useMe` is the source of truth here: the proxy already blocked anonymous users
 * by cookie presence, but this layer confirms the *role* and bounces a user who
 * landed on the wrong dashboard to their own. The backend independently enforces
 * RBAC on every API call, so this is UX, not the security boundary.
 */
export function DashboardShell({
  role,
  children,
}: {
  role: UserRole;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isLoading, isResolved } = useMe();

  useEffect(() => {
    if (!isResolved) return;
    if (!user) {
      router.replace("/login");
    } else if (user.role !== role) {
      router.replace(dashboardPath(user.role));
    }
  }, [isResolved, user, role, router]);

  if (isLoading || !user || user.role !== role) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-30 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-5 py-3.5 sm:px-8">
          <div className="flex items-center gap-3">
            <Brand href={dashboardPath(role)} />
            <span className="label-mono hidden rounded-md border bg-muted/50 px-2 py-1 text-[0.6rem] text-muted-foreground sm:inline-block">
              {ROLE_LABEL[role]}
            </span>
            <nav className="ml-1 hidden items-center gap-0.5 md:flex">
              <NavLinks role={role} pathname={pathname} />
            </nav>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden text-sm text-muted-foreground sm:inline">
              {user.email}
            </span>
            <NotificationBell />
            <ThemeToggle />
            <LogoutButton />
          </div>
        </div>
        {/* Mobile nav strip — the desktop bar's links are md+ only, so without this
            the navbar would be invisible on narrow screens. */}
        <nav className="flex items-center gap-0.5 overflow-x-auto border-t px-4 py-2 md:hidden">
          <NavLinks role={role} pathname={pathname} />
        </nav>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-5 py-8 sm:px-8 sm:py-10">
        {children}
      </main>
    </div>
  );
}
