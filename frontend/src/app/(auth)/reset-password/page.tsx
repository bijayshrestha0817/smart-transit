"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { Loader2, ShieldX } from "lucide-react";
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
import { resetPassword } from "@/lib/api/auth";
import { ApiError, toApiError } from "@/lib/api/error";
import type { DetailPayload } from "@/lib/api/types";
import { resetPasswordSchema, type ResetPasswordValues } from "@/lib/validation/auth";

interface ResetVars {
  token: string;
  newPassword: string;
}

function ResetPasswordInner() {
  const params = useSearchParams();
  const router = useRouter();
  const token = params.get("token") ?? "";

  const form = useForm<ResetPasswordValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { new_password: "", confirm_password: "" },
  });

  const mutation = useMutation<DetailPayload, ApiError, ResetVars>({
    mutationFn: ({ token, newPassword }) => resetPassword(token, newPassword),
    onSuccess: () => {
      toast.success("Password reset.", { description: "You can sign in with your new password." });
      router.replace("/login");
    },
    onError: (err) => {
      const apiError = toApiError(err);
      const pwError = apiError.fieldError("new_password");
      if (apiError.has("token_expired") || apiError.has("token_invalid")) {
        // Surface token problems inline so the "request a new link" CTA shows.
        return;
      }
      if (pwError) {
        form.setError("new_password", { message: pwError });
      } else {
        toast.error(apiError.message);
      }
    },
  });

  const tokenError =
    mutation.isError &&
    (toApiError(mutation.error).has("token_expired") ||
      toApiError(mutation.error).has("token_invalid"));

  if (!token) {
    return (
      <BadToken
        title="No reset token"
        body="This link is missing its reset token. Request a new link to continue."
      />
    );
  }

  if (tokenError) {
    const expired = toApiError(mutation.error).has("token_expired");
    return (
      <BadToken
        title={expired ? "Link expired" : "Invalid link"}
        body={
          expired
            ? "This reset link has expired. Request a fresh one to set a new password."
            : "This reset link is invalid. Request a new one to continue."
        }
      />
    );
  }

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit((values) =>
          mutation.mutate({ token, newPassword: values.new_password }),
        )}
        className="grid gap-4"
        noValidate
      >
        <FormField
          control={form.control}
          name="new_password"
          render={({ field }) => (
            <FormItem>
              <FormLabel>New password</FormLabel>
              <FormControl>
                <Input
                  type="password"
                  autoComplete="new-password"
                  placeholder="At least 8 characters"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="confirm_password"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Confirm password</FormLabel>
              <FormControl>
                <Input
                  type="password"
                  autoComplete="new-password"
                  placeholder="Re-enter your password"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button type="submit" size="lg" className="mt-1 w-full" disabled={mutation.isPending}>
          {mutation.isPending ? "Resetting…" : "Reset password"}
        </Button>
      </form>
    </Form>
  );
}

function BadToken({ title, body }: { title: string; body: string }) {
  return (
    <div className="grid gap-4">
      <div className="grid size-12 place-items-center rounded-xl border bg-muted/40">
        <ShieldX className="size-6 text-destructive" />
      </div>
      <div className="grid gap-1.5">
        <h2 className="font-display text-lg font-semibold">{title}</h2>
        <p className="text-sm text-muted-foreground text-pretty">{body}</p>
      </div>
      <Button asChild size="lg" className="mt-1 w-full">
        <Link href="/forgot-password">Request a new link</Link>
      </Button>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <AuthShell
      title="Set a new password"
      subtitle="Choose a strong password for your account."
      footer={
        <Link href="/login" className="font-medium text-foreground underline-offset-4 hover:underline">
          Back to sign in
        </Link>
      }
    >
      <Suspense
        fallback={
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" /> Loading…
          </div>
        }
      >
        <ResetPasswordInner />
      </Suspense>
    </AuthShell>
  );
}
