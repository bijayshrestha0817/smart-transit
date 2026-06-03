import { TrainFront } from "lucide-react";

import { cn } from "@/lib/utils";

/** Compact brand lockup used in headers and the auth panel. */
export function Brand({
  className,
  invert = false,
}: {
  className?: string;
  invert?: boolean;
}) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
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
    </div>
  );
}
