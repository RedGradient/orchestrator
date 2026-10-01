import { AlertCircle, Inbox, LoaderCircle, type LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

type StatePanelKind = "loading" | "empty" | "error"

const stateIcons: Record<StatePanelKind, LucideIcon> = {
  loading: LoaderCircle,
  empty: Inbox,
  error: AlertCircle,
}

export interface StatePanelProps {
  kind: StatePanelKind
  title: string
  description?: string
  actionLabel?: string
  onAction?: () => void
  children?: ReactNode
  className?: string
}

export function StatePanel({
  kind,
  title,
  description,
  actionLabel,
  onAction,
  children,
  className,
}: StatePanelProps) {
  const Icon = stateIcons[kind]

  return (
    <section
      className={cn(
        "flex min-h-52 flex-col items-center justify-center rounded-lg border border-dashed bg-card px-6 py-10 text-center",
        kind === "error" && "border-destructive/40 bg-destructive/5",
        className,
      )}
      role={kind === "error" ? "alert" : "status"}
      aria-live="polite"
    >
      <span
        className={cn(
          "mb-4 flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground",
          kind === "error" && "bg-destructive/10 text-destructive",
        )}
      >
        <Icon aria-hidden="true" className={cn("size-5", kind === "loading" && "animate-spin")} />
      </span>
      <h2 className="font-medium">{title}</h2>
      {description ? (
        <p className="mt-1.5 max-w-md text-sm leading-6 text-muted-foreground">{description}</p>
      ) : null}
      {children}
      {actionLabel && onAction ? (
        <Button type="button" variant="outline" size="sm" className="mt-5" onClick={onAction}>
          {actionLabel}
        </Button>
      ) : null}
    </section>
  )
}
