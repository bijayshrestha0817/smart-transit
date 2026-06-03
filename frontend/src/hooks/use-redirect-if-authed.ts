"use client";

/**
 * Bounce already-authenticated users away from auth pages to their dashboard.
 * Used by login/register etc. so a logged-in user never sees the sign-in form.
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { dashboardPath } from "@/lib/auth-routes";
import { useMe } from "@/hooks/use-auth";

export function useRedirectIfAuthed() {
  const router = useRouter();
  const { user, isResolved } = useMe();

  useEffect(() => {
    if (isResolved && user) {
      router.replace(dashboardPath(user.role));
    }
  }, [isResolved, user, router]);

  return { isResolved, user };
}
