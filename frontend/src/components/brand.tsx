import { TrainFront } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/utils";

/** Compact brand lockup used in headers and the auth panel. */
export function Brand({
  className,
  invert = false,
  href = "/",
}: {
  className?: string;
  invert?: boolean;
  /** Where the lockup links to. Defaults to the public landing page. */
  href?: string;
}) {
  return (
    <Link
      href={href}
      aria-label="Smart Transit home"
      className={cn(
        "flex items-center gap-2.5 rounded-lg transition-opacity hover:opacity-80",
        className,
      )}
    >
      <span
        className={cn(
          "grid size-8 place-items-center rounded-lg",
          invert
            ? "bg-accent text-accent-foreground"
            : "bg-primary text-primary-foreground",
        )}
      >
        <TrainFront className="size-[1.05rem]" />
      </span>
      <span className="flex flex-col leading-none">
        <span
          className={cn(
            "font-display text-[0.95rem] font-semibold tracking-tight",
            invert ? "text-white" : "text-foreground",
          )}
        >
          Smart Transit
        </span>
        <span
          className={cn(
            "label-mono text-[0.55rem] font-medium",
            invert ? "text-accent" : "text-muted-foreground",
          )}
        >
          AI Platform
        </span>
      </span>
    </Link>
  );
}
