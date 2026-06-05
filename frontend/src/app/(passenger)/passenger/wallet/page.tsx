"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, ArrowDownLeft, ArrowLeft, ArrowUpRight, Wallet } from "lucide-react";

import { CursorPager } from "@/components/data-table";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useCursorList } from "@/hooks/use-cursor-list";
import { ApiError, toApiError } from "@/lib/api/error";
import { getWalletBalance, listWalletTransactions, type WalletTxnListParams } from "@/lib/api/wallet";
import type { WalletTransaction } from "@/lib/api/types";
import { formatDateTime, formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";
import { QUERY_KEYS } from "@/lib/queryClient";

export default function WalletPage() {
  const balanceQuery = useQuery<{ balance: string }, ApiError>({
    queryKey: QUERY_KEYS.wallet,
    queryFn: getWalletBalance,
  });

  const params: WalletTxnListParams = { ordering: "-created_at" };
  const list = useCursorList<WalletTransaction, WalletTxnListParams>({
    queryKey: QUERY_KEYS.walletTxns(params),
    params,
    fetchPage: (args) => listWalletTransactions(args),
  });

  return (
    <div className="grid gap-6">
      <div>
        <Link
          href="/passenger/tickets"
          className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Tickets
        </Link>
        <h1 className="mt-3 font-display text-3xl font-semibold tracking-tight">Wallet</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Store credit from ticket refunds. Use it to pay for your next ride.
        </p>
      </div>

      <Card className="bg-muted/30">
        <CardContent className="flex items-center justify-between gap-4 py-6">
          <div className="flex items-center gap-3">
            <span className="grid size-11 place-items-center rounded-xl bg-background text-foreground ring-1 ring-border">
              <Wallet className="size-5" />
            </span>
            <div>
              <p className="label-mono text-[0.6rem] text-muted-foreground">Balance</p>
              {balanceQuery.isLoading ? (
                <Skeleton className="mt-1 h-8 w-28" />
              ) : balanceQuery.isError ? (
                <p className="text-sm text-destructive">
                  {toApiError(balanceQuery.error).message}
                </p>
              ) : (
                <p className="font-display text-3xl font-semibold tracking-tight">
                  {formatMoney(balanceQuery.data!.balance)}
                </p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <section className="grid gap-3">
        <h2 className="label-mono text-xs text-muted-foreground">Transactions</h2>
        {list.isError ? (
          <div className="flex items-center justify-center gap-2 rounded-xl border border-destructive/30 bg-destructive/5 py-10 text-sm text-destructive">
            <AlertCircle className="size-4" />
            {toApiError(list.error).message}
          </div>
        ) : list.isLoading ? (
          <div className="grid gap-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-14 rounded-lg" />
            ))}
          </div>
        ) : list.rows.length === 0 ? (
          <div className="rounded-xl border border-dashed py-12 text-center text-sm text-muted-foreground">
            No transactions yet. Refund a ticket to add credit.
          </div>
        ) : (
          <ul className="grid gap-2">
            {list.rows.map((txn) => (
              <TxnRow key={txn.id} txn={txn} />
            ))}
          </ul>
        )}

        <CursorPager
          hasPrev={list.hasPrev}
          hasNext={list.hasNext}
          onPrev={list.prev}
          onNext={list.next}
          isFetching={list.isFetching}
        />
      </section>
    </div>
  );
}

function TxnRow({ txn }: { txn: WalletTransaction }) {
  const isCredit = txn.kind === "credit";
  return (
    <li className="flex items-center justify-between gap-3 rounded-lg border bg-muted/20 px-3 py-2.5">
      <div className="flex min-w-0 items-center gap-3">
        <span
          className={cn(
            "grid size-8 shrink-0 place-items-center rounded-full",
            isCredit
              ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
              : "bg-muted text-muted-foreground",
          )}
        >
          {isCredit ? (
            <ArrowDownLeft className="size-4" />
          ) : (
            <ArrowUpRight className="size-4" />
          )}
        </span>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium capitalize">{txn.reference || txn.kind}</p>
          <p className="label-mono text-[0.6rem] text-muted-foreground">
            {formatDateTime(txn.created_at)}
          </p>
        </div>
      </div>
      <div className="text-right">
        <p
          className={cn(
            "text-sm font-medium",
            isCredit ? "text-emerald-600 dark:text-emerald-400" : "text-foreground",
          )}
        >
          {isCredit ? "+" : "−"}
          {formatMoney(txn.amount)}
        </p>
        <p className="label-mono text-[0.6rem] text-muted-foreground">
          bal {formatMoney(txn.balance_after)}
        </p>
      </div>
    </li>
  );
}
