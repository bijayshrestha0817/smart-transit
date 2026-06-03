"use client";

import { LogOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useLogout } from "@/hooks/use-auth";

export function LogoutButton() {
  const logout = useLogout();

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() => logout.mutate()}
      disabled={logout.isPending}
    >
      <LogOut className="size-4" />
      {logout.isPending ? "Signing out…" : "Sign out"}
    </Button>
  );
}
