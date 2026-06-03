"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { AuthShell } from "@/components/auth-shell";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { login } from "@/lib/api/auth";
import { ApiError, toApiError } from "@/lib/api/error";
import type { User } from "@/lib/api/types";
import { dashboardPath } from "@/lib/auth-routes";
import { loginSchema, type LoginValues } from "@/lib/validation/auth";
import { useRedirectIfAuthed } from "@/hooks/use-redirect-if-authed";

function LoginForm() {
  useRedirectIfAuthed();
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next");

  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const mutation = useMutation<User, ApiError, LoginValues>({
    mutationFn: login,
    onSuccess: (user) => {
      toast.success("Welcome back.");
      const dest = next && next.startsWith("/") ? next : dashboardPath(user.role);
      router.replace(dest);
      router.refresh();
    },
    onError: (err) => {
      const apiError = toApiError(err);
      if (apiError.has("invalid_credentials")) {
        form.setError("password", { message: "Email or password is incorrect." });
        toast.error("Email or password is incorrect.");
      } else if (apiError.has("not_verified")) {
        toast.error("Please verify your email before signing in.", {
          description: "Check your inbox for the verification link.",
        });
      } else {
        toast.error(apiError.message);
      }
    },
  });

  return (
    <AuthShell
      title="Sign in"
      subtitle="Access your Smart Transit AI dashboard."
      footer={
        <>
          New here?{" "}
          <Link href="/register" className="font-medium text-foreground underline-offset-4 hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
          className="grid gap-4"
          noValidate
        >
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Email</FormLabel>
                <FormControl>
                  <Input
                    type="email"
                    autoComplete="email"
                    placeholder="you@transit.app"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <div className="flex items-center justify-between">
                  <FormLabel>Password</FormLabel>
                  <Link
                    href="/forgot-password"
                    className="text-xs text-muted-foreground underline-offset-4 hover:underline"
                  >
                    Forgot?
                  </Link>
                </div>
                <FormControl>
                  <Input
                    type="password"
                    autoComplete="current-password"
                    placeholder="••••••••"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <Button type="submit" size="lg" className="mt-1 w-full" disabled={mutation.isPending}>
            {mutation.isPending ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </Form>
    </AuthShell>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-dvh items-center justify-center">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
