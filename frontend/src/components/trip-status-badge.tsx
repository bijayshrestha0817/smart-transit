import { Badge } from "@/components/ui/badge";
import type { TripStatus } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<TripStatus, string> = {
  scheduled: "bg-sky-500/15 text-sky-700 dark:text-sky-400",
  in_progress: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  completed: "bg-muted text-muted-foreground",
  cancelled: "bg-destructive/10 text-destructive",
};

const STATUS_LABEL: Record<TripStatus, string> = {
  scheduled: "Scheduled",
  in_progress: "In progress",
  completed: "Completed",
  cancelled: "Cancelled",
};

export function TripStatusBadge({
  status,
  className,
}: {
  status: TripStatus;
  className?: string;
}) {
  return (
    <Badge className={cn(STATUS_STYLES[status], className)}>{STATUS_LABEL[status]}</Badge>
  );
}
