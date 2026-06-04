import { Badge } from "@/components/ui/badge";
import type { PaymentStatus, TicketStatus } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const TICKET_STYLES: Record<TicketStatus, string> = {
  issued: "bg-sky-500/15 text-sky-700 dark:text-sky-400",
  active: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  used: "bg-muted text-muted-foreground",
  expired: "bg-muted text-muted-foreground",
  refunded: "bg-amber-500/15 text-amber-700 dark:text-amber-500",
  cancelled: "bg-destructive/10 text-destructive",
};

const TICKET_LABEL: Record<TicketStatus, string> = {
  issued: "Issued",
  active: "Active",
  used: "Used",
  expired: "Expired",
  refunded: "Refunded",
  cancelled: "Cancelled",
};

export function TicketStatusBadge({
  status,
  className,
}: {
  status: TicketStatus;
  className?: string;
}) {
  return <Badge className={cn(TICKET_STYLES[status], className)}>{TICKET_LABEL[status]}</Badge>;
}

const PAYMENT_STYLES: Record<PaymentStatus, string> = {
  pending: "bg-amber-500/15 text-amber-700 dark:text-amber-500",
  success: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  failed: "bg-destructive/10 text-destructive",
  refunded: "bg-muted text-muted-foreground",
};

const PAYMENT_LABEL: Record<PaymentStatus, string> = {
  pending: "Payment pending",
  success: "Paid",
  failed: "Payment failed",
  refunded: "Refunded",
};

export function PaymentStatusBadge({
  status,
  className,
}: {
  status: PaymentStatus;
  className?: string;
}) {
  return <Badge className={cn(PAYMENT_STYLES[status], className)}>{PAYMENT_LABEL[status]}</Badge>;
}
