"use client";

import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { MailCheck } from "lucide-react";

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
import { forgotPassword } from "@/lib/api/auth";
import { ApiError, toApiError } from "@/lib/api/error";
import type { DetailPayload } from "@/lib/api/types";
import {
  forgotPasswordSchema,
  type ForgotPasswordValues,
} from "@/lib/validation/auth";

export default function ForgotPasswordPage() {
  const form = useForm<ForgotPasswordValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
  });

  const mutation = useMutation<DetailPayload, ApiError, string>({
    mutationFn: forgotPassword,
    onError: (err) => toApiError(err),
  });

  return (
    <AuthShell
      title="Reset your password"
      subtitle={
        mutation.isSuccess
          ? undefined
          : "Enter your email and we'll send a reset link if an account exists."
      }
      footer={
        <Link href="/login" className="font-medium text-foreground underline-offset-4 hover:underline">
          Back to sign in
        </Link>
      }
    >
      {mutation.isSuccess ? (
        <div className="grid gap-4">
          <div className="grid size-12 place-items-center rounded-xl border bg-muted/40">
            <MailCheck className="size-6 text-chart-5" />
          </div>
          <div className="grid gap-1.5">
            <h2 className="font-display text-lg font-semibold">Check your inbox</h2>
            <p className="text-sm text-muted-foreground text-pretty">
              If that account exists, a password reset link is on its way. The
              link expires shortly, so use it soon.
            </p>
          </div>
        </div>
      ) : (
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit((values) => mutation.mutate(values.email))}
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

            <Button type="submit" size="lg" className="mt-1 w-full" disabled={mutation.isPending}>
              {mutation.isPending ? "Sending link…" : "Send reset link"}
            </Button>
          </form>
        </Form>
      )}
    </AuthShell>
  );
}
