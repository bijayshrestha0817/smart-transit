"use client";

import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
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
import { register, type RegisterInput } from "@/lib/api/auth";
import { ApiError, toApiError } from "@/lib/api/error";
import type { User } from "@/lib/api/types";
import { registerSchema, type RegisterValues } from "@/lib/validation/auth";
import { useRedirectIfAuthed } from "@/hooks/use-redirect-if-authed";

export default function RegisterPage() {
  useRedirectIfAuthed();

  const form = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { full_name: "", email: "", phone: "", password: "" },
  });

  const mutation = useMutation<User, ApiError, RegisterInput>({
    mutationFn: register,
    onSuccess: (user) => {
      toast.success("Account created.", {
        description: `We sent a verification link to ${user.email}.`,
      });
      form.reset();
    },
    onError: (err) => {
      const apiError = toApiError(err);
      // Map backend field errors onto the matching form fields.
      let mapped = false;
      for (const field of ["email", "password", "full_name", "phone"] as const) {
        const msg = apiError.fieldError(field);
        if (msg) {
          form.setError(field, { message: msg });
          mapped = true;
        }
      }
      toast.error(mapped ? "Please fix the highlighted fields." : apiError.message);
    },
  });

  return (
    <AuthShell
      title="Create your account"
      subtitle="Join Smart Transit AI in under a minute."
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-foreground underline-offset-4 hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit((values) =>
            mutation.mutate({
              full_name: values.full_name,
              email: values.email,
              password: values.password,
              phone: values.phone || undefined,
            }),
          )}
          className="grid gap-4"
          noValidate
        >
          <FormField
            control={form.control}
            name="full_name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Full name</FormLabel>
                <FormControl>
                  <Input autoComplete="name" placeholder="Ada Lovelace" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

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
            name="phone"
            render={({ field }) => (
              <FormItem>
                <FormLabel>
                  Phone <span className="text-muted-foreground">(optional)</span>
                </FormLabel>
                <FormControl>
                  <Input type="tel" autoComplete="tel" placeholder="+1 555 010 0199" {...field} />
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
                <FormLabel>Password</FormLabel>
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

          <Button type="submit" size="lg" className="mt-1 w-full" disabled={mutation.isPending}>
            {mutation.isPending ? "Creating account…" : "Create account"}
          </Button>
        </form>
      </Form>
    </AuthShell>
  );
}
