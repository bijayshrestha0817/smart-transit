import { Badge } from "@/components/ui/badge";
import type { AlertSeverity } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const SEVERITY_STYLES: Record<AlertSeverity, string> = {
  info: "bg-sky-500/15 text-sky-700 dark:text-sky-400",
  warning: "bg-amber-500/15 text-amber-700 dark:text-amber-500",
  critical: "bg-destructive/10 text-destructive",
};

const SEVERITY_LABEL: Record<AlertSeverity, string> = {
  info: "Info",
  warning: "Warning",
  critical: "Critical",
};

export function AlertSeverityBadge({
  severity,
  className,
}: {
  severity: AlertSeverity;
  className?: string;
}) {
  return (
    <Badge className={cn(SEVERITY_STYLES[severity], className)}>
      {SEVERITY_LABEL[severity]}
    </Badge>
  );
}
