"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { Brand } from "@/components/brand";
import { LogoutButton } from "@/components/logout-button";
import { ThemeToggle } from "@/components/theme-toggle";
import type { UserRole } from "@/lib/api/types";
import { dashboardPath } from "@/lib/auth-routes";
import { useMe } from "@/hooks/use-auth";

const ROLE_LABEL: Record<UserRole, string> = {
  passenger: "Passenger",
  driver: "Driver",
  admin: "Operator",
};

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
            <Brand />
            <span className="label-mono hidden rounded-md border bg-muted/50 px-2 py-1 text-[0.6rem] text-muted-foreground sm:inline-block">
              {ROLE_LABEL[role]}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden text-sm text-muted-foreground sm:inline">
              {user.email}
            </span>
            <ThemeToggle />
            <LogoutButton />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-5 py-8 sm:px-8 sm:py-10">
        {children}
      </main>
    </div>
  );
}
