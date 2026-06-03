"use client";

/**
 * App-wide client providers: TanStack Query, next-themes, and the Sonner toaster.
 *
 * Also registers the Axios auth-failure handler here (once, on mount) so the
 * axios module stays framework-agnostic: when a refresh ultimately fails, the
 * interceptor pushes the user to /login via this bridge.
 */

import { useEffect, useRef, useState } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";

import { registerAuthFailureHandler } from "@/lib/axios";
import { makeQueryClient } from "@/lib/queryClient";
import { useAuthStore } from "@/stores/auth";
import { Toaster } from "@/components/ui/sonner";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(makeQueryClient);
  const clear = useAuthStore((s) => s.clear);
  const registered = useRef(false);

  useEffect(() => {
    if (registered.current) return;
    registered.current = true;
    registerAuthFailureHandler(() => {
      clear();
      // Full navigation guarantees the protected page unmounts immediately.
      if (typeof window !== "undefined" && window.location.pathname !== "/login") {
        window.location.assign("/login");
      }
    });
  }, [clear]);

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        attribute="class"
        defaultTheme="system"
        enableSystem
        disableTransitionOnChange
      >
        {children}
        <Toaster position="top-center" richColors />
      </ThemeProvider>
    </QueryClientProvider>
  );
}
