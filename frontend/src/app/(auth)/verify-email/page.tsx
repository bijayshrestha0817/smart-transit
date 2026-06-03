"use client";

import { Suspense, useEffect, useRef } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, Loader2, MailWarning } from "lucide-react";

import { AuthShell } from "@/components/auth-shell";
import { Button } from "@/components/ui/button";
import { verifyEmail } from "@/lib/api/auth";
import { ApiError, toApiError } from "@/lib/api/error";
import type { DetailPayload } from "@/lib/api/types";

function VerifyEmailInner() {
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const started = useRef(false);

  const mutation = useMutation<DetailPayload, ApiError, string>({
    mutationFn: verifyEmail,
    onError: (err) => toApiError(err),
  });

  // Auto-verify once on mount when a token is present.
  useEffect(() => {
    if (token && !started.current) {
      started.current = true;
      mutation.mutate(token);
    }
  }, [token, mutation]);

  if (!token) {
    return (
      <State
        icon={<MailWarning className="size-6 text-destructive" />}
        title="No verification token"
        body="This link is missing its verification token. Open the link from your email exactly as sent."
        action={<LinkButton href="/login">Back to sign in</LinkButton>}
      />
    );
  }

  if (mutation.isPending || mutation.isIdle) {
    return (
      <State
        icon={<Loader2 className="size-6 animate-spin text-muted-foreground" />}
        title="Verifying your email…"
        body="Hang tight while we confirm your account."
      />
    );
  }

  if (mutation.isSuccess) {
    return (
      <State
        icon={<CheckCircle2 className="size-6 text-chart-5" />}
        title="Email verified"
        body="Your account is ready. You can sign in now."
        action={<LinkButton href="/login">Continue to sign in</LinkButton>}
      />
    );
  }

  const error = toApiError(mutation.error);
  const expired = error.has("token_expired");

  return (
    <State
      icon={<MailWarning className="size-6 text-destructive" />}
      title={expired ? "Link expired" : "Invalid link"}
      body={
        expired
          ? "This verification link has expired. Sign in to request a fresh one."
          : "This verification link is invalid. Request a new link from the sign-in screen."
      }
      action={<LinkButton href="/login">Back to sign in</LinkButton>}
    />
  );
}

function State({
  icon,
  title,
  body,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="grid gap-4">
      <div className="grid size-12 place-items-center rounded-xl border bg-muted/40">
        {icon}
      </div>
      <div className="grid gap-1.5">
        <h2 className="font-display text-lg font-semibold">{title}</h2>
        <p className="text-sm text-muted-foreground text-pretty">{body}</p>
      </div>
      {action}
    </div>
  );
}

function LinkButton({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Button asChild size="lg" className="mt-1 w-full">
      <Link href={href}>{children}</Link>
    </Button>
  );
}

export default function VerifyEmailPage() {
  return (
    <AuthShell title="Email verification">
      <Suspense
        fallback={
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" /> Loading…
          </div>
        }
      >
        <VerifyEmailInner />
      </Suspense>
    </AuthShell>
  );
}
